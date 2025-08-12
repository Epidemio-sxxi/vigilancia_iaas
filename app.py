import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ====== CONFIG GLOBAL ======
st.set_page_config(layout="wide", page_title="Monitoreo IAAS - REDIAAS")

# ====== CONEXIÓN GOOGLE SHEETS ======
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_ID = "1dXRRepFI6l3t6kW6pZ3BJo1G63EESINCUOd6L98V9E0"  # <-- tu archivo

def _gc_client():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], SCOPE
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=60, show_spinner=False)
def leer_tab(sheet_id: str, tab_name: str) -> pd.DataFrame:
    gc = _gc_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(tab_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    # normaliza headers
    df.columns = [str(c).strip() for c in df.columns]
    # parsea fechas típicas si existen
    for c in ["fecha_reporte", "fec_ingreso", "fec_egreso"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def get_vigilancia() -> pd.DataFrame:
    return leer_tab(SHEET_ID, "Vigilancia")  # tu pestaña operativa

def get_historico() -> pd.DataFrame:
    return leer_tab(SHEET_ID, "Histórico")   # tu serie temporal

# ====== ENCABEZADO ======
col1, col2, col3 = st.columns([1, 6, 1])
with col1:
    st.image("https://raw.githubusercontent.com/Epidemio-sxxi/vigilancia_iaas/main/assets/imss_logo.png", width=90)
with col2:
    st.markdown("""
        <h4 style='text-align: center;'>UMAE Hospital de Especialidades CMN SXXI</h4>
        <h5 style='text-align: center;'>División de Epidemiología</h5>
        <h2 style='text-align: center;'>Monitoreo de IAAS - REDIAAS</h2>
    """, unsafe_allow_html=True)
with col3:
    st.image("https://raw.githubusercontent.com/Epidemio-sxxi/vigilancia_iaas/main/assets/residencia_epi_logo.png", width=90)

# ====== UTILIDADES ======
def _es_paciente(df: pd.DataFrame) -> pd.Series:
    if "status_paciente" in df.columns:
        return df["status_paciente"].astype(str).str.lower() != "sin paciente"
    # si no existe la columna, asumimos que todas las filas son pacientes
    return pd.Series([True]*len(df), index=df.index)

def _iaas_num(df: pd.DataFrame, col="iaas_sino") -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series([0]*len(df), index=df.index)

# ====== MÓDULO: Riesgo IAAS por cama ======
def modulo_riesgo():
    st.subheader("🛏️ Mapa de Riesgo de IAAS por Cama")

    # Selector de fuente para el cálculo
    fuente = st.radio(
        "Fuente de cálculo:",
        ("Vigilancia (en vivo)", "Histórico (rango de fechas)"),
        horizontal=True
    )

    # Coordenadas de camas (puedes seguir usando tu CSV local)
    @st.cache_data
    def cargar_coords():
        return pd.read_csv("plantilla_coordenadas_camas.csv")
    df_coords = cargar_coords()

    if fuente == "Vigilancia (en vivo)":
        df_vivo = get_vigilancia()
        if df_vivo.empty:
            st.info("No hay datos en la pestaña 'Vigilancia'.")
            return

        df_censo = df_vivo[_es_paciente(df_vivo)].copy()
        if "cama" not in df_censo.columns:
            st.warning("No se encuentra la columna 'cama' en Vigilancia.")
            return

        # Cálculo simple en vivo: proporción IAAS por cama con lo capturado hoy
        df_censo["iaas_num"] = _iaas_num(df_censo)
        riesgo = (df_censo.groupby("cama")["iaas_num"]
                  .agg(casos_iaas="sum", total="count")
                  .reset_index())
        riesgo["porcentaje_iaas"] = 100 * riesgo["casos_iaas"] / riesgo["total"]

    else:
        # Histórico: rango de fechas
        df_hist = get_historico()
        if df_hist.empty or "fecha_reporte" not in df_hist.columns:
            st.warning("Histórico vacío o sin 'fecha_reporte'.")
            return

        c1, c2 = st.columns(2)
        with c1:
            f_ini = st.date_input("Fecha inicial", value=df_hist["fecha_reporte"].min().date())
        with c2:
            f_fin = st.date_input("Fecha final", value=df_hist["fecha_reporte"].max().date())

        mask = (df_hist["fecha_reporte"]>=pd.to_datetime(f_ini)) & (df_hist["fecha_reporte"]<=pd.to_datetime(f_fin))
        sub = df_hist[mask].copy()
        sub = sub[_es_paciente(sub)]
        if "cama" not in sub.columns:
            st.warning("No se encuentra la columna 'cama' en Histórico.")
            return

        sub["iaas_num"] = _iaas_num(sub)
        riesgo = (sub.groupby("cama")["iaas_num"]
                  .agg(casos_iaas="sum", total="count")
                  .reset_index())
        riesgo["porcentaje_iaas"] = 100 * riesgo["casos_iaas"] / riesgo["total"]

    # Merge con coordenadas y construcción de visual
    df_final = pd.merge(df_coords, riesgo[["cama","porcentaje_iaas"]], on="cama", how="left")
    df_final["porcentaje_iaas"] = df_final["porcentaje_iaas"].fillna(0)

    # Orden de pisos (ajusta a tus valores reales)
    orden_pisos = ["5B Norte","5B Sur","4B Norte","4B Sur","3B Norte","3B Sur","2B Norte","2B Sur",
                   "UCI","UTR","TMO","4A","3A","2A","1A"]
    if "piso" in df_final.columns:
        df_final["piso"] = pd.Categorical(df_final["piso"], categories=orden_pisos, ordered=True)
        pisos = df_final["piso"].dropna().unique()
    else:
        pisos = []

    if len(pisos) == 0:
        st.warning("No hay columna 'piso' en plantilla_coordenadas_camas.csv o está vacía.")
        return

    piso_sel = st.selectbox("Selecciona el piso a visualizar:", options=pisos)
    df_piso = df_final[df_final["piso"] == piso_sel].copy()
    df_piso["porcentaje_iaas_str"] = df_piso["porcentaje_iaas"].map("{:.2f}%".format)

    fig = px.scatter(
        df_piso, x="coord_x", y="coord_y", color="porcentaje_iaas",
        color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
        range_color=(0, 100), text="cama",
        labels={"coord_x": "Coordenada X", "coord_y": "Coordenada Y", "porcentaje_iaas": "% IAAS"},
        hover_data={"cama": True, "porcentaje_iaas_str": True, "porcentaje_iaas": False},
        height=650
    )
    fig.update_traces(marker=dict(size=25), textposition="top center")
    fig.update_layout(title=f"🛏️ Mapa de Riesgo – Piso {piso_sel}", title_font=dict(size=16), yaxis_autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

# ====== MÓDULO: Vigilancia Activa (con censo en vivo) ======
def modulo_vigilancia():
    st.subheader("🔍 Vigilancia Activa por Sector Hospitalario")

    # selector de planos (tu lógica actual)
    planos = [f.replace(".png", "") for f in sorted(os.listdir("data/planos")) if f.endswith(".png")]
    st.markdown("##### Selecciona el sector del hospital:")
    col_sel, _ = st.columns([1.2, 3])
    with col_sel:
        plano_sel = st.selectbox("", options=planos, label_visibility="collapsed")
    imagen_path = os.path.join("data/planos", f"{plano_sel}.png")

    col1, col2 = st.columns([1, 4])

    with col1:
        st.markdown("### 🧭 Módulos disponibles")
        mostrar_curva_epidemica = st.checkbox("Curva Epidémica de IAAS", value=False)
        mostrar_curva_captura = st.checkbox("Captura en INOSO", value=False)
        mostrar_laboratorio = st.checkbox("Laboratorio", value=False)
        mostrar_censo = st.checkbox("Censo nominal de casos (en vivo)", value=False)

        st.markdown("###")
        st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

    with col2:
        if os.path.exists(imagen_path):
            st.image(imagen_path, use_container_width=True, caption=f"Plano sector {plano_sel}")
        else:
            st.warning("⚠️ No se encontró el plano del sector.")

        if mostrar_curva_epidemica:
            st.subheader("📈 Curva Epidémica de IAAS")
            path_curva = "data/curva_epidemica.png"
            if os.path.exists(path_curva):
                st.image(path_curva, use_container_width=True)
            else:
                st.warning("No se encontró la imagen de la curva epidémica.")

        if mostrar_curva_captura:
            st.subheader("📊 Curva de Captura INOSO")
            path_captura = "data/curva_captura.png"
            if os.path.exists(path_captura):
                st.image(path_captura, use_container_width=True)
            else:
                st.warning("No se encontró la imagen de la curva de captura INOSO.")

        if mostrar_laboratorio:
            st.subheader("🧪 Laboratorio")
            path_lab = "data/laboratorio.png"
            if os.path.exists(path_lab):
                st.image(path_lab, use_container_width=True)
            else:
                st.warning("No se encontró la imagen del laboratorio.")

        if mostrar_censo:
            st.subheader("🗂️ Censo nominal de casos (en vivo)")
            df_vivo = get_vigilancia()
            if df_vivo.empty:
                st.info("No hay datos en 'Vigilancia'.")
            else:
                # filtro básico: pacientes activos
                df_censo = df_vivo[_es_paciente(df_vivo)].copy()
                # métricas rápidas
                c1, c2, c3 = st.columns(3)
                c1.metric("Pacientes activos", len(df_censo))
                if "iaas_sino" in df_censo.columns:
                    c2.metric("IAAS activos", int(_iaas_num(df_censo).sum()))
                if "servicio" in df_censo.columns:
                    top_srv = (df_censo.groupby("servicio")["servicio"].count()
                               .sort_values(ascending=False).head(5))
                    c3.write("Servicios con más pacientes (Top 5):")
                    c3.write(top_srv)

                st.dataframe(df_censo, use_container_width=True)

# ====== MENÚ PRINCIPAL ======
if 'menu' not in st.session_state:
    st.session_state.menu = None

if st.session_state.menu is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("###")
        if st.button("📊 Riesgos de IAAS por cama", use_container_width=True):
            st.session_state.menu = "riesgo"
        if st.button("🔍 Vigilancia activa", use_container_width=True):
            st.session_state.menu = "vigilancia"

elif st.session_state.menu == "riesgo":
    modulo_riesgo()

elif st.session_state.menu == "vigilancia":
    modulo_vigilancia()
