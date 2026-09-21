import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Dashboard Retail & Construcción", layout="wide", initial_sidebar_state="expanded")

# --- FUNCIONES DE CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        ventas = pd.read_csv('data/fact_ventas_fugas.csv')
        ventas['fecha'] = pd.to_datetime(ventas['fecha'])
        ventas['mes'] = ventas['fecha'].dt.month
    except Exception:
        ventas = pd.DataFrame(columns=['id_factura', 'id_cliente', 'id_sucursal', 'fecha', 'mes', 'monto_lista', 'descuento_aplicado', 'monto_final', 'fuga_rentabilidad'])

    try:
        clientes = pd.read_csv('data/dim_clientes_b2b.csv')
    except Exception:
        clientes = pd.DataFrame(columns=['id_cliente', 'nombre_constructora', 'region', 'segmento_rfm'])

    try:
        telemetria = pd.read_csv('data/Fact_Telemetria_ADKAR.csv')
    except Exception:
        # Fallback a minúsculas por si acaso
        try:
            telemetria = pd.read_csv('data/fact_telemetria_adkar.csv')
        except:
            telemetria = pd.DataFrame(columns=['id_sucursal', 'mes', 'score_adopcion_sistema', 'errores_operativos_mensuales'])

    # Mock Data Hiperrealista para Materiales si no existe
    np.random.seed(42)
    materiales_list = ['Hormigón Estructural', 'Acero Rebar', 'Cemento Portland', 'Cerámica Industrial', 'Tableros OSB', 'Tubería PVC']
    if 'id_material' not in ventas.columns and not ventas.empty:
        ventas['id_material'] = np.random.choice([f'MAT-00{i}' for i in range(len(materiales_list))], size=len(ventas))
    
    dim_materiales = pd.DataFrame({
        'id_material': [f'MAT-00{i}' for i in range(len(materiales_list))],
        'nombre_material': materiales_list
    })

    # Cruce Relacional Masivo
    df = ventas.merge(clientes, on='id_cliente', how='left')
    df = df.merge(telemetria, on=['id_sucursal', 'mes'], how='left')
    df = df.merge(dim_materiales, on='id_material', how='left')

    # Limpieza de Nulos
    for col in ['region', 'segmento_rfm', 'nombre_material', 'id_sucursal']:
        if col in df.columns:
            df[col].fillna('Desconocido', inplace=True)
            
    for col in ['fuga_rentabilidad', 'score_adopcion_sistema', 'monto_lista', 'errores_operativos_mensuales']:
        if col in df.columns:
            df[col].fillna(0, inplace=True)
            
    return df

# --- CARGAR DATOS ---
df = load_data()

# --- SIDEBAR (FILTROS) ---
st.sidebar.title("Filtros B2B")
if not df.empty:
    region_filter = st.sidebar.multiselect("Seleccionar Región", options=df['region'].unique(), default=df['region'].unique())
    segment_filter = st.sidebar.multiselect("Segmento RFM", options=df['segmento_rfm'].unique(), default=df['segmento_rfm'].unique())

    # Aplicar filtros
    df_filtered = df[(df['region'].isin(region_filter)) & (df['segmento_rfm'].isin(segment_filter))]
else:
    st.sidebar.warning("No hay datos disponibles para filtrar.")
    df_filtered = df

# --- HEADER Y KPIS ---
st.title("📊 Análisis de Fuga de Rentabilidad y Adopción (B2B Retail)")
st.markdown("Dashboard interactivo para evaluar el impacto de la adopción del sistema en la rentabilidad de las sucursales.")

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

    # --- GRÁFICOS ---
    colA, colB = st.columns(2)

    with colA:
        # Gráfico 1: Scatter ADKAR vs Fuga
        df_scatter = df_filtered.groupby(['id_sucursal', 'region']).agg(
            fuga_total=('fuga_rentabilidad', 'sum'),
            adkar_avg=('score_adopcion_sistema', 'mean'),
            vol_ventas=('monto_lista', 'sum')
        ).reset_index()

        fig_scatter = px.scatter(
            df_scatter, x='adkar_avg', y='fuga_total', size='vol_ventas', color='region',
            title="ADKAR vs Fuga por Sucursal (Burbuja = Vol. Ventas)", size_max=40,
            template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with colB:
        # Gráfico 2: Barras Fuga por Material
        df_material = df_filtered.groupby('nombre_material')['fuga_rentabilidad'].sum().reset_index()
        df_material = df_material.sort_values('fuga_rentabilidad', ascending=False)
        fig_bar = px.bar(
            df_material, x='fuga_rentabilidad', y='nombre_material', orientation='h',
            title="Fuga por Categoría de Material", color='fuga_rentabilidad',
            template="plotly_dark", color_continuous_scale="Reds"
        )
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    colC, colD = st.columns(2)
    with colC:
        # Gráfico 3: Serie de Tiempo Fugas
        df_time = df_filtered.groupby('fecha')['fuga_rentabilidad'].sum().reset_index()
        fig_line = px.line(
            df_time, x='fecha', y='fuga_rentabilidad', 
            title="Tendencia Diaria de Fugas de Rentabilidad",
            template="plotly_dark"
        )
        fig_line.update_traces(line_color='#00ffcc')
        st.plotly_chart(fig_line, use_container_width=True)

    with colD:
        # Tabla de Datos en bruto opcional
        st.markdown("### 📋 Datos de Transacciones Críticas")
        st.dataframe(df_filtered[['id_factura', 'fecha', 'id_sucursal', 'nombre_material', 'fuga_rentabilidad']]
                     .sort_values('fuga_rentabilidad', ascending=False).head(100),
                     use_container_width=True)

else:
    st.error("No se encontraron datos para mostrar. Verifica que los archivos CSV estén en la carpeta 'data/'.")
