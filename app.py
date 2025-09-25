# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import unicodedata
from datetime import datetime
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
    for c in [
        "fecha_reporte", "fec_ingreso", "fec_egreso", "fec_inicio_sintomas", "fec_toma_muestra",
        "fecha_muestra_1", "fecha_resultado_1", "fecha_muestra_2", "fecha_resultado_2",
        "fecha_muestra_3", "fecha_resultado_3", "fecha_muestra_4", "fecha_resultado_4",
    ]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    return df


def get_vigilancia(gid_map: dict) -> pd.DataFrame:
    """Devuelve la hoja operativa del día.
    Preferimos "Viglancia"; si no existe, probamos "Vigilancia"; si ninguna, DataFrame vacío.
    """
    # Intento 1: "Viglancia"
    df = _leer_tab(SHEET_ID, "Viglancia", gid_map)
    if not df.empty:
        return df
    # Intento 2: "Vigilancia"
    df = _leer_tab(SHEET_ID, "Vigilancia", gid_map)
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

        # ===== Servicios top 5 =====
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

        # --- Curva epidémica (desde Histórico) ---
        if mostrar_curva_epidemica:
            st.subheader("📈 Curva Epidémica de IAAS")
            try:
                df_hist = get_historico(gid_map)
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
                    st.line_chart(prev.set_index("fecha_reporte")["prevalencia"].dropna(), use_container_width=True)
                    st.caption(f"Prevalencia diaria (IAAS activos / hospitalizados) – Vista: {plano_sel}.")
            except Exception as e:
                st.error(f"No se pudo calcular la curva epidémica: {e}")

        # --- Captura en INOSO (desde Viglancia/Vigilancia) ---
        if mostrar_curva_captura:
            st.subheader("📊 Captura en INOSO (casos)")
            try:
                df_v = df_vig.copy()
                if df_v.empty:
                    st.info("'Viglancia/Vigilancia' está vacía.")
                else:
                    fecha_cols = [c for c in [
                        "fecha_reporte", "fec_ingreso", "fecha_muestra_1", "fecha_resultado_1",
                        "fecha_muestra_2", "fecha_resultado_2", "fecha_muestra_3", "fecha_resultado_3",
                        "fecha_muestra_4", "fecha_resultado_4"
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
                        fig_cap = px.bar(serie, x=fecha_ref, y="casos", labels={"casos": "Casos/día"})
                        fig_cap.update_layout(xaxis_tickangle=-30)
                        st.plotly_chart(fig_cap, use_container_width=True)
                        st.caption(f"Conteo diario de registros – Vista: {plano_sel}.")
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

                        # --- Treemap interactivo de microorganismos ---
                        # 1) Conteo por germen
                        if "germen" in df_lab.columns:
                            top = (
                                df_lab["germen"].astype(str).str.strip()
                                .replace({"nan": pd.NA, "": pd.NA}).dropna()
                                .value_counts().reset_index()
                            )
                            top.columns = ["Microorganismo", "Casos"]
                        else:
                            top = pd.DataFrame(columns=["Microorganismo", "Casos"])

                        if not top.empty:
                            # Estado del filtro
                            if "micro_filter" not in st.session_state:
                                st.session_state.micro_filter = None

                            # Treemap con click-to-filter (si hay dependencia), si no, fallback a selectbox
                            can_click = False
                            try:
                                from streamlit_plotly_events import plotly_events  # type: ignore
                                can_click = True
                            except Exception:
                                can_click = False

                            fig_top = px.treemap(top, path=["Microorganismo"], values="Casos")
                            fig_top.update_traces(root_color="lightgrey")

                            clicked_label = None
                            if can_click:
                                selected = plotly_events(fig_top, click_event=True, hover_event=False, select_event=False,
                                                         key=f"treemap_micro_{_norm_piso(plano_sel)}")
                                if selected:
                                    # plotly_events devuelve dicts con varias claves; intentamos obtener etiqueta
                                    cand = selected[0]
                                    clicked_label = cand.get("label") or cand.get("text") or cand.get("id")
                            else:
                                st.plotly_chart(fig_top, use_container_width=True)

                            # Fallback UI si no hay click events disponibles
                            if not can_click:
                                opciones = ["(Todos)"] + top["Microorganismo"].tolist()
                                sel_ui = st.selectbox("Filtrar por microorganismo", opciones, index=0,
                                                      key=f"sel_micro_{_norm_piso(plano_sel)}")
                                if sel_ui != "(Todos)":
                                    st.session_state.micro_filter = sel_ui
                                else:
                                    st.session_state.micro_filter = None

                            # Aplicar filtro por click (o por selectbox fallback)
                            if clicked_label:
                                st.session_state.micro_filter = clicked_label

                            if st.session_state.micro_filter:
                                st.success(f"Filtro aplicado: {st.session_state.micro_filter}")
                                df_lab = df_lab[df_lab["germen"].astype(str).str.strip().str.casefold() ==
                                                str(st.session_state.micro_filter).strip().casefold()]
                                if st.button("Quitar filtro", key=f"clear_micro_{_norm_piso(plano_sel)}"):
                                    st.session_state.micro_filter = None
                                    st.rerun()

                        # Métrica de registros tras aplicar filtro
                        st.metric(f"Registros de laboratorio ({plano_sel})", len(df_lab))

                        # 2) Distribución por tipo de muestra
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

                        # 3) Tabla detallada
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
    # Requerimiento: SIEMPRE hora/fecha actuales del refresco (no del histórico ni del contenido)
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
        <div style=\"margin-top:16px; padding:10px 16px; background:rgba(255,255,255,0.06);
                    border-radius:10px; text-align:center;\">
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
    # (Se conserva el módulo de riesgo por cama por si lo usas)
    # Si lo deseas ocultar, elimina este bloque y el botón del menú.
    st.info("Módulo de riesgo por cama disponible en otra sección del código.")
elif st.session_state.menu == "vigilancia":
    modulo_vigilancia()
