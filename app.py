import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Configuración global
st.set_page_config(layout="wide")

# --- Encabezado institucional ---
col1, col2, col3 = st.columns([1, 6, 1])
with col1:
    st.image("https://raw.githubusercontent.com/oscarovalles/rediaas/main/data/logo_imss.png", width=90)
with col2:
    st.markdown("""
        <h4 style='text-align: center;'>UMAE Hospital de Especialidades CMN SXXI</h4>
        <h5 style='text-align: center;'>División de Epidemiología</h5>
        <h2 style='text-align: center;'>Monitoreo de IAAS - REDIAAS</h2>
    """, unsafe_allow_html=True)
with col3:
    st.image("https://raw.githubusercontent.com/oscarovalles/rediaas/main/data/logo_epi.png", width=90)

# --- Módulo: Riesgo IAAS por cama ---
def modulo_riesgo():
    st.subheader("🛏️ Mapa de Riesgo de IAAS por Cama")

    @st.cache_data
    def cargar_datos():
        df_coords = pd.read_csv("plantilla_coordenadas_camas.csv")
        df_iaas = pd.read_csv("rediaas.csv")
        return df_coords, df_iaas

    df_coords, df_iaas = cargar_datos()

    df_riesgo = (
        df_iaas.groupby('cama')['iaas_sino']
        .agg(['sum', 'count'])
        .reset_index()
        .rename(columns={'sum': 'casos_iaas', 'count': 'total_pacientes'})
    )
    df_riesgo['porcentaje_iaas'] = 100 * df_riesgo['casos_iaas'] / df_riesgo['total_pacientes']
    df_final = pd.merge(df_coords, df_riesgo[['cama', 'porcentaje_iaas']], on='cama', how='left')
    df_final['porcentaje_iaas'] = df_final['porcentaje_iaas'].fillna(0)

    orden_pisos = ["5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur", "2B Norte", "2B Sur",
                   "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A"]
    df_final['piso'] = pd.Categorical(df_final['piso'], categories=orden_pisos, ordered=True)

    piso_sel = st.selectbox("Selecciona el piso a visualizar:", options=df_final['piso'].dropna().unique())
    df_piso = df_final[df_final['piso'] == piso_sel].copy()
    df_piso['porcentaje_iaas_str'] = df_piso['porcentaje_iaas'].map("{:.2f}%".format)

    fig = px.scatter(
        df_piso, x='coord_x', y='coord_y', color='porcentaje_iaas',
        color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
        range_color=(0, 100), text='cama',
        labels={'coord_x': 'Coordenada X', 'coord_y': 'Coordenada Y', 'porcentaje_iaas': '% IAAS'},
        hover_data={'cama': True, 'porcentaje_iaas_str': True, 'porcentaje_iaas': False},
        height=650
    )
    fig.update_traces(marker=dict(size=25), textposition='top center')
    fig.update_layout(title=f"🛏️ Mapa de Riesgo – Piso {piso_sel}", title_font=dict(size=16), yaxis_autorange="reversed")

    st.plotly_chart(fig, use_container_width=True)

    st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

# --- Módulo: Vigilancia Activa ---
def modulo_vigilancia():
    st.subheader("🧪 Vigilancia Activa por Sector Hospitalario")

    planos = [f.replace(".png", "") for f in sorted(os.listdir("data/planos")) if f.endswith(".png")]
    plano_sel = st.selectbox("Selecciona el sector del hospital:", options=planos)
    imagen_path = os.path.join("data/planos", f"{plano_sel}.png")

    if os.path.exists(imagen_path):
        st.image(imagen_path, use_container_width=True)
    else:
        st.error(f"No se encontró el plano: {imagen_path}")

    st.subheader("Curva Epidémica de IAAS")
    curva_epidemica_path = "data/curva_epidemica.png"
    if os.path.exists(curva_epidemica_path):
        st.image(curva_epidemica_path, use_container_width=True)
    else:
        st.warning("No se encontró la imagen de la curva epidémica.")

    st.subheader("Curva de Captura INOSO")
    curva_captura_path = "data/curva_captura.png"
    if os.path.exists(curva_captura_path):
        st.image(curva_captura_path, use_container_width=True)
    else:
        st.warning("No se encontró la imagen de la curva de captura INOSO.")

    st.subheader("Laboratorio (cultivos/FilmArray)")
    laboratorio_path = "data/laboratorio.png"
    if os.path.exists(laboratorio_path):
        st.image(laboratorio_path, use_container_width=True)
    else:
        st.warning("No se encontró la imagen del laboratorio.")

    st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

# --- Interfaz principal con menú único (solo botones grandes) ---
if 'menu' not in st.session_state:
    st.session_state.menu = None

if st.session_state.menu is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("###")
        if st.button("📊 Riesgos de IAAS por cama", key="btn_riesgo", use_container_width=True):
            st.session_state.menu = "riesgo"
        if st.button("🧪 Vigilancia activa", key="btn_vigilancia", use_container_width=True):
            st.session_state.menu = "vigilancia"

elif st.session_state.menu == "riesgo":
    modulo_riesgo()
elif st.session_state.menu == "vigilancia":
    modulo_vigilancia()
