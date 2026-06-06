import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from controller.ArquivoController import ArquivoController
from view.ui import render_toast


@st.cache_data(ttl=120)
def _carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.carregar_actigrafia(arquivo_id, usuario_id)


def analises_page():
    # ─────────────────────────────────────────────
    # 1. CONFIGURAÇÃO DA PÁGINA
    # ─────────────────────────────────────────────
    st.title("Análises")
    st.divider()

    usuario    = st.session_state.get("usuario", {})
    usuario_id = usuario.get("id")

    if not usuario_id:
        st.info("Esta funcionalidade está disponível apenas para usuários cadastrados com e-mail.")
        return

    render_toast()

    # ══════════════════════════════════════════════════════════════
    # SELEÇÃO DO ARQUIVO — lido do banco do usuário
    # ══════════════════════════════════════════════════════════════

    arquivos = ArquivoController.listar(usuario_id)

    if not arquivos:
        st.info("Nenhum arquivo enviado ainda. Acesse **Conjunto de dados** para fazer upload.")
        return

    opcoes = {arq["nome"]: arq for arq in arquivos}

    col_arq, col_dia = st.columns(2)

    with col_arq:
        nome_escolhido = st.selectbox("Arquivo", list(opcoes.keys()))

    arquivo_id = opcoes[nome_escolhido]["id"]

    metadata, df_total = _carregar_actigrafia(arquivo_id, usuario_id)

    if df_total.empty:
        st.warning("Não foi possível processar este arquivo.")
        st.stop()

    # ── seleção do dia ───────────────────────────────────────────────
    dias = ArquivoController.dias_disponiveis(df_total)

    with col_dia:
        dia = st.selectbox("Dia", dias)

    df = ArquivoController.filtrar_dia(df_total, dia)

    if df.empty:
        st.warning("Sem dados para esse dia.")
        st.stop()

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # MÉTRICAS RÁPIDAS
    # ══════════════════════════════════════════════════════════════
    m1, m2, m3 = st.columns(3)
    m1.metric("PIM total", f"{df['pim'].sum():,.0f}")
    m2.metric("Pico PIM", f"{df['pim'].max():,.0f}")
    m3.metric("Temp. média", f"{df['temperatura'].mean():.1f} °C")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # GRÁFICOS
    # ══════════════════════════════════════════════════════════════

    # ── PIM ao longo do dia ─────────────────────────────────────────
    st.subheader("Atividade (PIM)")

    fig_pim = go.Figure()
    fig_pim.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["pim"],
        mode="lines",
        name="PIM",
        line=dict(color="#234cbe", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(29,78,216,0.1)",
    ))
    fig_pim.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(tickformat="%H:%M"),
        yaxis_title="PIM",
        hovermode="x unified",
    )
    st.plotly_chart(fig_pim, use_container_width=True)

    # ── Temperatura e Luz lado a lado ───────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Temperatura (°C)")
        fig_temp = px.line(df, x="timestamp", y="temperatura", color_discrete_sequence=["#c43903"])
        fig_temp.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                               xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="°C")
        st.plotly_chart(fig_temp, use_container_width=True)

    with c2:
        st.subheader("Luz (Lux)")
        # agrega por hora para o gráfico ficar legível
        df_hora = (df.set_index("timestamp")["luz"]
                   .resample("1h").mean()
                   .reset_index().rename(columns={"timestamp": "hora"}))
        fig_luz = px.bar(df_hora, x="hora", y="luz", color_discrete_sequence=["#ffb433"])
        fig_luz.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="Lux")
        st.plotly_chart(fig_luz, use_container_width=True)

    # ── Melanopic EDI (se tiver dados) ──────────────────────────────
    if "melanopic" in df.columns and df["melanopic"].sum() > 0:
        st.subheader("Melanopic EDI")
        fig_mel = px.line(df, x="timestamp", y="melanopic", color_discrete_sequence=["#7c3aed"])
        fig_mel.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="EDI")
        st.plotly_chart(fig_mel, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # METADADOS DO DISPOSITIVO
    # ══════════════════════════════════════════════════════════════
    with st.expander("Metadados do arquivo"):
        st.json(metadata)