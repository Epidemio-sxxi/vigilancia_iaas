import streamlit as st
import os
import pandas as pd
import plotly.express as px
from PIL import Image

# ----------- CONFIGURACIÓN DE PÁGINA -----------
st.set_page_config(layout="wide", page_title="Dashboard IAAS", page_icon="✅")

# ----------- FUNCIONES AUXILIARES -----------
def mostrar_encabezado():
    col1, col2, col3 = st.columns([1, 6, 1])

    with col1:
        st.image("assets/imss_logo.png", width=90)

    with col2:
        st.markdown("""
            <div style='text-align: center; line-height: 1.2;'>
                <h4>Instituto Mexicano del Seguro Social</h4>
                <h5>UMAE Hospital de Especialidades CMN SXXI</h5>
                <h5>División de Epidemiología Hospitalaria</h5>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.image("assets/residencia_epi_logo.png", width=90)

    st.markdown("---")

def mostrar_menu_inicial():
    st.markdown("""
        <h2 style='text-align: center;'>Monitoreo de IAAS</h2>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛏️ Riesgos de IAAS por cama", use_container_width=True):
            st.session_state.vista = "riesgos"
    with col2:
        if st.button("🔍 Vigilancia activa", use_container_width=True):
            st.session_state.vista = "vigilancia"

# ----------- VISTA: RIESGOS POR CAMA -----------
def vista_riesgos():
    st.button("⬅️ Regresar al menú", on_click=volver_al_inicio)
    st.subheader("Visualización de riesgos de IAAS por cama (2024)")

    # Subir archivo rediaas
    archivo = st.file_uploader("Sube la base 'rediaas.dta'", type=["dta"], key="upload_riesgos")
    coords = st.file_uploader("Sube la plantilla de coordenadas (plantilla_coordenadas_camas.csv)", type="csv")

    if archivo and coords:
        import pyreadstat
        df, meta = pyreadstat.read_dta(archivo)
        df_coords = pd.read_csv(coords)

        if 'cama' in df.columns and 'iaas_sino' in df.columns:
            riesgo = df.groupby('cama')['iaas_sino'].mean().reset_index(name='riesgo')
            df_mapa = df_coords.merge(riesgo, on='cama', how='left')
            df_mapa['riesgo'] = df_mapa['riesgo'].fillna(0)

            fig = px.scatter(
                df_mapa,
                x="x", y="y", text="cama",
                color="riesgo",
                color_continuous_scale=["green", "yellow", "red"],
                range_color=[0, 1],
                title="Mapa de camas con riesgo de IAAS",
            )
            fig.update_traces(textposition='top center')
            fig.update_layout(height=600, xaxis_visible=False, yaxis_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("La base debe tener las columnas 'cama' e 'iaas_sino'")

# ----------- VISTA: VIGILANCIA ACTIVA -----------
def vista_vigilancia():
    st.button("⬅️ Regresar al menú", on_click=volver_al_inicio)
    mostrar_encabezado()

    # ----------- MENÚ LATERAL -----------
    st.sidebar.header("🔹 Módulos")

    planos_files = os.listdir("data/planos")
    planos_nombres = [os.path.splitext(f)[0] for f in planos_files if f.endswith(".png")]
    planos_nombres.sort(reverse=True)
    sector_seleccionado = st.sidebar.selectbox("Selecciona el sector del hospital:", planos_nombres)

    mostrar_curva_iaas = st.sidebar.checkbox("Mostrar curva epidémica IAAS")
    mostrar_curva_inoso = st.sidebar.checkbox("Mostrar curva de captura INOSO")
    mostrar_laboratorio = st.sidebar.checkbox("Mostrar resultados de laboratorio")

    st.subheader("Mapeo de camas")
    st.image(f"data/planos/{sector_seleccionado}.png", use_container_width=True)
    st.markdown("---")

    if mostrar_curva_iaas:
        st.subheader("Curva epidémica de IAAS por sector")
        archivo = st.file_uploader("Sube el archivo de IAAS (.csv o .dta)", type=["csv", "dta"], key="iaas")
        if archivo is not None:
            if archivo.name.endswith(".csv"):
                df = pd.read_csv(archivo, parse_dates=["fec_evento"])
            else:
                import pyreadstat
                df, meta = pyreadstat.read_dta(archivo)
                df["fec_evento"] = pd.to_datetime(df["fec_evento"], errors='coerce')

            if {"fec_evento", "sector", "iaas_sino"}.issubset(df.columns):
                df_iaas = df[df["iaas_sino"] == 1].copy()
                df_iaas["semana_epi"] = df_iaas["fec_evento"].dt.to_period("W").apply(lambda r: r.start_time)
                curva = df_iaas.groupby(["semana_epi", "sector"]).size().reset_index(name="casos")

                fig = px.line(curva, x="semana_epi", y="casos", color="sector", markers=True,
                              labels={"semana_epi": "Semana", "casos": "Casos de IAAS"})
                fig.update_layout(xaxis_title="Semana epidemiológica", yaxis_title="Casos", legend_title="Sector")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("El archivo debe tener las columnas: fec_evento, sector, iaas_sino.")

    if mostrar_curva_inoso:
        st.subheader("Curva de captura de registros en INOSO")
        st.info("[AQUÍ VA LA CURVA DE CAPTURA - datos por integrar]")
        st.markdown("---")

    if mostrar_laboratorio:
        st.subheader("Resultados de laboratorio (cultivos y FilmArray)")
        st.info("[AQUÍ VA LA TABLA DE LABORATORIO - datos por integrar]")
        st.markdown("---")

    st.markdown("<small>Versión prototipo - Julio 2025</small>", unsafe_allow_html=True)

# ----------- FUNCIONES DE ESTADO -----------
def volver_al_inicio():
    st.session_state.vista = "inicio"

# ----------- CONTROL DE VISTA -----------
if "vista" not in st.session_state:
    st.session_state.vista = "inicio"

if st.session_state.vista == "inicio":
    mostrar_menu_inicial()
elif st.session_state.vista == "riesgos":
    vista_riesgos()
elif st.session_state.vista == "vigilancia":
    vista_vigilancia()
