import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import warnings
import os

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Dashboard Retail & Construcción", layout="wide", initial_sidebar_state="expanded")

# --- FUNCIONES DE CARGA DE DATOS ---
@st.cache_data
def load_data():
    # Función para leer sin romper la aplicación
    def read_csv_safe(path, default_cols):
        try:
            if os.path.exists(path):
                return pd.read_csv(path)
            # Buscar en minúsculas por si acaso
            lower_path = path.lower()
            if os.path.exists(lower_path):
                return pd.read_csv(lower_path)
        except Exception as e:
            st.error(f"Error interno leyendo {path}: {e}")
            
        return pd.DataFrame(columns=default_cols)

    # Carga segura
    ventas = read_csv_safe('data/fact_ventas_fugas.csv', 
                           ['id_factura', 'id_cliente', 'id_sucursal', 'fecha', 'mes', 'monto_lista', 'descuento_aplicado', 'monto_final', 'fuga_rentabilidad'])
    
    if not ventas.empty and 'fecha' in ventas.columns:
        ventas['fecha'] = pd.to_datetime(ventas['fecha'], errors='coerce')
        ventas['mes'] = ventas['fecha'].dt.month

    clientes = read_csv_safe('data/dim_clientes_b2b.csv', 
                             ['id_cliente', 'nombre_constructora', 'region', 'segmento_rfm'])

    telemetria = read_csv_safe('data/Fact_Telemetria_ADKAR.csv', 
                               ['id_sucursal', 'mes', 'score_adopcion_sistema', 'errores_operativos_mensuales'])

    # Mock Data para Materiales
    np.random.seed(42)
    materiales_list = ['Hormigón Estructural', 'Acero Rebar', 'Cemento Portland', 'Cerámica Industrial', 'Tableros OSB', 'Tubería PVC']
    
    if 'id_material' not in ventas.columns:
        if not ventas.empty:
            ventas['id_material'] = np.random.choice([f'MAT-00{i}' for i in range(len(materiales_list))], size=len(ventas))
        else:
            ventas['id_material'] = pd.Series(dtype='str')
    
    dim_materiales = pd.DataFrame({
        'id_material': [f'MAT-00{i}' for i in range(len(materiales_list))],
        'nombre_material': materiales_list
    })

    # SI ESTÁ VACÍO, ABORTAR EL MERGE PARA EVITAR EL KEYERROR
    if ventas.empty:
        st.warning("⚠️ No se encontraron datos en los archivos CSV (o no se han subido a la carpeta 'data'). Mostrando dashboard vacío.")
        return ventas

    # Cruce Relacional Seguro
    df = ventas.merge(clientes, on='id_cliente', how='left') if 'id_cliente' in ventas.columns and 'id_cliente' in clientes.columns else ventas
    
    if 'id_sucursal' in df.columns and 'mes' in df.columns and 'id_sucursal' in telemetria.columns:
        df = df.merge(telemetria, on=['id_sucursal', 'mes'], how='left')
        
    if 'id_material' in df.columns:
        df = df.merge(dim_materiales, on='id_material', how='left')

    # Limpieza de Nulos
    for col in ['region', 'segmento_rfm', 'nombre_material', 'id_sucursal']:
        if col in df.columns:
            df[col] = df[col].fillna('Desconocido')
            
    for col in ['fuga_rentabilidad', 'score_adopcion_sistema', 'monto_lista', 'errores_operativos_mensuales']:
        if col in df.columns:
            df[col] = df[col].fillna(0)
            
    return df

# --- INICIO DEL DASHBOARD ---
df = load_data()

st.sidebar.title("Filtros B2B")
if not df.empty:
    region_filter = st.sidebar.multiselect("Seleccionar Región", options=df['region'].unique(), default=df['region'].unique())
    segment_filter = st.sidebar.multiselect("Segmento RFM", options=df['segmento_rfm'].unique(), default=df['segmento_rfm'].unique())
    df_filtered = df[(df['region'].isin(region_filter)) & (df['segmento_rfm'].isin(segment_filter))]
else:
    df_filtered = df

st.title("📊 Análisis de Fuga de Rentabilidad y Adopción (B2B Retail)")

if not df_filtered.empty:
    kpi_fuga_total = df_filtered['fuga_rentabilidad'].sum() / 1e6
    kpi_adkar_avg = df_filtered.groupby('id_sucursal')['score_adopcion_sistema'].mean().mean()
    if pd.isna(kpi_adkar_avg): kpi_adkar_avg = 0

    fuga_por_sucursal = df_filtered.groupby('id_sucursal')['fuga_rentabilidad'].sum()
    sucursal_critica = fuga_por_sucursal.idxmax() if not fuga_por_sucursal.empty else "N/A"
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Fuga Total Detectada", f"${kpi_fuga_total:,.2f}M", "-8% vs meta", delta_color="inverse")
    col2.metric("Score ADKAR Promedio", f"{kpi_adkar_avg:.1f}/5.0", "+0.2 pts")
    col3.metric("Sucursal Crítica", str(sucursal_critica))
    st.markdown("---")

    colA, colB = st.columns(2)
    with colA:
        df_scatter = df_filtered.groupby(['id_sucursal', 'region']).agg(fuga_total=('fuga_rentabilidad', 'sum'), adkar_avg=('score_adopcion_sistema', 'mean'), vol_ventas=('monto_lista', 'sum')).reset_index()
        fig_scatter = px.scatter(df_scatter, x='adkar_avg', y='fuga_total', size='vol_ventas', color='region', title="ADKAR vs Fuga por Sucursal", size_max=40, template="plotly_dark")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with colB:
        if 'nombre_material' in df_filtered.columns:
            df_material = df_filtered.groupby('nombre_material')['fuga_rentabilidad'].sum().reset_index().sort_values('fuga_rentabilidad', ascending=False)
            fig_bar = px.bar(df_material, x='fuga_rentabilidad', y='nombre_material', orientation='h', title="Fuga por Material", template="plotly_dark", color_continuous_scale="Reds")
            st.plotly_chart(fig_bar, use_container_width=True)

    colC, colD = st.columns(2)
    with colC:
        df_time = df_filtered.groupby('fecha')['fuga_rentabilidad'].sum().reset_index()
        fig_line = px.line(df_time, x='fecha', y='fuga_rentabilidad', title="Tendencia Diaria", template="plotly_dark")
        fig_line.update_traces(line_color='#00ffcc')
        st.plotly_chart(fig_line, use_container_width=True)

    with colD:
        st.markdown("### 📋 Datos Críticos")
        st.dataframe(df_filtered.head(100), use_container_width=True)
else:
    st.info("La aplicación está en línea, pero los archivos CSV de datos aún no se encuentran o están vacíos.")
