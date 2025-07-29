import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")

# -------------------------- Encabezado institucional --------------------------
st.markdown("""
<div style='display: flex; justify-content: space-between; align-items: center;'>
    <img src='https://raw.githubusercontent.com/tu_usuario/logo_imss/main/logo_imss.png' width='100'>
    <div style='text-align: center;'>
        <h4>UMAE Hospital de Especialidades CMN SXXI</h4>
        <h5>División de Epidemiología</h5>
        <h2>Monitoreo de IAAS - REDIAAS</h2>
    </div>
    <img src='https://raw.githubusercontent.com/tu_usuario/logo_imss/main/logo_epi.png' width='100'>
</div>
""", unsafe_allow_html=True)

# -------------------------- Módulos --------------------------
def modulo_riesgos_iaas():
    st.subheader("Visualización de riesgos de IAAS por cama (2024)")
    df_coords = pd.read_csv("plantilla_coordenadas_camas.csv")
    df_iaas = pd.read_csv("rediaas.csv")

    assert 'cama' in df_iaas.columns and 'iaas_sino' in df_iaas.columns
    assert all(col in df_coords.columns for col in ['cama', 'coord_x', 'coord_y', 'piso'])

    df_riesgo = (
        df_iaas.groupby('cama')['iaas_sino']
        .agg(['sum', 'count'])
        .reset_index()
        .rename(columns={'sum': 'casos_iaas', 'count': 'total_pacientes'})
    )
    df_riesgo['porcentaje_iaas'] = 100 * df_riesgo['casos_iaas'] / df_riesgo['total_pacientes']

    df_final = pd.merge(df_coords, df_riesgo[['cama', 'porcentaje_iaas']], on='cama', how='left')
    df_final['porcentaje_iaas'] = df_final['porcentaje_iaas'].fillna(0)

    orden_pisos = ["5B Norte", "5B Sur", "4B Norte", "4B Sur", "3B Norte", "3B Sur", "2B Norte", "2B Sur",
                   "UCI", "UTR", "TMO", "4A", "3A", "2A", "1A"]
    df_final['piso'] = pd.Categorical(df_final['piso'], categories=orden_pisos, ordered=True)

    piso_sel = st.selectbox("🛏️🦠 Selecciona el piso a visualizar", options=df_final['piso'].dropna().unique())
    df_piso = df_final[df_final['piso'] == piso_sel].copy()
    df_piso['porcentaje_iaas_str'] = df_piso['porcentaje_iaas'].map("{:.2f}%".format)

    fig = px.scatter(
        df_piso,
        x='coord_x',
        y='coord_y',
        color='porcentaje_iaas',
        color_continuous_scale=[(0.0, "green"), (0.5, "orange"), (1.0, "red")],
        range_color=(0, 100),
        text='cama',
        hover_data={'cama': True, 'porcentaje_iaas_str': True},
        height=650
    )
    fig.update_traces(marker=dict(size=25), textposition='top center')
    fig.update_layout(
        title=f"🛏️ Mapa de Riesgo de IAAS – Piso {piso_sel}",
        yaxis_autorange="reversed",
        coloraxis_colorbar=dict(title="% IAAS", tickformat=".0f")
    )

    st.plotly_chart(fig, use_container_width=True)
    if st.button("🔙 Regresar al menú principal"):
        st.session_state.menu = "inicio"


def modulo_vigilancia():
    st.subheader("Vigilancia Activa por Sector Hospitalario")
    try:
        planos = sorted([f.replace(".png", "") for f in os.listdir("data/planos") if f.endswith(".png")], reverse=True)
        plano_sel = st.selectbox("Selecciona el sector del hospital:", options=planos)
        st.image(f"data/planos/{plano_sel}.png", use_column_width=True)
    except Exception as e:
        st.error(f"Error al cargar planos: {e}")

    if st.button("🔙 Regresar al menú principal"):
        st.session_state.menu = "inicio"


# -------------------------- Control de navegación --------------------------
if "menu" not in st.session_state:
    st.session_state.menu = "inicio"

if st.session_state.menu == "inicio":
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Riesgos de IAAS por cama"):
            st.session_state.menu = "riesgos"
    with col2:
        if st.button("🧪 Vigilancia activa"):
            st.session_state.menu = "vigilancia"

elif st.session_state.menu == "riesgos":
    modulo_riesgos_iaas()

elif st.session_state.menu == "vigilancia":
    modulo_vigilancia()
