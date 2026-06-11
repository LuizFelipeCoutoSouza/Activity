"""
view/pages/exportar_relatorio.py — Relatórios exportados pelo usuário.

Lista os arquivos .zip gerados em "Análise 2" e salvos no banco, permitindo
baixar novamente ou excluir.
"""

import streamlit as st
from controller.relatorio_controller import RelatorioController
from view.ui import render_toast, set_toast, get_usuario_id, paginacao

POR_PAGINA = 8


# ── Cache de conteúdo ─────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _buscar_conteudo(relatorio_id: int, usuario_id: int) -> tuple:
    return RelatorioController.baixar(relatorio_id, usuario_id)


# ── Diálogo de exclusão ────────────────────────────────────────────────────────

@st.dialog("Excluir relatório")
def _dialogo_excluir(relatorio_id: int, usuario_id: int, nome: str):
    st.write(f"Tem certeza que deseja excluir **{nome}**?")
    st.caption("Esta ação não pode ser desfeita.")
    col1, col2 = st.columns(2)
    if col1.button("Excluir", type="primary", width="stretch"):
        ok, msg = RelatorioController.deletar(relatorio_id, usuario_id)
        st.cache_data.clear()
        st.session_state.pop("confirm_delete_relatorio", None)
        set_toast(msg) if ok else st.error(msg)
        st.rerun()
    if col2.button("Cancelar", width="stretch"):
        st.session_state.pop("confirm_delete_relatorio", None)
        st.rerun()


# ── Página principal ──────────────────────────────────────────────────────────

def exportar_relatorio_page():
    st.title("📄 Exportar relatório")
    st.divider()

    usuario_id = get_usuario_id()
    if not usuario_id:
        return

    render_toast()

    relatorios = RelatorioController.listar(usuario_id)

    if "confirm_delete_relatorio" in st.session_state:
        rel_id = st.session_state["confirm_delete_relatorio"]
        relatorio = next((r for r in relatorios if r["id"] == rel_id), None)
        if relatorio:
            _dialogo_excluir(rel_id, usuario_id, relatorio["nome"])
        else:
            st.session_state.pop("confirm_delete_relatorio", None)

    if not relatorios:
        st.info(
            "Nenhum relatório exportado ainda. Acesse **Análise 2** e use o botão "
            "\"Baixar dados (.zip)\" ao final da página para gerar um."
        )
        return

    n = len(relatorios)
    n_paginas = max(1, (n + POR_PAGINA - 1) // POR_PAGINA)
    pagina    = min(max(st.session_state.get("pag_relatorios", 0), 0), n_paginas - 1)
    st.session_state["pag_relatorios"] = pagina
    inicio = pagina * POR_PAGINA
    pagina_relatorios = relatorios[inicio : inicio + POR_PAGINA]

    if n_paginas > 1:
        st.subheader(f"Meus relatórios — página {pagina + 1} de {n_paginas} ({n} no total)")
    else:
        st.subheader(f"Meus relatórios ({n})")

    cols_h = st.columns([4, 3, 1.5, 1.3, 1.3])
    for col, h in zip(cols_h, ["Relatório", "Arquivo de origem", "Tamanho", "", ""]):
        if h:
            col.markdown(f"**{h}**")

    for relatorio in pagina_relatorios:
        _linha_relatorio(relatorio, usuario_id)

    paginacao(pagina, n_paginas, "pag_relatorios")


# ── Linha de relatório ──────────────────────────────────────────────────────────

def _linha_relatorio(relatorio: dict, usuario_id: int):
    st.divider()
    cols = st.columns([4, 3, 1.5, 1.3, 1.3])

    cols[0].write(f"**{relatorio['nome']}**")
    cols[0].caption(relatorio["criado_em"].strftime("%d/%m/%Y %H:%M"))

    cols[1].write(relatorio.get("arquivo_origem") or "—")

    cols[2].write(_formatar_bytes(relatorio["tamanho_bytes"]))

    conteudo, nome_arq = _buscar_conteudo(relatorio["id"], usuario_id)
    if conteudo:
        cols[3].download_button(
            "Baixar", data=conteudo, file_name=nome_arq, mime="application/zip",
            key=f"dl_rel_{relatorio['id']}", width="stretch",
        )

    if cols[4].button("Excluir", key=f"del_rel_{relatorio['id']}", width="stretch"):
        st.session_state["confirm_delete_relatorio"] = relatorio["id"]
        st.rerun()


# ── Helper ────────────────────────────────────────────────────────────────────

def _formatar_bytes(n: int) -> str:
    if n < 1_024:
        return f"{n} B"
    if n < 1_024 ** 2:
        return f"{n / 1_024:.1f} KB"
    return f"{n / 1_024 ** 2:.1f} MB"
