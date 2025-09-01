# app.py
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
