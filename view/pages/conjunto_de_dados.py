"""
view/pages/conjunto_de_dados.py — Gerenciamento de arquivos .txt do usuário.

Funcionalidades: upload, listagem paginada com filtros, busca, edição e exclusão.

Filtros seguem o padrão draft/aplicado:
  _d_*        → estado dos widgets antes de clicar "Aplicar"
  filtro_*    → estado efetivamente usado na listagem
"""

import io
import zipfile
from datetime import datetime, timedelta

import streamlit as st
from st_keyup import st_keyup
from controller.ArquivoController import ArquivoController
from view.ui import set_toast, render_toast

POR_PAGINA   = 5
OPCOES_ORDEM = ["Nome", "Data de envio", "Tamanho", "Linhas", "Atualização"]

# Mapeamento draft ↔ aplicado (mesma ordem)
_CHAVES_DRAFT  = ["_d_data_ini", "_d_data_fim", "_d_ordenar_por", "_d_ordem_asc", "_d_apenas_atualizados"]
_CHAVES_FILTRO = ["filtro_data_ini", "filtro_data_fim", "filtro_ordenar_por", "filtro_ordem_asc", "filtro_apenas_atualizados"]


# ── Cache de conteúdo ─────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _buscar_conteudo(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.baixar(arquivo_id, usuario_id)


# ── Callback de checkbox ──────────────────────────────────────────────────────

def _toggle_chk(arq_id: int, gen: int):
    key = f"chk_{arq_id}_{gen}"
    sel = st.session_state.setdefault("selecionados", set())
    if st.session_state.get(key, False):
        sel.add(arq_id)
    else:
        sel.discard(arq_id)


# ── Dialog de edição ──────────────────────────────────────────────────────────

@st.dialog("Editar arquivo")
def _dialogo_editar(arquivo_id: int, usuario_id: int):
    arquivos = ArquivoController.listar(usuario_id)
    arquivo  = next((a for a in arquivos if a["id"] == arquivo_id), None)

    if not arquivo:
        st.error("Arquivo não encontrado.")
        return

    st.caption(
        f"Linhas: {arquivo['num_linhas']:,} · "
        f"Encoding: {arquivo.get('encoding') or '—'} · "
        f"{_formatar_bytes(arquivo['tamanho_bytes'])} · "
        f"Enviado em {arquivo['criado_em'].strftime('%d/%m/%Y %H:%M')}"
    )

    nome_sem_ext = arquivo["nome"][:-4] if arquivo["nome"].lower().endswith(".txt") else arquivo["nome"]
    novo_nome = st.text_input(
        "Nome do arquivo",
        value=nome_sem_ext,
        help="A extensão .txt é adicionada automaticamente",
    )
    st.caption("A extensão `.txt` é adicionada automaticamente ao salvar.")
    nova_desc = st.text_area(
        "Descrição",
        value=arquivo.get("descricao") or "",
        max_chars=200,
        height=80,
    )

    st.divider()
    st.markdown("**Substituir conteúdo** *(opcional)*")
    st.caption("Envie um novo .txt para substituir o conteúdo mantendo nome e descrição acima.")
    novo_arq = st.file_uploader("Novo arquivo .txt", type=["txt"], key="edit_uploader")

    col1, col2 = st.columns(2)
    if col1.button("Salvar", type="primary", use_container_width=True):
        if novo_arq:
            ok, msg = ArquivoController.substituir_arquivo(arquivo_id, usuario_id, novo_nome, nova_desc, novo_arq)
        else:
            ok, msg = ArquivoController.atualizar_metadados(arquivo_id, usuario_id, novo_nome, nova_desc)

        if ok:
            st.cache_data.clear()
            st.session_state.pop("editando_id", None)
            set_toast("Arquivo atualizado com sucesso.")
            st.rerun()
        else:
            st.error(msg)

    if col2.button("Cancelar", use_container_width=True):
        st.session_state.pop("editando_id", None)
        st.rerun()


# ── Página principal ──────────────────────────────────────────────────────────

def conjunto_de_dados_page():
    st.title("🗃️ Conjunto de dados")

    usuario    = st.session_state.get("usuario", {})
    usuario_id = usuario.get("id")

    if not usuario_id:
        st.info("Esta funcionalidade está disponível apenas para usuários cadastrados com e-mail.")
        return

    render_toast()

    if "editando_id" in st.session_state:
        _dialogo_editar(st.session_state["editando_id"], usuario_id)

    arquivos = ArquivoController.listar(usuario_id)

    total_bytes  = sum(a["tamanho_bytes"] for a in arquivos)
    total_linhas = sum(a.get("num_linhas") or 0 for a in arquivos)
    col1, col2, col3 = st.columns(3)
    col1.metric("Arquivos", len(arquivos))
    col2.metric("Tamanho total", _formatar_bytes(total_bytes))
    col3.metric("Linhas salvas", f"{total_linhas:,}")

    aba_lista, aba_upload = st.tabs(["🗃️  Meus arquivos", "⬆️  Enviar"])
    with aba_lista:
        _secao_listagem(usuario_id, arquivos)
    with aba_upload:
        _secao_upload(usuario_id)


# ── Upload ────────────────────────────────────────────────────────────────────

def _resumir_upload(msgs: list) -> tuple:
    n     = len(msgs)
    n_ok  = sum(1 for ok, _ in msgs if ok)
    n_err = n - n_ok

    if n_err == 0:
        texto = msgs[0][1] if n == 1 else f"{n_ok} arquivo(s) enviado(s) com sucesso."
        return "success", texto
    if n_ok == 0:
        texto = msgs[0][1] if n == 1 else "Nenhum arquivo foi enviado. Verifique os nomes ou o formato."
        return "error", texto
    return "warning", f"{n_ok} de {n} enviado(s). {n_err} ignorado(s) — nome duplicado ou formato inválido."


def _secao_upload(usuario_id: int):
    counter = st.session_state.get("upload_counter", 0)

    if "upload_msg" in st.session_state:
        tipo, texto = st.session_state.pop("upload_msg")
        if tipo == "success":
            st.toast(texto, icon="✅")
        else:
            getattr(st, tipo)(texto)

    arquivos = st.file_uploader(
        "Selecione um ou mais arquivos .txt",
        type=["txt"],
        accept_multiple_files=True,
        key=f"uploader_{counter}",
    )

    descricoes: dict = {}
    if arquivos:
        if len(arquivos) == 1:
            descricoes[arquivos[0].name] = st.text_input(
                "Descrição (opcional)", max_chars=200,
                placeholder="Ex: Coleta paciente João — nov/2025",
                key=f"desc_{counter}",
            )
        else:
            st.write("**Descrição por arquivo** *(opcional)*")
            for i, f in enumerate(arquivos):
                descricoes[f.name] = st.text_input(
                    f.name, max_chars=200, placeholder="Descrição opcional",
                    key=f"fdesc_{i}_{counter}",
                )

    if st.button("Enviar", type="primary", disabled=not arquivos):
        msgs = []
        with st.spinner("Enviando..."):
            for f in arquivos:
                ok, msg = ArquivoController.fazer_upload(usuario_id, f, descricoes.get(f.name, ""))
                msgs.append((ok, msg))

        st.session_state["upload_msg"]    = _resumir_upload(msgs)
        st.session_state["upload_counter"] = counter + 1
        st.session_state["pag_arquivos"]  = 0
        st.rerun()


# ── Listagem ──────────────────────────────────────────────────────────────────

def _secao_listagem(usuario_id: int, arquivos: list):
    n = len(arquivos)

    if not arquivos:
        st.subheader("Meus arquivos (0)")
        st.info("Nenhum arquivo enviado ainda. Use o painel acima para fazer upload.")
        return

    ids_atuais = {arq["id"] for arq in arquivos}
    sel: set   = st.session_state.setdefault("selecionados", set())
    sel        &= ids_atuais
    gen: int   = st.session_state.setdefault("chk_gen", 0)

    if "zip_pronto" in st.session_state:
        dados_zip, nome_zip, n_zip = st.session_state.pop("zip_pronto")
        st.toast(f"{n_zip} arquivo(s) compactado(s). Clique para baixar.", icon="✅")
        st.download_button(
            f"⬇️  Baixar  {nome_zip}", data=dados_zip, file_name=nome_zip,
            mime="application/zip", key="dl_zip_final", use_container_width=True,
        )

    # Renderiza painel de filtros (draft → widgets)
    _painel_filtros()

    # Lê os valores APLICADOS (não os drafts) para filtrar
    busca     = st.session_state.get("busca_arquivo", "")
    data_ini  = st.session_state.get("filtro_data_ini")
    data_fim  = st.session_state.get("filtro_data_fim")
    apenas_at = st.session_state.get("filtro_apenas_atualizados", False)
    ordenar   = st.session_state.get("filtro_ordenar_por", "Nome")
    asc       = st.session_state.get("filtro_ordem_asc", True)

    # Busca textual é reativa: reseta paginação quando muda
    if busca != st.session_state.get("_busca_anterior", ""):
        st.session_state["pag_arquivos"]   = 0
        st.session_state["_busca_anterior"] = busca

    arquivos_filtrados = _aplicar_filtros(arquivos, busca, data_ini, data_fim, apenas_at, ordenar, asc)
    n_filtrado = len(arquivos_filtrados)

    n_paginas = max(1, (n_filtrado + POR_PAGINA - 1) // POR_PAGINA)
    pagina    = min(max(st.session_state.get("pag_arquivos", 0), 0), n_paginas - 1)
    st.session_state["pag_arquivos"] = pagina
    inicio = pagina * POR_PAGINA
    arquivos_pagina = arquivos_filtrados[inicio : inicio + POR_PAGINA]

    ha_filtros = any([busca, data_ini, data_fim, apenas_at])
    if ha_filtros:
        titulo = f"Meus arquivos — {n_filtrado} de {n} resultado(s)"
    elif n_paginas > 1:
        titulo = f"Meus arquivos — página {pagina + 1} de {n_paginas} ({n} no total)"
    else:
        titulo = f"Meus arquivos ({n})"
    st.subheader(titulo)

    if n_filtrado == 0:
        st.info("Nenhum arquivo corresponde aos filtros aplicados.")
        return

    # Controles de seleção em massa
    n_sel = len(sel)
    c1, c2, *_ = st.columns([2.5, 2.5, 6])
    if c1.button("Selecionar todos", use_container_width=True, key="btn_sel_all"):
        st.session_state["selecionados"] = ids_atuais.copy()
        st.session_state["chk_gen"]      = gen + 1
        st.rerun()
    if c2.button("Limpar seleção", use_container_width=True, key="btn_des_all", disabled=n_sel == 0):
        st.session_state["selecionados"] = set()
        st.session_state["chk_gen"]      = gen + 1
        st.rerun()

    if n_sel > 0:
        ba1, ba2 = st.columns(2)
        if ba1.button(f"⬇️  Download ({n_sel} arquivo(s))", type="primary", use_container_width=True, key="btn_bulk_dl"):
            _preparar_zip(list(sel), usuario_id)
        if ba2.button(f"🗑️  Excluir ({n_sel} arquivo(s))", use_container_width=True, key="btn_bulk_del"):
            st.session_state["bulk_delete_ids"] = list(sel)

    if "bulk_delete_ids" in st.session_state:
        ids_del   = st.session_state["bulk_delete_ids"]
        nomes_del = [a["nome"] for a in arquivos if a["id"] in ids_del]
        preview   = ", ".join(nomes_del[:3]) + (" ..." if len(nomes_del) > 3 else "")
        st.warning(f"Excluir **{len(ids_del)}** arquivo(s)? ({preview})")
        cd1, cd2 = st.columns(2)
        if cd1.button("✓ Confirmar exclusão", type="primary", key="conf_bulk_del", use_container_width=True):
            for arq_id in ids_del:
                ArquivoController.deletar(arq_id, usuario_id)
            st.session_state["selecionados"] -= set(ids_del)
            st.session_state["chk_gen"]      += 1
            st.cache_data.clear()
            st.session_state.pop("bulk_delete_ids", None)
            set_toast(f"{len(ids_del)} arquivo(s) excluído(s).")
            st.rerun()
        if cd2.button("✗ Cancelar", key="canc_bulk_del", use_container_width=True):
            st.session_state.pop("bulk_delete_ids", None)
            st.rerun()

    cols_h = st.columns([0.5, 4, 2.5, 1.5, 3])
    for col, h in zip(cols_h, ["", "Nome do arquivo", "Descrição", "Atualização", "Ações"]):
        col.markdown(f"**{h}**")

    for arq in arquivos_pagina:
        _linha_arquivo(arq, usuario_id, gen)

    _controles_paginacao(pagina, n_paginas)


# ── Painel de filtros ─────────────────────────────────────────────────────────

def _painel_filtros() -> None:
    """
    Renderiza a barra de busca e a linha de filtros compacta.

    Os widgets escrevem em chaves de rascunho (_d_*). O botão "Aplicar"
    copia os rascunhos para as chaves efetivas (filtro_*) e reseta a paginação.
    A busca textual é reativa e não depende do botão "Aplicar".
    """
    _init_draft()

    # Busca textual — reativa, sem botão Aplicar
    st_keyup(
        "Buscar por nome ou descrição",
        placeholder="Nome do arquivo ou trecho da descrição...",
        key="busca_arquivo",
    )

    # Linha de filtros compacta
    c1, c2, c3, c4, c5, c6, c7 = st.columns([1.8, 1.8, 2.8, 1.3, 2.0, 1.5, 1.2])

    with c1:
        st.date_input("De", key="_d_data_ini", format="DD/MM/YYYY")
    with c2:
        st.date_input("Até", key="_d_data_fim", format="DD/MM/YYYY")
    with c3:
        st.selectbox("Ordenar por", OPCOES_ORDEM, key="_d_ordenar_por")
    with c4:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.checkbox("Crescente", key="_d_ordem_asc")
    with c5:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.checkbox("Só atualizados", key="_d_apenas_atualizados")
    with c6:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Aplicar", type="primary", use_container_width=True):
            _commit_draft()
            st.rerun()
    with c7:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Limpar", use_container_width=True, disabled=not _tem_filtros_ativos()):
            _limpar_filtros()
            st.rerun()

    # Indicador sutil de filtros ativos
    _caption_filtros_ativos()


# ── Estado dos filtros (draft / aplicado) ─────────────────────────────────────

def _init_draft() -> None:
    """Inicializa as chaves de rascunho a partir dos filtros aplicados (apenas na primeira vez)."""
    st.session_state.setdefault("_d_data_ini",           st.session_state.get("filtro_data_ini"))
    st.session_state.setdefault("_d_data_fim",           st.session_state.get("filtro_data_fim"))
    st.session_state.setdefault("_d_ordenar_por",        st.session_state.get("filtro_ordenar_por", "Nome"))
    st.session_state.setdefault("_d_ordem_asc",          st.session_state.get("filtro_ordem_asc", True))
    st.session_state.setdefault("_d_apenas_atualizados", st.session_state.get("filtro_apenas_atualizados", False))


def _commit_draft() -> None:
    """Copia o rascunho para os filtros aplicados e reseta a paginação."""
    st.session_state["filtro_data_ini"]            = st.session_state.get("_d_data_ini")
    st.session_state["filtro_data_fim"]            = st.session_state.get("_d_data_fim")
    st.session_state["filtro_ordenar_por"]         = st.session_state.get("_d_ordenar_por", "Nome")
    st.session_state["filtro_ordem_asc"]           = st.session_state.get("_d_ordem_asc", True)
    st.session_state["filtro_apenas_atualizados"]  = st.session_state.get("_d_apenas_atualizados", False)
    st.session_state["pag_arquivos"] = 0


def _limpar_filtros() -> None:
    """Remove todos os filtros (rascunho e aplicados) e reseta a paginação."""
    for k in _CHAVES_DRAFT + _CHAVES_FILTRO + ["busca_arquivo", "_busca_anterior"]:
        st.session_state.pop(k, None)
    st.session_state["pag_arquivos"] = 0


def _tem_filtros_ativos() -> bool:
    """Retorna True se há algum filtro aplicado ou busca textual ativa."""
    return any([
        st.session_state.get("filtro_data_ini"),
        st.session_state.get("filtro_data_fim"),
        st.session_state.get("filtro_apenas_atualizados"),
        st.session_state.get("filtro_ordenar_por", "Nome") != "Nome",
        not st.session_state.get("filtro_ordem_asc", True),
        st.session_state.get("busca_arquivo", ""),
    ])


def _caption_filtros_ativos() -> None:
    """Exibe uma linha de caption descrevendo os filtros ativos, se houver."""
    partes = []
    busca  = st.session_state.get("busca_arquivo", "")
    ini    = st.session_state.get("filtro_data_ini")
    fim    = st.session_state.get("filtro_data_fim")
    apenas = st.session_state.get("filtro_apenas_atualizados", False)
    ord_p  = st.session_state.get("filtro_ordenar_por", "Nome")
    asc    = st.session_state.get("filtro_ordem_asc", True)

    if busca:        partes.append(f'busca: "{busca}"')
    if ini:          partes.append(f"de {ini.strftime('%d/%m/%Y')}")
    if fim:          partes.append(f"até {fim.strftime('%d/%m/%Y')}")
    if apenas:       partes.append("só atualizados")
    if ord_p != "Nome" or not asc:
        partes.append(f"ordem: {ord_p} {'↑' if asc else '↓'}")

    if partes:
        st.caption("Filtros ativos: " + "  ·  ".join(partes))


# ── Lógica de filtragem e ordenação ──────────────────────────────────────────

def _aplicar_filtros(
    arquivos: list,
    busca: str,
    data_ini,
    data_fim,
    apenas_atualizados: bool,
    ordenar_por: str,
    ordem_asc: bool,
) -> list:
    resultado = arquivos

    if busca:
        termo     = busca.lower()
        resultado = [
            a for a in resultado
            if termo in a["nome"].lower() or termo in (a.get("descricao") or "").lower()
        ]

    if data_ini:
        resultado = [a for a in resultado if a["criado_em"].date() >= data_ini]
    if data_fim:
        resultado = [a for a in resultado if a["criado_em"].date() <= data_fim]

    if apenas_atualizados:
        resultado = [
            a for a in resultado
            if (a["atualizado_em"] - a["criado_em"]) > timedelta(seconds=1)
        ]

    chave = {
        "Nome":          lambda a: a["nome"].lower(),
        "Data de envio": lambda a: a["criado_em"],
        "Tamanho":       lambda a: a["tamanho_bytes"],
        "Linhas":        lambda a: a.get("num_linhas") or 0,
        "Atualização":   lambda a: a["atualizado_em"],
    }.get(ordenar_por)
    if chave:
        resultado = sorted(resultado, key=chave, reverse=not ordem_asc)

    return resultado


# ── Helpers de listagem ───────────────────────────────────────────────────────

def _preparar_zip(ids: list, usuario_id: int):
    buf = io.BytesIO()
    n   = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arq_id in ids:
            conteudo, nome = _buscar_conteudo(arq_id, usuario_id)
            if conteudo:
                zf.writestr(nome, conteudo)
                n += 1

    if n == 0:
        st.error("Nenhum arquivo pôde ser compactado.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state["zip_pronto"] = (buf.getvalue(), f"logs_{ts}.zip", n)
    st.rerun()


def _controles_paginacao(pagina: int, n_paginas: int):
    if n_paginas <= 1:
        return

    st.divider()
    col_prev, col_info, col_next = st.columns([2, 3, 2])
    if col_prev.button("◀  Anterior", disabled=pagina == 0, use_container_width=True, key="pag_prev"):
        st.session_state["pag_arquivos"] = pagina - 1
        st.rerun()
    col_info.button(
        f"Página {pagina + 1} de {n_paginas}",
        disabled=True, use_container_width=True, key="pag_info",
    )
    if col_next.button("Próxima  ▶", disabled=pagina >= n_paginas - 1, use_container_width=True, key="pag_next"):
        st.session_state["pag_arquivos"] = pagina + 1
        st.rerun()


def _linha_arquivo(arq: dict, usuario_id: int, gen: int):
    st.divider()
    cols = st.columns([0.5, 4, 2.5, 1.5, 3])

    cols[0].checkbox(
        "Selecionar", value=arq["id"] in st.session_state.get("selecionados", set()),
        key=f"chk_{arq['id']}_{gen}", on_change=_toggle_chk,
        kwargs={"arq_id": arq["id"], "gen": gen}, label_visibility="collapsed",
    )

    cols[1].write(f"**{arq['nome']}**")
    linhas = arq.get("num_linhas")
    partes = []
    if linhas:
        partes.append(f"{linhas:,} linhas")
    partes.append(_formatar_bytes(arq["tamanho_bytes"]))
    partes.append(arq["criado_em"].strftime("%d/%m/%Y %H:%M"))
    cols[1].caption("  ·  ".join(partes))

    cols[2].write(arq.get("descricao") or "—")

    foi_atualizado = (arq["atualizado_em"] - arq["criado_em"]) > timedelta(seconds=1)
    if foi_atualizado:
        cols[3].write(arq["atualizado_em"].strftime("%d/%m/%Y"))
        cols[3].caption(arq["atualizado_em"].strftime("%H:%M"))
    else:
        cols[3].write("—")

    with cols[4]:
        c1, c2, c3 = st.columns(3)

        conteudo, nome_arq = _buscar_conteudo(arq["id"], usuario_id)
        if conteudo:
            c1.download_button(
                "Baixar", data=conteudo, file_name=nome_arq, mime="text/plain",
                key=f"dl_{arq['id']}", use_container_width=True,
            )

        if c2.button("Editar", key=f"ed_{arq['id']}", use_container_width=True):
            st.session_state["editando_id"] = arq["id"]
            st.rerun()

        if st.session_state.get("confirm_delete") != arq["id"]:
            if c3.button("Excluir", key=f"del_{arq['id']}", use_container_width=True):
                st.session_state["confirm_delete"] = arq["id"]
                st.rerun()

    if st.session_state.get("confirm_delete") == arq["id"]:
        st.warning(f"Tem certeza que deseja excluir **{arq['nome']}**?")
        cc1, cc2 = st.columns(2)
        if cc1.button("✓ Confirmar", key=f"conf_{arq['id']}", type="primary"):
            ok, msg = ArquivoController.deletar(arq["id"], usuario_id)
            st.session_state.get("selecionados", set()).discard(arq["id"])
            st.cache_data.clear()
            st.session_state.pop("confirm_delete", None)
            if ok:
                set_toast(msg)
            else:
                st.error(msg)
            st.rerun()
        if cc2.button("✗ Cancelar", key=f"canc_{arq['id']}"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()


def _formatar_bytes(n: int) -> str:
    if n < 1_024:
        return f"{n} B"
    if n < 1_024 ** 2:
        return f"{n / 1_024:.1f} KB"
    return f"{n / 1_024 ** 2:.1f} MB"
