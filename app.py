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
#            Conexión a Google Sheets (robusta)
# ======================================================
SHEET_ID = st.secrets.get(
    "sheet_id",
    os.environ.get("REDIAAS_SHEET_ID", "1dXRRepFI6l3t6kW6pZ3BJo1G63EESINCUOd6L98V9E0"),
)

GS_READY = False
_gs_err: Optional[str] = None

# Helper: valida que existan credenciales en secrets
def _get_sa_info():
    sa = st.secrets.get("gcp_service_account")
    if not sa or not isinstance(sa, dict) or not sa.get("client_email"):
        raise RuntimeError("Falta st.secrets['gcp_service_account'] (JSON del Service Account)")
    return sa

# Intento 1: gspread + google.oauth2 (recomendado)
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
    # Intento 2: compatibilidad con oauth2client si el proyecto ya lo usa
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
    for c in [
        "fecha_reporte",
        "fec_ingreso",
        "fec_egreso",
        "fec_inicio_sintomas",
        "fec_toma_muestra",
        "fecha_muestra_1","fecha_resultado_1",
        "fecha_muestra_2","fecha_resultado_2",
        "fecha_muestra_3","fecha_resultado_3",
        "fecha_muestra_4","fecha_resultado_4",
    ]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True, infer_datetime_format=True)

    return df


def get_vigilancia() -> pd.DataFrame:
    return _leer_tab(SHEET_ID, "Vigilancia")


def get_historico() -> pd.DataFrame:
    return _leer_tab(SHEET_ID, "Histórico")


# ======================================================
#        Módulo: Riesgo IAAS por cama (SIN CAMBIOS)
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
#        Módulo: Vigilancia Activa (Drive + Histórico)
# ======================================================

def _es_paciente(df: pd.DataFrame) -> pd.Series:
    if "status_paciente" in df.columns:
        return df["status_paciente"].astype(str).str.lower() != "sin paciente"
    return pd.Series([True] * len(df), index=df.index)


def _iaas_num(df: pd.DataFrame, col="iaas_sino") -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series([0] * len(df), index=df.index)

# --- Nuevo: Laboratorio desde Vigilancia (aplanado 1..4) ---
def lab_desde_vigilancia(df_src: pd.DataFrame) -> pd.DataFrame:
    id_cols = [
        "piso","servicio","cama","nss","ap_paterno","ap_materno","nombre","sexo","edad","fec_ingreso"
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
                tmp[c] = pd.to_datetime(tmp[c], errors="coerce", dayfirst=True, infer_datetime_format=True)
        # Filtra filas sin información relevante
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
        "no_cultivo","fecha_muestra","fecha_resultado","tipo_muestra","tipo_resultado","germen","resistencia"
    ] if c in df_long.columns]
    df_long = df_long[id_cols + ordered]
    return df_long


def modulo_vigilancia():
    st.subheader("🔍 Vigilancia Activa por Sector Hospitalario")

    # Indicador de conexión a Google Sheets
    with st.expander("Estado de conexión a Google Sheets", expanded=False):
        if GS_READY:
            if st.secrets.get("gcp_service_account"):
                st.success("Conexión preparada (credenciales cargadas). ID de hoja: " + SHEET_ID)
            else:
                st.error("Faltan credenciales: st.secrets['gcp_service_account']")
        else:
            st.error("Google Sheets no listo. " + (f"Detalle: {_gs_err}" if _gs_err else ""))
            st.info(
                "Sube el JSON del Service Account a st.secrets como 'gcp_service_account' y comparte la hoja con ese correo."
            )

    # Selector de planos (tu lógica existente)
    planos = [f.replace(".png", "") for f in sorted(os.listdir("data/planos")) if f.endswith(".png")]
    if not planos:
        st.warning("No hay planos en 'data/planos'. Se mostrarán solo tablas y gráficas.")
        plano_sel = None
    else:
        st.markdown("##### Selecciona el sector del hospital:")
        col_sel, _ = st.columns([1.2, 3])
        with col_sel:
            plano_sel = st.selectbox("", options=planos, label_visibility="collapsed")

    imagen_path = os.path.join("data/planos", f"{plano_sel}.png") if plano_sel else None

    col1, col2 = st.columns([1, 4])

    with col1:
        st.markdown("### 🧭 Módulos disponibles")
        mostrar_curva_epidemica = st.checkbox("Curva Epidémica de IAAS", value=False)
        mostrar_curva_captura   = st.checkbox("Captura en INOSO", value=False)
        mostrar_laboratorio     = st.checkbox("Laboratorio (desde Vigilancia)", value=False)
        mostrar_censo           = st.checkbox("Censo nominal de casos (en vivo)", value=False)

        st.markdown("###")
        st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

    with col2:
        if imagen_path and os.path.exists(imagen_path):
            st.image(imagen_path, use_container_width=True, caption=f"Plano sector {plano_sel}")
        elif plano_sel:
            st.warning("⚠️ No se encontró el plano del sector.")

        # ------ Submódulos ------
        if mostrar_curva_epidemica:
            st.subheader("📈 Curva Epidémica de IAAS (Histórico)")
            if not GS_READY:
                st.warning("Conecta Google Sheets (sube credenciales y comparte la hoja) para mostrar la curva.")
            else:
                try:
                    df_hist = get_historico()
                    if df_hist.empty or "fecha_reporte" not in df_hist.columns:
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
            st.subheader("🧪 Laboratorio (derivado de Vigilancia)")
            if not GS_READY:
                st.warning("Conecta Google Sheets para mostrar laboratorio.")
            else:
                try:
                    df_vig = get_vigilancia()
                    if df_vig.empty:
                        st.info("'Vigilancia' está vacía.")
                    else:
                        df_lab_long = lab_desde_vigilancia(df_vig)
                        if df_lab_long.empty:
                            st.info("Sin registros de laboratorio en 'Vigilancia'.")
                        else:
                            # Filtro por últimos días, usa fecha_muestra si existe, si no fecha_resultado
                            fecha_ref = "fecha_muestra" if "fecha_muestra" in df_lab_long.columns else (
                                "fecha_resultado" if "fecha_resultado" in df_lab_long.columns else None
                            )
                            if fecha_ref:
                                dias = st.slider("Rango de días a analizar", 7, 120, 30)
                                fecha_max = df_lab_long[fecha_ref].max()
                                if pd.notna(fecha_max):
                                    desde = fecha_max - pd.Timedelta(days=dias)
                                    df_lab_long = df_lab_long[df_lab_long[fecha_ref] >= desde]

                            st.metric("Registros de laboratorio", len(df_lab_long))

                            if "germen" in df_lab_long.columns:
                                top = (
                                    df_lab_long["germen"].astype(str).str.strip()
                                    .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                    .value_counts().head(10).reset_index()
                                )
                                top.columns = ["Microorganismo", "Casos"]
                                if not top.empty:
                                    fig_top = px.bar(top, x="Microorganismo", y="Casos")
                                    fig_top.update_layout(xaxis_tickangle=-30)
                                    st.plotly_chart(fig_top, use_container_width=True)

                            if "tipo_muestra" in df_lab_long.columns:
                                por_muestra = (
                                    df_lab_long["tipo_muestra"].astype(str).str.strip()
                                    .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                    .value_counts().reset_index()
                                )
                                por_muestra.columns = ["Tipo de muestra", "Registros"]
                                if not por_muestra.empty:
                                    fig_m = px.bar(por_muestra, x="Tipo de muestra", y="Registros")
                                    fig_m.update_layout(xaxis_tickangle=-30)
                                    st.plotly_chart(fig_m, use_container_width=True)

                            st.dataframe(df_lab_long, use_container_width=True)
                except Exception as e:
                    st.error(f"No se pudo leer laboratorio desde 'Vigilancia': {e}")

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
