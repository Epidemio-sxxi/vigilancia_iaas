# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from typing import Optional


# ---------------- Configuración global ----------------
st.set_page_config(layout="wide", page_title="Monitoreo de IAAS - REDIAAS")


# ---------------- Encabezado institucional ----------------
col1, col2, col3 = st.columns([1, 6, 1])
with col1:
st.image(
"https://raw.githubusercontent.com/Epidemio-sxxi/vigilancia_iaas/main/assets/imss_logo.png",
width=90,
)
with col2:
st.markdown(
"""
<h4 style='text-align: center;'>UMAE Hospital de Especialidades CMN SXXI</h4>
<h5 style='text-align: center;'>División de Epidemiología</h5>
<h2 style='text-align: center;'>Monitoreo de IAAS - REDIAAS</h2>
""",
unsafe_allow_html=True,
)
with col3:
st.image(
"https://raw.githubusercontent.com/Epidemio-sxxi/vigilancia_iaas/main/assets/residencia_epi_logo.png",
width=90,
)


# ======================================================
# Conexión a Google Sheets (robusta)
# ======================================================
SHEET_ID = st.secrets.get(
"sheet_id",
os.environ.get("REDIAAS_SHEET_ID", "1dXRRepFI6l3t6kW6pZ3BJo1G63EESINCUOd6L98V9E0"),
)


GS_READY = False
_gs_err: Optional[str] = None


# Intento 1: gspread + google.oauth2 (recomendado)
try:
import gspread
from google.oauth2.service_account import Credentials as GA_Credentials


SCOPE = [
"https://www.googleapis.com/auth/spreadsheets.readonly",
"https://www.googleapis.com/auth/drive.readonly",
]


def _gc_client():
creds_dict = st.secrets.get("gcp_service_account")
if not creds_dict:
raise RuntimeError("Falta st.secrets['gcp_service_account']")
creds = GA_Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
return gspread.authorize(creds)

GS_READY = True
def _gc_client():
creds_dict = st.secrets.get("gcp_service_account")
if not creds_dict:
raise RuntimeError("Falta st.secrets['gcp_service_account']")
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
return gspread.authorize(creds)


GS_READY = True
except Exception as e2:
_gs_err = f"OAuth error: {e1} | {e2}"
GS_READY = False




@st.cache_data(ttl=60, show_spinner=False)
def _leer_tab(sheet_id: str, tab_name: str) -> pd.DataFrame:
"""Lee una pestaña de Google Sheets y normaliza columnas/fechas."""
gc = _gc_client()
sh = gc.open_by_key(sheet_id)
ws = sh.worksheet(tab_name)
data = ws.get_all_records()
df = pd.DataFrame(data)
if df.empty:
return df


# Normalización de nombres de columnas
df.columns = [str(c).strip() for c in df.columns]


# Parseo flexible de fechas comunes del tablero
for c in ["fecha_reporte", "fec_ingreso", "fec_egreso", "fec_inicio_sintomas", "fec_toma_muestra"]:
if c in df.columns:
df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True, infer_datetime_format=True)


return df




def get_vigilancia() -> pd.DataFrame:
# Nota: la pestaña puede ser "Vigilancia" (según tu GS). Ajusta aquí si cambia.
return _leer_tab(SHEET_ID, "Vigilancia")




def get_historico() -> pd.DataFrame:
return _leer_tab(SHEET_ID, "Histórico")



def cargar_datos():
df_coords = pd.read_csv("plantilla_coordenadas_camas.csv")
df_iaas = pd.read_csv("rediaas.csv")
return df_coords, df_iaas


df_coords, df_iaas = cargar_datos()


df_riesgo = (
df_iaas.groupby("cama")["iaas_sino"]
.agg(["sum", "count"])
.reset_index()
.rename(columns={"sum": "casos_iaas", "count": "total_pacientes"})
)
df_riesgo["porcentaje_iaas"] = 100 * df_riesgo["casos_iaas"] / df_riesgo["total_pacientes"]
df_final = pd.merge(df_coords, df_riesgo[["cama", "porcentaje_iaas"]], on="cama", how="left")
df_final["porcentaje_iaas"] = df_final["porcentaje_iaas"].fillna(0)


orden_pisos = [
"5B Norte",
"5B Sur",
"4B Norte",
"4B Sur",
"3B Norte",
"3B Sur",
"2B Norte",
"2B Sur",
"UCI",
"UTR",
"TMO",
"4A",
"3A",
"2A",
"1A",
]
df_final["piso"] = pd.Categorical(df_final["piso"], categories=orden_pisos, ordered=True)


piso_sel = st.selectbox("Selecciona el piso a visualizar:", options=df_final["piso"].dropna().unique())
df_piso = df_final[df_final["piso"] == piso_sel].copy()
df_piso["porcentaje_iaas_str"] = df_piso["porcentaje_iaas"].map("{:.2f}%".format)


fig = px.scatter(
df_piso,
x="coord_x",
y="coord_y",
color="porcentaje_iaas",
color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
range_color=(0, 100),
text="cama",
labels={"coord_x": "Coordenada X", "coord_y": "Coordenada Y", "porcentaje_iaas": "% IAAS"},
hover_data={"cama": True, "porcentaje_iaas_str": True, "porcentaje_iaas": False},
height=650,
)
fig.update_traces(marker=dict(size=25), textposition="top center")
fig.update_layout(title=f"🛏️ Mapa de Riesgo – Piso {piso_sel}", title_font=dict(size=16), yaxis_autorange="reversed")


st.plotly_chart(fig, use_container_width=True)
st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

# ======================================================
st.info("Histórico vacío o sin 'fecha_reporte'.")
else:
tmp = df_hist.copy()
tmp["es_paciente"] = _es_paciente(tmp)
tmp["iaas_num"] = _iaas_num(tmp)


prev = (
tmp.groupby("fecha_reporte")
.agg(total_hosp=("es_paciente", "sum"), iaas_activos=("iaas_num", "sum"))
.assign(prevalencia=lambda d: d["iaas_activos"] / d["total_hosp"].replace(0, pd.NA))
)
st.line_chart(prev[["prevalencia"]].dropna())
st.caption("Prevalencia diaria (IAAS activos / hospitalizados).")
except Exception as e:
st.error(f"No se pudo leer 'Histórico': {e}")


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
if not GS_READY:
st.warning("Conecta Google Sheets (gspread + credenciales) para mostrar el censo en vivo.")
else:
try:
df_vivo = get_vigilancia()
if df_vivo.empty:
st.info("No hay datos en la pestaña 'Vigilancia'.")
else:
df_censo = df_vivo[_es_paciente(df_vivo)].copy()
c1, c2, c3 = st.columns(3)
c1.metric("Pacientes activos", len(df_censo))
if "iaas_sino" in df_censo.columns:
c2.metric("IAAS activos", int(_iaas_num(df_censo).sum()))
if "servicio" in df_censo.columns and not df_censo.empty:
top_srv = (
df_censo.groupby("servicio")["servicio"].count().sort_values(ascending=False).head(5)
)
c3.write("Servicios con más pacientes (Top 5):")
c3.write(top_srv)
st.dataframe(df_censo, use_container_width=True)
except Exception as e:
st.error(f"No se pudo leer 'Vigilancia': {e}")



# ---------------- Menú principal ----------------
if "menu" not in st.session_state:
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
