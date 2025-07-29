import streamlit as st
import pandas as pd
import plotly.express as px
import pyreadstat

# ----------- CONFIGURACIÓN DE PÁGINA -----------
st.set_page_config(layout="wide", page_title="REDIAAS", page_icon="✅")

# ----------- LOGOS Y TÍTULOS -----------
def mostrar_encabezado():
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        st.image("assets/imss_logo.png", width=100)
    with col2:
        st.markdown("""
            <h4 style='text-align: center; margin-bottom:0;'>UMAE Hospital de Especialidades CMN SXXI</h4>
            <h5 style='text-align: center; margin-top:0;'>División de Epidemiología</h5>
        """, unsafe_allow_html=True)
    with col3:
        st.image("assets/residencia_epi_logo.png", width=100)

# ----------- MENÚ PRINCIPAL -----------
def menu_principal():
    mostrar_encabezado()
    st.markdown("<h1 style='text-align: center;'>REDIAAS</h1>", unsafe_allow_html=True)
    st.markdown("##")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Riesgos de IAAS por cama", use_container_width=True):
            st.session_state.pantalla = "riesgos"
    with col2:
        if st.button("🧪 Vigilancia activa", use_container_width=True):
            st.session_state.pantalla = "vigilancia"

# ----------- MÓDULO: RIESGO DE IAAS POR CAMA -----------
def modulo_riesgos_iaas():
    st.button("⬅️ Regresar al menú", on_click=regresar)

    st.markdown("## Visualización de riesgos de IAAS por cama (2024)")

    # Rutas a los archivos en GitHub
    rediaas_url = "https://raw.githubusercontent.com/usuario/repositorio/main/data/rediaas.csv"
    coordenadas_url = "https://raw.githubusercontent.com/usuario/repositorio/main/data/plantilla_coordenadas_camas.csv"

    # Cargar los datos
    df_rediaas = pd.read_csv(rediaas_url)
    df_coords = pd.read_csv(coordenadas_url)

    # Generar proporción de IAAS por cama
    iaas_por_cama = df_rediaas[df_rediaas["iaas_sino"] == 1].groupby("cama").size().reset_index(name="casos_iaas")
    total_por_cama = df_rediaas.groupby("cama").size().reset_index(name="total_casos")
    riesgo = pd.merge(total_por_cama, iaas_por_cama, on="cama", how="left").fillna(0)
    riesgo["proporcion"] = (riesgo["casos_iaas"] / riesgo["total_casos"]) * 100

    # Unir con coordenadas
    df_plot = pd.merge(df_coords, riesgo, on="cama", how="left").fillna(0)

    fig = px.scatter(
        df_plot,
        x="x",
        y="y",
        text="cama",
        size="proporcion",
        color="proporcion",
        color_continuous_scale="YlOrRd",
        labels={"proporcion": "% IAAS"},
        title="Mapa de riesgo por cama (IAAS)",
        height=700
    )
    fig.update_traces(textposition='top center')
    fig.update_layout(xaxis_visible=False, yaxis_visible=False, coloraxis_colorbar=dict(title="% IAAS"))

    st.plotly_chart(fig, use_container_width=True)

# ----------- MÓDULO: VIGILANCIA ACTIVA -----------
def modulo_vigilancia():
    st.button("⬅️ Regresar al menú", on_click=regresar)

    mostrar_encabezado()
    st.markdown("<h2 style='text-align:center;'>Monitoreo de IAAS - REDIAAS</h2>", unsafe_allow_html=True)
    st.markdown("---")

    st.sidebar.header("🔹 Módulos")

    # Menú de sectores
    planos = [f.replace(".png", "") for f in sorted(os.listdir("data/planos"), reverse=True) if f.endswith(".png")]
    sector = st.sidebar.selectbox("Selecciona el sector del hospital:", planos)

    # Checkboxes
    curva_iaas = st.sidebar.checkbox("Mostrar curva epidémica IAAS")
    curva_inoso = st.sidebar.checkbox("Mostrar curva de captura INOSO")
    laboratorio = st.sidebar.checkbox("Mostrar resultados de laboratorio")

    # Mapa por sector
    st.subheader("Mapeo de camas")
    st.image(f"data/planos/{sector}.png", use_container_width=True)
    st.markdown("---")

    if curva_iaas:
        st.subheader("Curva epidémica de IAAS por sector")
        archivo = st.file_uploader("Sube el archivo de IAAS (.csv o .dta)", type=["csv", "dta"], key="iaas")
        if archivo:
            if archivo.name.endswith(".csv"):
                df = pd.read_csv(archivo, parse_dates=["fec_evento"])
            else:
                df, _ = pyreadstat.read_dta(archivo)
                df["fec_evento"] = pd.to_datetime(df["fec_evento"], errors='coerce')

            if {"fec_evento", "sector", "iaas_sino"}.issubset(df.columns):
                df_iaas = df[df["iaas_sino"] == 1].copy()
                df_iaas["semana_epi"] = df_iaas["fec_evento"].dt.to_period("W").apply(lambda r: r.start_time)
                curva = df_iaas.groupby(["semana_epi", "sector"]).size().reset_index(name="casos")

                fig = px.line(curva, x="semana_epi", y="casos", color="sector", markers=True,
                              labels={"semana_epi": "Semana", "casos": "Casos de IAAS"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("El archivo debe contener: fec_evento, sector, iaas_sino")

    if curva_inoso:
        st.subheader("Curva de captura de registros en INOSO")
        st.info("Próximamente...")

    if laboratorio:
        st.subheader("Resultados de laboratorio")
        st.info("Próximamente...")

# ----------- FUNCIÓN DE RETORNO AL MENÚ -----------
def regresar():
    st.session_state.pantalla = "inicio"

# ----------- CONTROL DE FLUJO -----------
if "pantalla" not in st.session_state:
    st.session_state.pantalla = "inicio"

if st.session_state.pantalla == "inicio":
    menu_principal()
elif st.session_state.pantalla == "riesgos":
    modulo_riesgos_iaas()
elif st.session_state.pantalla == "vigilancia":
    modulo_vigilancia()
