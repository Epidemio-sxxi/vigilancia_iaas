# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import unicodedata
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
#     Conexión a Google Sheets (Service Account + CSV)
# ======================================================
SHEET_ID = st.secrets.get(
    "sheet_id",
    os.environ.get("REDIAAS_SHEET_ID", "1dXRRepFI6l3t6kW6pZ3BJo1G63EESINCUOd6L98V9E0"),
)

DEFAULT_SHEET_GID_MAP = {
    "Vigilancia": st.secrets.get("gid_vigilancia", os.environ.get("REDIAAS_GID_VIGILANCIA", "0")),
    "Histórico":  st.secrets.get("gid_historico",  os.environ.get("REDIAAS_GID_HISTORICO",  "0")),
}

GS_READY = False
_gs_err: Optional[str] = None

def _get_sa_info():
    sa = st.secrets.get("gcp_service_account")
    if not sa or not isinstance(sa, dict) or not sa.get("client_email"):
        raise RuntimeError("Falta st.secrets['gcp_service_account'] (JSON del Service Account)")
    return sa

try:
    import gspread
    from google.oauth2.service_account import Credentials as GA_Credentials
    SCOPE = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    def _gc_client():
        creds_dict = _get_sa_info()
        creds = GA_Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        return gspread.authorize(creds)
    _ = st.secrets.get("gcp_service_account")
    GS_READY = True
except Exception as e1:
    _gs_err = str(e1)
    try:
        import gspread  # type: ignore
        from oauth2client.service_account import ServiceAccountCredentials  # type: ignore
        SCOPE = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        def _gc_client():
            creds_dict = _get_sa_info()
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            return gspread.authorize(creds)
        _ = st.secrets.get("gcp_service_account")
        GS_READY = True
    except Exception as e2:
        _gs_err = f"OAuth error: {e1} | {e2}"
        GS_READY = False

def _leer_csv_publico(sheet_id: str, gid: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return pd.read_csv(url)

@st.cache_data(ttl=120, show_spinner=False)
def _leer_tab(sheet_id: str, tab_name: str, gid_map: dict) -> pd.DataFrame:
    if GS_READY:
        try:
            gc = _gc_client()
            sh = gc.open_by_key(sheet_id)
            ws = sh.worksheet(tab_name)
            data = ws.get_all_records()
            df = pd.DataFrame(data)
        except Exception:
            gid = str(gid_map.get(tab_name, "0"))
            df = _leer_csv_publico(sheet_id, gid)
    else:
        gid = str(gid_map.get(tab_name, "0"))
        df = _leer_csv_publico(sheet_id, gid)

    if df.empty:
        return df

    df.columns = [str(c).strip() for c in df.columns]
    for c in [
        "fecha_reporte","fec_ingreso","fec_egreso","fec_inicio_sintomas","fec_toma_muestra",
        "fecha_muestra_1","fecha_resultado_1","fecha_muestra_2","fecha_resultado_2",
        "fecha_muestra_3","fecha_resultado_3","fecha_muestra_4","fecha_resultado_4",
    ]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True, infer_datetime_format=True)
    return df

def get_vigilancia(gid_map: dict) -> pd.DataFrame:
    return _leer_tab(SHEET_ID, "Vigilancia", gid_map)

def get_historico(gid_map: dict) -> pd.DataFrame:
    return _leer_tab(SHEET_ID, "Histórico", gid_map)

# ======================================================
#        Módulo: Riesgo IAAS por cama (igual)
# ======================================================
def modulo_riesgo():
    st.subheader("🛏️ Mapa de Riesgo de IAAS por Cama")

    @st.cache_data
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
        "5B Norte","5B Sur","4B Norte","4B Sur","3B Norte","3B Sur",
        "2B Norte","2B Sur","UCI","UTR","TMO","4A","3A","2A","1A",
    ]
    df_final["piso"] = pd.Categorical(df_final["piso"], categories=orden_pisos, ordered=True)

    piso_sel = st.selectbox("Selecciona el piso a visualizar:", options=df_final["piso"].dropna().unique())
    df_piso = df_final[df_final["piso"] == piso_sel].copy()
    df_piso["porcentaje_iaas_str"] = df_piso["porcentaje_iaas"].map("{:.2f}%".format)

    fig = px.scatter(
        df_piso, x="coord_x", y="coord_y", color="porcentaje_iaas",
        color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
        range_color=(0, 100), text="cama",
        labels={"coord_x": "Coordenada X","coord_y":"Coordenada Y","porcentaje_iaas":"% IAAS"},
        hover_data={"cama": True, "porcentaje_iaas_str": True, "porcentaje_iaas": False},
        height=650,
    )
    fig.update_traces(marker=dict(size=25), textposition="top center")
    fig.update_layout(title=f"🛏️ Mapa de Riesgo – Piso {piso_sel}", title_font=dict(size=16), yaxis_autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

# ======================================================
#        Módulo: Vigilancia Activa
# ======================================================
def _es_paciente(df: pd.DataFrame) -> pd.Series:
    if "status_paciente" in df.columns:
        return df["status_paciente"].astype(str).str.lower() != "sin paciente"
    return pd.Series([True] * len(df), index=df.index)

def _strip_accents(text: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch))

def _es_si(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    s = _strip_accents(s)
    return s in {"si", "s", "true", "1"}

def _iaas_cols(df: pd.DataFrame):
    wanted = {"iaas_1","iaas_2","iaas_3","iaas_4"}
    return [c for c in df.columns if c.lower() in wanted]

def contar_iaas_totales(df: pd.DataFrame) -> int:
    cols = _iaas_cols(df)
    if not cols:
        return 0
    return int(df[cols].applymap(_es_si).sum(axis=1).sum())

def contar_pacientes_con_iaas(df: pd.DataFrame) -> int:
    cols = _iaas_cols(df)
    if not cols:
        return 0
    return int(df[cols].applymap(_es_si).any(axis=1).sum())

def contar_cultivos_si(df: pd.DataFrame) -> int:
    cols = [c for c in ["cultivo_1","cultivo_2","cultivo_3","cultivo_4"] if c in df.columns]
    if not cols:
        return 0
    return int(df[cols
