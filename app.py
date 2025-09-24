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
        for c in ["fecha_muestra","fecha_resultado","fec_ingreso"]:
            if c in tmp.columns:
                tmp[c] = pd.to_datetime(tmp[c], errors="coerce", dayfirst=True, infer_datetime_format=True)
        has_info = False
        for c in ["germen","tipo_resultado","tipo_muestra","cultivo"]:
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
        "no_cultivo","fecha_muestra","fecha_resultado","tipo_muestra","tipo_resultado","germen","resistencia","cultivo"
    ] if c in df_long.columns]
    df_long = df_long[id_cols + ordered]
    return df_long

def _norm_piso(s):
    return str(s).strip().upper()

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
            <span style="font-size:22px">{icon}</span>
            <span style="font-size:15px; opacity:.95">{label}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def modulo_vigilancia():
    st.subheader("🔍 Vigilancia Activa por Sector Hospitalario")

    with st.expander("⚙️ Configuración de Google Sheets", expanded=False):
        st.caption("Si no hay credenciales, se usa CSV público. Ajusta aquí el gid por pestaña si tu hoja no es '0'.")
        gid_vig = st.text_input("gid de pestaña 'Vigilancia'", value=DEFAULT_SHEET_GID_MAP["Vigilancia"])
        gid_his = st.text_input("gid de pestaña 'Histórico'",  value=DEFAULT_SHEET_GID_MAP["Histórico"])
        gid_map = {"Vigilancia": gid_vig, "Histórico": gid_his}
        if GS_READY:
            if st.secrets.get("gcp_service_account"):
                st.success(f"Conexión por Service Account lista. Sheet ID: {SHEET_ID}")
            else:
                st.warning("Service Account habilitada pero sin JSON en secrets.")
        else:
            msg = "Usando modo CSV público (sin credenciales). Asegúrate que el Sheet esté en 'Cualquiera con el enlace: Lector'."
            if _gs_err:
                st.info(msg + f" | Detalle: {_gs_err}")
            else:
                st.info(msg)

    # ===== Fila 1: Selector (angosto) + Plano (derecha) =====
    st.markdown("#### Selecciona el sector del hospital:")
    col_sel, col_plano = st.columns([1.1, 3.9])  # ¡importante mantener la misma proporción en filas siguientes!
    with col_sel:
        # Opciones desde la hoja
        try:
            df_vig_opts = get_vigilancia(gid_map)
            pisos_disponibles = sorted(
                df_vig_opts["piso"].dropna().astype(str).map(str.strip).unique()
            ) if "piso" in df_vig_opts.columns else []
        except Exception:
            pisos_disponibles = []
        opciones_sector = ["UMAE completa"] + pisos_disponibles
        plano_sel = st.selectbox("", options=opciones_sector, label_visibility="collapsed")

    with col_plano:
        imagen_path = os.path.join("data/planos", f"{plano_sel}.png") if plano_sel != "UMAE completa" else None
        if imagen_path and os.path.exists(imagen_path):
            st.image(imagen_path, use_container_width=True, caption=f"Plano sector {plano_sel}")
        elif plano_sel != "UMAE completa" and len(pisos_disponibles) > 0:
            st.caption("No hay imagen para este sector. (Opcional: coloca un PNG en data/planos con el nombre del piso).")

    # ===== Datos filtrados según 'piso' =====
    df_vig = get_vigilancia({"Vigilancia": gid_vig, "Histórico": gid_his})
    df_vig = filtra_por_piso(df_vig, plano_sel)
    df_censo = df_vig[_es_paciente(df_vig)].copy()

    # ===== Fila 2: Izquierda (módulos) + Derecha (info + servicios + contenido) =====
    col_left, col_right = st.columns([1.1, 3.9])  # MISMA PROPORCIÓN que la fila del PNG
    with col_left:
        st.markdown("### 🏥 Módulos disponibles")
        mostrar_curva_epidemica = st.checkbox("Curva Epidémica de IAAS", value=False)
        mostrar_curva_captura   = st.checkbox("Captura en INOSO", value=False)
        mostrar_reporte_cult    = st.checkbox("Reporte de cultivos", value=False)
        mostrar_censo           = st.checkbox("Censo nominal", value=False)
        st.button("🔙 Regresar al menú principal", on_click=lambda: st.session_state.update(menu=None))

    with col_right:
        # ===== Información general (tarjetas) =====
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

        # ===== Top 5 Servicios (debajo de tarjetas) =====
        st.markdown("### Servicios con más pacientes (Top 5)")
        if "servicio" in df_censo.columns and not df_censo.empty:
            top_srv = (
                df_censo.groupby("servicio")["servicio"].count()
                .sort_values(ascending=False).head(5).reset_index(name="pacientes")
            )
            st.dataframe(top_srv, use_container_width=True, hide_index=True)
        else:
            st.info("No hay columna 'servicio' para mostrar el Top 5.")

        st.markdown("---")

        # --- Curva epidémica ---
        if mostrar_curva_epidemica:
            st.subheader("📈 Curva Epidémica de IAAS")
            try:
                df_hist = get_historico({"Histórico": gid_his, "Vigilancia": gid_vig})
                if df_hist.empty or "fecha_reporte" not in df_hist.columns:
                    st.info("Histórico vacío o sin 'fecha_reporte'.")
                else:
                    tmp = filtra_por_piso(df_hist.copy(), plano_sel)
                    tmp["es_paciente"] = _es_paciente(tmp)
                    iaas_col = "iaas_sino" if "iaas_sino" in tmp.columns else None
                    if iaas_col:
                        tmp["iaas_num"] = pd.to_numeric(tmp[iaas_col], errors="coerce").fillna(0)
                    else:
                        cols = _iaas_cols(tmp)
                        tmp["iaas_num"] = tmp[cols].applymap(_es_si).any(axis=1).astype(int) if cols else 0
                    prev = (
                        tmp.groupby("fecha_reporte")
                        .agg(total_hosp=("es_paciente", "sum"),
                             iaas_activos=("iaas_num", "sum"))
                        .assign(prevalencia=lambda d: d["iaas_activos"] / d["total_hosp"].replace(0, pd.NA))
                        .reset_index()
                    )
                    dias = st.slider("Rango de días para la curva", 14, 180, 60, key="slider_curva")
                    if pd.notna(prev["fecha_reporte"].max()):
                        desde = prev["fecha_reporte"].max() - pd.Timedelta(days=dias)
                        prev = prev[prev["fecha_reporte"] >= desde]
                    st.line_chart(prev.set_index("fecha_reporte")[["prevalencia"]].dropna(),
                                  use_container_width=True)
                    st.caption(f"Prevalencia diaria (IAAS activos / hospitalizados) – Vista: {plano_sel}.")
            except Exception as e:
                st.error(f"No se pudo calcular la curva epidémica: {e}")

        # --- Captura en INOSO ---
        if mostrar_curva_captura:
            st.subheader("📊 Captura en INOSO (casos)")
            try:
                df_v = df_vig.copy()
                if df_v.empty:
                    st.info("'Vigilancia' está vacía.")
                else:
                    fecha_cols = [c for c in [
                        "fecha_reporte","fec_ingreso","fecha_muestra_1","fecha_resultado_1",
                        "fecha_muestra_2","fecha_resultado_2","fecha_muestra_3","fecha_resultado_3",
                        "fecha_muestra_4","fecha_resultado_4"
                    ] if c in df_v.columns]
                    fecha_ref = fecha_cols[0] if fecha_cols else None
                    if not fecha_ref:
                        st.info("No hay columnas de fecha para graficar la captura.")
                    else:
                        df_cap = df_v[_es_paciente(df_v)].copy()
                        df_cap = df_cap[pd.notna(df_cap[fecha_ref])]
                        dias = st.slider("Rango de días para captura", 14, 180, 60, key="slider_cap")
                        fecha_max = df_cap[fecha_ref].max()
                        if pd.notna(fecha_max):
                            desde = fecha_max - pd.Timedelta(days=dias)
                            df_cap = df_cap[df_cap[fecha_ref] >= desde]
                        serie = df_cap.groupby(fecha_ref)[fecha_ref].count().rename("casos").reset_index()
                        fig_cap = px.bar(serie, x=fecha_ref, y="casos", labels={"casos":"Casos/día"})
                        fig_cap.update_layout(xaxis_tickangle=-30)
                        st.plotly_chart(fig_cap, use_container_width=True)
                        st.caption(f"Conteo diario de registros – Vista: {plano_sel}.")
            except Exception as e:
                st.error(f"No se pudo calcular la captura INOSO: {e}")

        # --- Reporte de cultivos ---
        if mostrar_reporte_cult:
            st.subheader("🧪 Reporte de cultivos")
            try:
                df_v = df_vig.copy()
                if df_v.empty:
                    st.info("'Vigilancia' está vacía.")
                else:
                    df_lab = lab_desde_vigilancia(df_v)
                    if "cultivo" in df_lab.columns:
                        df_lab = df_lab[df_lab["cultivo"].map(_es_si)]
                    if df_lab.empty:
                        st.info("Sin cultivos positivos en esta vista.")
                    else:
                        fecha_ref = "fecha_muestra" if "fecha_muestra" in df_lab.columns else (
                            "fecha_resultado" if "fecha_resultado" in df_lab.columns else None
                        )
                        if fecha_ref:
                            dias = st.slider("Rango de días para el reporte", 7, 120, 30, key="slider_lab")
                            fecha_max = df_lab[fecha_ref].max()
                            if pd.notna(fecha_max):
                                desde = fecha_max - pd.Timedelta(days=dias)
                                df_lab = df_lab[df_lab[fecha_ref] >= desde]

                        st.metric(f"Registros de laboratorio ({plano_sel})", len(df_lab))

                        if "germen" in df_lab.columns:
                            top = (
                                df_lab["germen"].astype(str).str.strip()
                                .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                .value_counts().head(10).reset_index()
                            )
                            top.columns = ["Microorganismo", "Casos"]
                            if not top.empty:
                                fig_top = px.bar(top, x="Microorganismo", y="Casos")
                                fig_top.update_layout(xaxis_tickangle=-30)
                                st.plotly_chart(fig_top, use_container_width=True)

                        if "tipo_muestra" in df_lab.columns:
                            por_muestra = (
                                df_lab["tipo_muestra"].astype(str).str.strip()
                                .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                .value_counts().reset_index()
                            )
                            por_muestra.columns = ["Tipo de muestra", "Registros"]
                            if not por_muestra.empty:
                                fig_m = px.bar(por_muestra, x="Tipo de muestra", y="Registros")
                                fig_m.update_layout(xaxis_tickangle=-30)
                                st.plotly_chart(fig_m, use_container_width=True)

                        drop_cols = {"Unnamed: 0", "index", "no_cultivo", "cultivo", "fec_ingreso"}
                        cols = [c for c in df_lab.columns if c not in drop_cols]
                        st.dataframe(df_lab[cols], use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo generar el reporte de cultivos: {e}")

        # --- Censo nominal ---
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
                        "cama","status_paciente","servicio","fec_ingreso","ap_paterno","ap_materno","nombre","nss",
                        "ag_med","edad","sexo","iaas_1","iaas_2","iaas_3","iaas_4",
                        "tp_iaas_1","tp_iaas_2","tp_iaas_3","tp_iaas_4","tp_aislamiento"
                    ]
                    to_hide = {"Unnamed: 0", "index", "#", "No", "no"}
                    cols_finales = [c for c in keep if c in df_v.columns and c not in to_hide]
                    if not cols_finales:
                        st.info("No se encontraron las columnas esperadas para el censo.")
                    else:
                        st.dataframe(df_v[cols_finales], use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo mostrar el censo nominal: {e}")

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
