import streamlit as st
import os
from PIL import Image
import pandas as pd
import plotly.express as px

# ----------- CONFIGURACIÓN DE PÁGINA -----------
st.set_page_config(layout="wide", page_title="Dashboard IAAS", page_icon="✅")

# ----------- TÍTULO INSTITUCIONAL CON LOGOS -----------
col1, col2, col3 = st.columns([1, 6, 1])

with col1:
    st.image("assets/imss_logo.png", width=100)

with col2:
    st.markdown("""
        <h4 style='text-align: center;'>Instituto Mexicano del Seguro Social</h4>
        <h5 style='text-align: center;'>UMAE Hospital de Especialidades CMN SXXI</h5>
        <h5 style='text-align: center;'>Dashboard de IAAS</h5>
    """, unsafe_allow_html=True)

with col3:
    st.image("assets/residencia_epi_logo.png", width=100)

st.markdown("---")

# ----------- MENÚ LATERAL -----------
st.sidebar.header("🔹 Módulos del Dashboard")
mostrar_plano = st.sidebar.checkbox("Mostrar plano del hospital")
mostrar_curva_iaas = st.sidebar.checkbox("Mostrar curva epidémica IAAS")
mostrar_curva_inoso = st.sidebar.checkbox("Mostrar curva de captura INOSO")
mostrar_laboratorio = st.sidebar.checkbox("Mostrar resultados de laboratorio")

# ----------- SECCIÓN: PLANO HOSPITALARIO -----------
if mostrar_plano:
    st.subheader("Mapa hospitalario por sector")
    planos = os.listdir("data/planos")
    plano_seleccionado = st.selectbox("Selecciona el plano a mostrar:", planos)
    st.image(f"data/planos/{plano_seleccionado}", use_column_width=True)
    st.markdown("---")

# ----------- SECCIÓN: CURVA EPIDÉMICA IAAS -----------
if mostrar_curva_iaas:
    st.subheader("Curva epidémica de IAAS por sector")

    uploaded_file = st.file_uploader("Sube el archivo de IAAS (.csv o .dta)", type=["csv", "dta"], key="iaas_curva")
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, parse_dates=["fec_evento"])
        elif uploaded_file.name.endswith(".dta"):
            import pyreadstat
            df, meta = pyreadstat.read_dta(uploaded_file)
            df["fec_evento"] = pd.to_datetime(df["fec_evento"], errors='coerce')

        required_cols = {"fec_evento", "sector", "iaas_sino"}
        if required_cols.issubset(df.columns):
            df_iaas = df[df["iaas_sino"] == 1].copy()
            df_iaas["semana_epi"] = df_iaas["fec_evento"].dt.to_period("W").apply(lambda r: r.start_time)
            curva = df_iaas.groupby(["semana_epi", "sector"]).size().reset_index(name="casos")

            fig = px.line(
                curva,
                x="semana_epi",
                y="casos",
                color="sector",
                markers=True,
                title="Casos de IAAS por semana y sector",
                labels={"semana_epi": "Semana", "casos": "Casos de IAAS"}
            )

            fig.update_layout(xaxis_title="Semana epidemiológica", yaxis_title="Casos", legend_title="Sector")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("El archivo debe tener las columnas: fec_evento, sector, iaas_sino.")
    else:
        st.info("Por favor sube un archivo con los datos de IAAS.")
    st.markdown("---")

# ----------- SECCIÓN: CURVA CAPTURA INOSO -----------
if mostrar_curva_inoso:
    st.subheader("Curva de captura de registros en INOSO")
    st.info("[AQUÍ VA LA CURVA DE CAPTURA - datos por integrar]")
    st.markdown("---")

# ----------- SECCIÓN: LABORATORIO -----------
if mostrar_laboratorio:
    st.subheader("Resultados de laboratorio (cultivos y FilmArray)")
    st.info("[AQUÍ VA LA TABLA DE LABORATORIO - datos por integrar]")
    st.markdown("---")

# ----------- PIE -----------
st.markdown("<small>Versión prototipo - Julio 2025</small>", unsafe_allow_html=True)
