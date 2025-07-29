import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- Encabezado institucional ---
def encabezado():
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.image("https://raw.githubusercontent.com/epivigilancia/vigilancia_iaas/main/img/logo_imss.png", width=100)
    with col2:
        st.markdown("<h4 style='text-align: center;'>UMAE Hospital de Especialidades CMN SXXI</h4>", unsafe_allow_html=True)
        st.markdown("<h5 style='text-align: center;'>División de Epidemiología</h5>", unsafe_allow_html=True)
    with col3:
        st.image("https://raw.githubusercontent.com/epivigilancia/vigilancia_iaas/main/img/logo_epi.png", width=100)

# --- Pantalla de inicio ---
def menu_inicio():
    encabezado()
    st.markdown("<h2 style='text-align: center;'>Monitoreo de IAAS - REDIAAS</h2>", unsafe_allow_html=True)
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛏️ Riesgos de IAAS por cama"):
            st.session_state.pantalla = "riesgos"
    with col2:
        if st.button("📊 Vigilancia activa"):
            st.session_state.pantalla = "vigilancia"

# --- Módulo 1: Riesgos IAAS por cama ---
def modulo_riesgos():
    if st.button("🔙 Regresar al menú"): st.session_state.pantalla = "inicio"
    encabezado()

    @st.cache_data
    def cargar_datos():
        df_coords = pd.read_csv("plantilla_coordenadas_camas.csv")
        df_iaas = pd.read_csv("rediaas.csv")
        return df_coords, df_iaas

    df_coords, df_iaas = cargar_datos()

    assert 'cama' in df_iaas.columns and 'iaas_sino' in df_iaas.columns
    assert all(col in df_coords.columns for col in ['cama', 'coord_x', 'coord_y', 'piso'])

    df_riesgo = (
        df_iaas.groupby('cama')['iaas_sino']
        .agg(['sum', 'count'])
        .reset_index()
        .rename(columns={'sum': 'casos_iaas', 'count': 'total_pacientes'})
    )
    df_riesgo['porcentaje_iaas'] = 100 * df_riesgo['casos_iaas'] / df_riesgo['total_pacientes']
    df_final = pd.merge(df_coords, df_riesgo[['cama', 'porcentaje_iaas']], on='cama', how='left')
    df_final['porcentaje_iaas'] = df_final['porcentaje_iaas'].fillna(0)

    orden_pisos = ["5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur",
                   "2B Norte", "2B Sur", "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A"]
    df_final['piso'] = pd.Categorical(df_final['piso'], categories=orden_pisos, ordered=True)
    pisos_disponibles = df_final['piso'].dropna().unique()
    piso_sel = st.selectbox("🛏️🦠 Selecciona el piso a visualizar", options=pisos_disponibles)

    df_piso = df_final[df_final['piso'] == piso_sel].copy()
    df_piso['porcentaje_iaas_str'] = df_piso['porcentaje_iaas'].map("{:.2f}%".format)

    fig = px.scatter(
        df_piso, x='coord_x', y='coord_y', color='porcentaje_iaas',
        color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
        range_color=(0, 100), text='cama', height=650,
        labels={'coord_x': 'Coordenada X', 'coord_y': 'Coordenada Y', 'porcentaje_iaas': '% IAAS'},
        hover_data={'cama': True, 'coord_x': True, 'coord_y': True,
                    'porcentaje_iaas_str': True, 'porcentaje_iaas': False}
    )
    fig.update_traces(marker=dict(size=25), textposition='top center')
    fig.update_layout(
        title={'text': f"🛏️ Mapa de Riesgo de IAAS – Piso {piso_sel}", 'x': 0.01, 'xanchor': 'left'},
        title_font=dict(size=16), yaxis_autorange="reversed",
        coloraxis_colorbar=dict(title="% IAAS", tickformat=".0f", ticks="outside")
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Módulo 2: Vigilancia activa ---
def modulo_vigilancia():
    if st.button("🔙 Regresar al menú"): st.session_state.pantalla = "inicio"
    encabezado()

    planos = [f.replace(".png", "") for f in sorted(os.listdir("data/planos"), reverse=True) if f.endswith(".png")]
    sector_sel = st.selectbox("Selecciona el sector del hospital:", planos)
    st.image(f"data/planos/{sector_sel}.png", caption=f"Plano del sector {sector_sel}", use_column_width=True)
    # Aquí podrías agregar gráficas adicionales como curva epidémica, etc.

# --- Controlador principal ---
if 'pantalla' not in st.session_state:
    st.session_state.pantalla = 'inicio'

if st.session_state.pantalla == 'inicio':
    menu_inicio()
elif st.session_state.pantalla == 'riesgos':
    modulo_riesgos()
elif st.session_state.pantalla == 'vigilancia':
    modulo_vigilancia(
