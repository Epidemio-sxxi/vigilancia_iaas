import pandas as pd
import plotly.express as px
import streamlit as st

# Título institucional
st.markdown("""
<h4 style='text-align: center;'>Instituto Mexicano del Seguro Social</h4>
<h5 style='text-align: center;'>UMAE Hospital de Especialidades Centro Médico Nacional Siglo XXI</h5>
<h5 style='text-align: center;'>División de Epidemiología</h5>
""", unsafe_allow_html=True)

# Función para cargar datos CSV
@st.cache_data
def cargar_datos():
    df_coords = pd.read_csv("plantilla_coordenadas_camas.csv")
    df_iaas = pd.read_csv("rediaas.csv")
    return df_coords, df_iaas

# Cargar datos
df_coords, df_iaas = cargar_datos()

# Validación de columnas
assert 'cama' in df_iaas.columns and 'iaas_sino' in df_iaas.columns, "Faltan columnas en rediaas.csv"
assert all(col in df_coords.columns for col in ['cama', 'coord_x', 'coord_y', 'piso']), "Faltan columnas en coordenadas"

# Cálculo de % IAAS
df_riesgo = (
    df_iaas.groupby('cama')['iaas_sino']
    .agg(['sum', 'count'])
    .reset_index()
    .rename(columns={'sum': 'casos_iaas', 'count': 'total_pacientes'})
)
df_riesgo['porcentaje_iaas'] = 100 * df_riesgo['casos_iaas'] / df_riesgo['total_pacientes']

# Unir datos
df_final = pd.merge(df_coords, df_riesgo[['cama', 'porcentaje_iaas']], on='cama', how='left')
df_final['porcentaje_iaas'] = df_final['porcentaje_iaas'].fillna(0)

# Orden de pisos
orden_pisos = [
    "5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur",
    "2B Norte", "2B Sur", "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A"
]
df_final['piso'] = pd.Categorical(df_final['piso'], categories=orden_pisos, ordered=True)

# Menú de selección
pisos_disponibles = df_final['piso'].dropna().unique()
piso_sel = st.selectbox("🛏️🦠 Selecciona el piso a visualizar", options=pisos_disponibles)

# Filtrar datos por piso
df_piso = df_final[df_final['piso'] == piso_sel].copy()
df_piso['porcentaje_iaas_str'] = df_piso['porcentaje_iaas'].map("{:.2f}%".format)

# Generar gráfico
fig = px.scatter(
    df_piso,
    x='coord_x',
    y='coord_y',
    color='porcentaje_iaas',
    color_continuous_scale=[
        (0.0, "green"),
        (0.5, "orange"),
        (1.0, "red")
    ],
    range_color=(0, 100),
    text='cama',
    labels={
        'coord_x': 'Coordenada X',
        'coord_y': 'Coordenada Y',
        'porcentaje_iaas': '% IAAS'
    },
    hover_data={
        'cama': True,
        'coord_x': True,
        'coord_y': True,
        'porcentaje_iaas_str': True,
        'porcentaje_iaas': False
    },
    height=650
)

fig.update_traces(marker=dict(size=25), textposition='top center')
fig.update_layout(
    title={
        'text': f"🛏️ Mapa de Riesgo de IAAS – Piso {piso_sel}",
        'x': 0.01,
        'xanchor': 'left'
    },
    title_font=dict(size=16),
    yaxis_autorange="reversed",
    coloraxis_colorbar=dict(
        title="% IAAS",
        tickformat=".0f",
        ticks="outside"
    ),
  
)

# Mostrar gráfico
st.plotly_chart(fig, use_container_width=True)
