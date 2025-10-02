# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os
import unicodedata
from datetime import datetime
from typing import Optional, List

# ---------------- Configuración global ----------------
st.set_page_config(layout="wide", page_title="Monitoreo de IAAS - REDIAAS")

# ====== Tema oscuro forzado (UI + Plotly) ======
px.defaults.template = "plotly_dark"
pio.templates.default = "plotly_dark"

def _darken_plot(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

# ====== CSS oscuro + FIX del header que tapaba el título ======
st.markdown("""
<style>
:root { color-scheme: dark; }

/* Fondo global negro (excepto header) */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
  background-color: #000 !important;
  color: #eaeaea !important;
}

/* Header fijo transparente, sin sombras ni bordes */
[data-testid="stHeader"]{
  background: transparent !important;
  box-shadow: none !important;
  backdrop-filter: none !important;
  border-bottom: 0 !important;
}

/* Espacio extra bajo el header para que no se encime el contenido */
.block-container,
[data-testid="stAppViewContainer"] .main .block-container{
  padding-top: 4.75rem !important;
}

[data-testid="stAppViewContainer"] * { color: #eaeaea; }
h1, h2, h3, h4, h5, h6 { color: #f0f0f0 !important; }
a { color: #d0e3ff !important; }

/* Controles */
div.stButton > button {
  background: #111 !important; color: #eaeaea !important;
  border: 1px solid #333 !important; box-shadow: none !important;
}
div.stCheckbox > label, label { color: #eaeaea !important; }
div[data-baseweb="select"] * { color: #eaeaea !important; }
div[data-baseweb="input"] { background: #111 !important; }
div[data-testid="stSelectbox"] div[role="combobox"] { background: #111 !important; }

/* Tablas / DataFrame */
div[data-testid="stDataFrame"] { background-color: #0a0a0a !important; }
thead tr th { background: #0f0f0f !important; color: #eaeaea !important; }
tbody tr td { background: #0a0a0a !important; color: #eaeaea !important; }
hr { border-color: #2a2a2a !important; }

/* Alertas */
[data-testid="stNotification"], .stAlert { background: #121212 !important; color: #eaeaea !important; }

/* Extra en móviles */
@media (max-width: 768px){
  .block-container,
  [data-testid="stAppViewContainer"] .main .block-container{
    padding-top: 5.5rem !important;
  }
}
</style>
""", unsafe_allow_html=True)

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
#     (sin UI; se resuelve en automático)
# ======================================================
SHEET_ID = st.secrets.get(
    "sheet_id",
    os.environ.get("REDIAAS_SHEET_ID", "1dXRRepFI6l3t6kW6pZ3BJo1G63EESINCUOd6L98V9E0"),
)

# Nota: la pestaña operativa del día se llama **"Viglancia"** (sin segunda i).
# Dejamos compatibilidad con "Vigilancia" por si en algún entorno existe así.
DEFAULT_SHEET_GID_MAP = {
    "Viglancia": st.secrets.get("gid_viglancia", os.environ.get("REDIAAS_GID_VIGLANCIA", "0")),
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


@st.cache_data(ttl=10, show_spinner=False)
def _leer_tab(sheet_id: str, tab_name: str, gid_map: dict) -> pd.DataFrame:
    """Lee una pestaña por nombre; si falla, intenta por CSV usando el gid del nombre dado."""
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

    # Limpieza de encabezados
    df.columns = [str(c).strip() for c in df.columns]

    # Parseo de fechas (compat. pandas 2.x)
    fecha_cols_basicas: List[str] = [
        "fecha_reporte", "fec_ingreso", "fec_egreso", "fec_inicio_sintomas", "fec_toma_muestra",
        "fecha_muestra_1", "fecha_resultado_1", "fecha_muestra_2", "fecha_resultado_2",
        "fecha_muestra_3", "fecha_resultado_3", "fecha_muestra_4", "fecha_resultado_4",
    ]
    # Nuevas columnas múltiples: fec_inicio_iaas_1..4 y fec_captura_1..4
    fecha_cols_nuevas = [f"fec_inicio_iaas_{i}" for i in range(1,5)] + [f"fec_captura_{i}" for i in range(1,5)]

    for c in fecha_cols_basicas + fecha_cols_nuevas:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    return df


def get_vigilancia(gid_map: dict) -> pd.DataFrame:
    """Devuelve la hoja operativa del día.
    Preferimos "Viglancia"; si no existe, probamos "Vigilancia"; si ninguna, DataFrame vacío.
    """
    df = _leer_tab(SHEET_ID, "Viglancia", gid_map)  # Intento 1
    if not df.empty:
        return df
    df = _leer_tab(SHEET_ID, "Vigilancia", gid_map)  # Intento 2
    return df


def get_historico(gid_map: dict) -> pd.DataFrame:
    return _leer_tab(SHEET_ID, "Histórico", gid_map)


# ======================================================
#        Utilidades de negocio
# ======================================================
ORDER_PISOS = [
    "5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur",
    "2B Norte", "2B Sur", "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A",
]


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _norm_piso(s):
    return _strip_accents(str(s)).strip().upper()


def _es_paciente(df: pd.DataFrame) -> pd.Series:
    if "status_paciente" in df.columns:
        return df["status_paciente"].astype(str).str.lower() != "sin paciente"
    return pd.Series([True] * len(df), index=df.index)


def _es_si(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    s = _strip_accents(s)
    return s in {"si", "s", "true", "1"}


def _iaas_cols(df: pd.DataFrame):
    wanted = {"iaas_1", "iaas_2", "iaas_3", "iaas_4"}
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
    cols = [c for c in ["cultivo_1", "cultivo_2", "cultivo_3", "cultivo_4"] if c in df.columns]
    if not cols:
        return 0
    return int(df[cols].applymap(_es_si).sum(axis=1).sum())


def contar_microorganismos_si(df: pd.DataFrame) -> int:
    piezas = []
    for i in [1, 2, 3, 4]:
        c_cult = f"cultivo_{i}"
        c_germ = f"germen_{i}"
        if c_cult in df.columns and c_germ in df.columns:
            mask = df[c_cult].map(_es_si)
            piezas.append(df.loc[mask, c_germ].astype(str).str.strip())
    if not piezas:
        return 0
    germs = pd.concat(piezas, ignore_index=True).replace({"": pd.NA, "nan": pd.NA})
    return int(germs.dropna().nunique())


def lab_desde_vigilancia(df_src: pd.DataFrame) -> pd.DataFrame:
    id_cols = [
        "piso", "servicio", "cama", "nss", "ap_paterno", "ap_materno", "nombre", "sexo", "edad", "fec_ingreso"
    ]
    id_cols = [c for c in id_cols if c in df_src.columns]

    frames = []
    for i in [1, 2, 3, 4]:
        cols_i = {
            "cultivo": f"cultivo_{i}",
            "fecha_muestra": f"fecha_muestra_{i}",
            "fecha_resultado": f"fecha_resultado_{i}",
            "tipo_muestra": f"tipo_muestra_{i}",
            "tipo_resultado": f"tipo_resultado_{i}",
            "germen": f"germen_{i}",
            "resistencia": f"resistencia_{i}",
        }
        use_cols = [c for c in cols_i.values() if c in df_src.columns]
        if not use_cols:
            continue
        tmp = df_src[id_cols + use_cols].copy()
        rename_map = {v: k for k, v in cols_i.items() if v in tmp.columns}
        tmp = tmp.rename(columns=rename_map)
        for c in ["fecha_muestra", "fecha_resultado", "fec_ingreso"]:
            if c in tmp.columns:
                tmp[c] = pd.to_datetime(tmp[c], errors="coerce", dayfirst=True)
        has_info = False
        for c in ["germen", "tipo_resultado", "tipo_muestra", "cultivo"]:
            if c in tmp.columns:
                s = tmp[c].astype(str).str.strip().ne("")
                has_info = s if has_info is False else (has_info | s)
        if isinstance(has_info, pd.Series):
            tmp = tmp[has_info]
        tmp["no_cultivo"] = i
        frames.append(tmp)

    if not frames:
        return pd.DataFrame()

    df_long = pd.concat(frames, ignore_index=True)
    ordered = [c for c in [
        "no_cultivo", "fecha_muestra", "fecha_resultado", "tipo_muestra", "tipo_resultado", "germen", "resistencia", "cultivo"
    ] if c in df_long.columns]
    df_long = df_long[id_cols + ordered]
    return df_long


def filtra_por_piso(df: pd.DataFrame, seleccion: Optional[str]) -> pd.DataFrame:
    if df is None or df.empty or not seleccion:
        return df
    if _norm_piso(seleccion) in {"UMAE COMPLETA", "UMAE", "TODOS", "ALL"}:
        return df
    if "piso" not in df.columns:
        st.error("La hoja no tiene la columna 'piso'. Verifica tu Google Sheet.")
        return df
    df2 = df.copy()
    df2["__piso_norm"] = df2["piso"].map(_norm_piso)
    return df2[df2["__piso_norm"] == _norm_piso(seleccion)].drop(columns="__piso_norm")


def stat_card(value: int, label: str, color_bg: str, icon: str):
    html = f"""
    <div style="background:{color_bg}; border-radius:14px; padding:16px 18px; color:white;
                box-shadow:0 6px 18px rgba(0,0,0,.20);">
        <div style="font-size:34px; font-weight:800; line-height:1">{value:,}</div>
        <div style="display:flex; align-items:center; gap:10px; margin-top:6px;">
            <span style="font-size:22px" aria-hidden="true">{icon}</span>
            <span style="font-size:15px; opacity:.95">{label}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ======================================================
#        Módulo: Riesgo IAAS por cama (INSERTADO)
#        (tomado del código 1, sin cambios en lógica)
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
        "5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur",
        "2B Norte", "2B Sur", "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A",
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
#                     Módulo: Vigilancia
# ======================================================

def modulo_vigilancia():
    st.subheader("🔍 Vigilancia Activa por Sector Hospitalario")

    gid_map = DEFAULT_SHEET_GID_MAP  # sin UI

    # --------- Fila 1: Selector (angosto) y, si aplica, plano a la derecha ---------
    st.markdown("#### Selecciona el sector del hospital:")

    # Cargamos una vez para opciones del combo
    try:
        df_vig_opts = get_vigilancia(gid_map)
        opciones_raw = (
            sorted(df_vig_opts["piso"].dropna().astype(str).map(str.strip).unique())
            if "piso" in df_vig_opts.columns else []
        )
    except Exception:
        df_vig_opts = pd.DataFrame()
        opciones_raw = []

    # Ordenar con la lista de referencia (mantiene extras alfabéticos al final)
    def ordena_pisos(opts):
        norm_map = {o: _norm_piso(o) for o in opts}
        base = [p for p in ORDER_PISOS if any(norm_map[o] == _norm_piso(p) for o in opts)]
        base_original = []
        for p in base:
            for o in opts:
                if norm_map[o] == _norm_piso(p):
                    base_original.append(o)
                    break
        extra = [o for o in opts if _norm_piso(o) not in {_norm_piso(p) for p in ORDER_PISOS}]
        return base_original + sorted(extra)

    pisos_ordenados = ordena_pisos(opciones_raw)
    opciones_sector = ["UMAE completa"] + pisos_ordenados

    # Renderizamos selector en una columna angosta; si hay plano, lo mostramos a la derecha
    col_sel_only = st.columns([1.1])[0]
    with col_sel_only:
        plano_sel = st.selectbox("", options=opciones_sector, index=0, label_visibility="collapsed", key="sel_piso")

    # --------- Preparamos data filtrada según selección ---------
    df_vig = get_vigilancia(gid_map)
    df_vig = df_vig.copy()
    df_vig = filtra_por_piso(df_vig, plano_sel)
    df_censo = df_vig[_es_paciente(df_vig)].copy()

    # Para la vista con plano, volvemos a mostrar el PNG en una fila separada SOLO si no es UMAE completa
    if _norm_piso(plano_sel) not in {"UMAE COMPLETA", "UMAE", "TODOS", "ALL"}:
        col_sel, col_plano = st.columns([1.1, 3.9])
        with col_sel:
            st.empty()  # espacio para que el plano se alinee arriba
        with col_plano:
            imagen_path = os.path.join("data/planos", f"{plano_sel}.png")
            if os.path.exists(imagen_path):
                st.image(imagen_path, use_container_width=True, caption=f"Plano sector {plano_sel}")
            else:
                st.caption("No hay imagen para este sector. (Coloca un PNG en data/planos con el nombre del piso).")

    # --------- Fila 2: Izquierda (módulos) + Derecha (info/servicios/contenidos)
    col_left, col_right = st.columns([1.1, 3.9])

    with col_left:
        st.markdown("### 🏥 Módulos disponibles")
        mostrar_curva_epidemica = st.checkbox("Curva Epidémica de IAAS", value=False, key="cb_curva")
        mostrar_curva_captura   = st.checkbox("Captura en INOSO", value=False, key="cb_inoso")
        mostrar_reporte_cult    = st.checkbox("Reporte de cultivos", value=False, key="cb_cult")
        mostrar_censo           = st.checkbox("Censo nominal", value=False, key="cb_censo")
        st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

    with col_right:
        # ===== Información general (siempre desde Viglancia/Vigilancia) =====
        st.markdown("### Información general")
        total_pac    = int(len(df_censo))
        iaas_total   = contar_iaas_totales(df_censo)
        pacs_iaas    = contar_pacientes_con_iaas(df_censo)
        cultivos_cnt = contar_cultivos_si(df_vig)
        micro_cnt    = contar_microorganismos_si(df_vig)

        cA, cB, cB2, cC, cD = st.columns(5)
        with cA:  stat_card(total_pac, "Total de pacientes",   "#6C63FF", "🛏️")
        with cB:  stat_card(iaas_total, "IAAS",                 "#2ECC71", "🩺")
        with cB2: stat_card(pacs_iaas,  "Pacientes con IAAS",   "#E74C3C", "👤")
        with cC:  stat_card(cultivos_cnt, "Cultivos",           "#1E90FF", "🧪")
        with cD:  stat_card(micro_cnt,    "Microorganismos",    "#F39C12", "🔬")

        st.markdown("---")

        # --- Curva epidémica (fec_inicio_iaas_1..4) usando Histórico ∪ Viglancia ---
        if mostrar_curva_epidemica:
            st.subheader("📈 Curva Epidémica de IAAS (inicio de síntomas)")
            try:
                df_hist = get_historico(gid_map)
                df_union = pd.concat([df_hist, df_vig], ignore_index=True, sort=False)
                tmp = filtra_por_piso(df_union.copy(), plano_sel)
                if tmp.empty:
                    st.info("No hay datos para construir la curva en esta vista.")
                else:
                    id_cols = [c for c in ["nss", "cama", "ap_paterno", "ap_materno", "nombre"] if c in tmp.columns]
                    eventos = []
                    for i in range(1, 5):
                        dcol = f"fec_inicio_iaas_{i}"
                        icol = f"iaas_{i}"
                        if dcol not in tmp.columns:
                            continue
                        mask_dt = tmp[dcol].notna()
                        if icol in tmp.columns:
                            mask_iaas = tmp[icol].map(_es_si)
                            mask = mask_dt & mask_iaas
                        else:
                            mask = mask_dt
                        if mask.any():
                            cols_take = id_cols + [dcol]
                            df_i = tmp.loc[mask, cols_take].copy()
                            df_i = df_i.rename(columns={dcol: "fec_inicio_iaas"})
                            eventos.append(df_i)
                    if not eventos:
                        st.info("No hay fechas de inicio de IAAS registradas.")
                    else:
                        ev = pd.concat(eventos, ignore_index=True)

                        # Agrupar por día (no por fecha-hora) y formatear etiqueta DD/MM/AAAA
                        serie = (
                            ev.groupby(ev["fec_inicio_iaas"].dt.date)
                              .size().reset_index(name="iaas_nuevas")
                              .rename(columns={"fec_inicio_iaas": "fecha_dia"})
                        )
                        serie["fecha_dt"] = pd.to_datetime(serie["fecha_dia"])
                        dias = st.slider("Rango de días para la curva", 14, 180, 60, key="slider_curva_inicio")
                        fmax = serie["fecha_dt"].max()
                        if pd.notna(fmax):
                            desde = fmax - pd.Timedelta(days=dias)
                            serie = serie[serie["fecha_dt"] >= desde]
                        serie["fecha_label"] = serie["fecha_dt"].dt.strftime("%d/%m/%Y")

                        fig_inc = px.bar(
                            serie, x="fecha_label", y="iaas_nuevas",
                            labels={"fecha_label": "Fecha", "iaas_nuevas": "IAAS nuevas"}
                        )
                        _darken_plot(fig_inc)
                        fig_inc.update_xaxes(type="category", tickangle=-30)
                        st.plotly_chart(fig_inc, use_container_width=True)
                        st.caption(f"Incidencia diaria por fecha de inicio – Vista: {plano_sel}.")
            except Exception as e:
                st.error(f"No se pudo calcular la curva epidémica: {e}")

        # --- Captura en INOSO por fec_captura_1..4 (usando Histórico ∪ Viglancia) ---
        if mostrar_curva_captura:
            st.subheader("📊 Captura en INOSO (por fecha de captura)")
            try:
                df_hist = get_historico(gid_map)
                df_union = pd.concat([df_hist, df_vig], ignore_index=True, sort=False)
                tmp = filtra_por_piso(df_union.copy(), plano_sel)

                if tmp.empty:
                    st.info("No hay datos para la curva de captura en esta vista.")
                else:
                    id_cols = [c for c in ["nss", "cama", "ap_paterno", "ap_materno", "nombre"] if c in tmp.columns]
                    caps = []
                    for i in range(1, 5):
                        dcol = f"fec_captura_{i}"
                        if dcol not in tmp.columns:
                            continue
                        mask = tmp[dcol].notna()
                        if mask.any():
                            cols_take = id_cols + [dcol]
                            df_i = tmp.loc[mask, cols_take].copy()
                            df_i = df_i.rename(columns={dcol: "fec_captura"})
                            caps.append(df_i)

                    if not caps:
                        st.info("No hay fechas de captura registradas (fec_captura_1..4).")
                    else:
                        cap = pd.concat(caps, ignore_index=True)

                        # Agrupar por día y formatear etiqueta DD/MM/AAAA
                        serie = (
                            cap.groupby(cap["fec_captura"].dt.date)
                               .size().reset_index(name="casos")
                               .rename(columns={"fec_captura": "fecha_dia"})
                        )
                        serie["fecha_dt"] = pd.to_datetime(serie["fecha_dia"])
                        dias = st.slider("Rango de días para captura", 14, 180, 60, key="slider_cap")
                        fmax = serie["fecha_dt"].max()
                        if pd.notna(fmax):
                            desde = fmax - pd.Timedelta(days=dias)
                            serie = serie[serie["fecha_dt"] >= desde]
                        serie["fecha_label"] = serie["fecha_dt"].dt.strftime("%d/%m/%Y")

                        fig_cap = px.bar(
                            serie, x="fecha_label", y="casos",
                            labels={"fecha_label": "Fecha", "casos": "Casos/día"}
                        )
                        _darken_plot(fig_cap)
                        fig_cap.update_xaxes(type="category", tickangle=-30)
                        st.plotly_chart(fig_cap, use_container_width=True)
                        st.caption(f"Capturas diarias en INOSO – Vista: {plano_sel}.")
            except Exception as e:
                st.error(f"No se pudo calcular la captura INOSO: {e}")

        # --- Reporte de cultivos (desde Viglancia/Vigilancia) ---
        if mostrar_reporte_cult:
            st.subheader("🧪 Reporte de cultivos")
            try:
                df_v = df_vig.copy()
                if df_v.empty:
                    st.info("'Viglancia/Vigilancia' está vacía.")
                else:
                    df_lab = lab_desde_vigilancia(df_v)
                    if "cultivo" in df_lab.columns:
                        df_lab = df_lab[df_lab["cultivo"].map(_es_si)]
                    if df_lab.empty:
                        st.info("Sin cultivos positivos en esta vista.")
                    else:
                        # Filtro temporal
                        fecha_ref = "fecha_muestra" if "fecha_muestra" in df_lab.columns else (
                            "fecha_resultado" if "fecha_resultado" in df_lab.columns else None
                        )
                        if fecha_ref:
                            dias = st.slider("Rango de días para el reporte", 7, 120, 30, key="slider_lab")
                            fecha_max = df_lab[fecha_ref].max()
                            if pd.notna(fecha_max):
                                desde = fecha_max - pd.Timedelta(days=dias)
                                df_lab = df_lab[df_lab[fecha_ref] >= desde]

                        # Treemap de microorganismos (+ regla "Pendiente")
                        if "germen" in df_lab.columns:
                            df_lab["germen_plot"] = (
                                df_lab["germen"].astype(str).str.strip()
                                .replace({"nan": pd.NA, "": pd.NA})
                            )
                        else:
                            df_lab["germen_plot"] = pd.NA

                        if "fecha_muestra" in df_lab.columns:
                            mask_pend = df_lab["germen_plot"].isna() & df_lab["fecha_muestra"].notna()
                            df_lab.loc[mask_pend, "germen_plot"] = "Pendiente"

                        top = df_lab["germen_plot"].dropna().value_counts().reset_index()
                        top.columns = ["Microorganismo", "Casos"]

                        if not top.empty:
                            fig_top = px.treemap(top, path=["Microorganismo"], values="Casos")
                            _darken_plot(fig_top)
                            fig_top.update_traces(root_color="lightgrey")
                            st.plotly_chart(fig_top, use_container_width=True)

                        # Métrica y barras por tipo de muestra
                        st.metric(f"Registros de laboratorio ({plano_sel})", len(df_lab))
                        if "tipo_muestra" in df_lab.columns:
                            por_muestra = (
                                df_lab["tipo_muestra"].astype(str).str.strip()
                                .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                .value_counts().reset_index()
                            )
                            por_muestra.columns = ["Tipo de muestra", "Registros"]
                            if not por_muestra.empty:
                                fig_m = px.bar(por_muestra, x="Tipo de muestra", y="Registros")
                                _darken_plot(fig_m)
                                fig_m.update_layout(xaxis_tickangle=-30)
                                st.plotly_chart(fig_m, use_container_width=True)

                        # Tabla detallada
                        drop_cols = {"Unnamed: 0", "index", "no_cultivo", "cultivo", "fec_ingreso"}
                        cols = [c for c in df_lab.columns if c not in drop_cols]
                        st.dataframe(df_lab[cols], use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo generar el reporte de cultivos: {e}")

        # --- Censo nominal (desde Viglancia/Vigilancia) ---
        if mostrar_censo:
            st.subheader("📒 Censo nominal")
            try:
                df_v = df_censo.copy()
                if df_v.empty:
                    st.info("Sin pacientes en esta vista.")
                else:
                    cols_iaas = _iaas_cols(df_v)
                    if cols_iaas:
                        df_v = df_v[df_v[cols_iaas].applymap(_es_si).any(axis=1)]
                    keep = [
                        "cama", "status_paciente", "servicio", "fec_ingreso", "ap_paterno", "ap_materno", "nombre", "nss",
                        "ag_med", "edad", "sexo", "iaas_1", "iaas_2", "iaas_3", "iaas_4",
                        "tp_iaas_1", "tp_iaas_2", "tp_iaas_3", "tp_iaas_4", "tp_aislamiento"
                    ]
                    to_hide = {"Unnamed: 0", "index", "#", "No", "no"}
                    cols_finales = [c for c in keep if c in df_v.columns and c not in to_hide]
                    if not cols_finales:
                        st.info("No se encontraron las columnas esperadas para el censo.")
                    else:
                        st.dataframe(df_v[cols_finales], use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo mostrar el censo nominal: {e}")

    # --------- Cintilla de “Información actualizada” ---------
    import os as _os
    try:
        from zoneinfo import ZoneInfo
        tz_name = st.secrets.get("tz", _os.environ.get("REDIAAS_TZ", "America/Mexico_City"))
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = None

    now_ts = datetime.now(tz) if tz else datetime.now()
    fecha_txt = now_ts.strftime("%d-%m-%Y")
    hora_txt = now_ts.strftime("%H:%M:%S")
    st.markdown(
        f"""
        <div style="margin-top:16px; padding:10px 16px; background:rgba(255,255,255,0.06);
                    border-radius:10px; text-align:center;">
            <strong>Información actualizada al {fecha_txt} a las {hora_txt}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
