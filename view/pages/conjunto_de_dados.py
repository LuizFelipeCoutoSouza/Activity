# -----------------------------------------------------------------------------
# Activity — Sistema web para análise de dados de actigrafia
#
# Monografia apresentada à Escola de Artes, Ciências e Humanidades da
# Universidade de São Paulo, como parte dos requisitos exigidos na disciplina
# ACH2017 — Projeto Supervisionado ou de Graduação I, para obtenção do título
# de Bacharelado em Sistemas de Informação.
#
# Modalidade: TCC curto (1 semestre) — em grupo
#
# Autores:
#   Laila Malafaia Vieira
#   Luiz Felipe Couto de Souza
#
# Orientadora: Profa. Dra. Ana Amélia Benedito Silva
#
# São Paulo, 2026
# -----------------------------------------------------------------------------

"""Página de gerenciamento dos arquivos `.txt` do usuário.

Cobre upload, listagem paginada com busca e filtros, edição, exclusão (individual
e em massa) e download (individual e compactado).

Os filtros seguem o padrão *draft/aplicado*: as chaves `_d_*` guardam o estado
dos widgets antes de "Aplicar", e as chaves `filtro_*` guardam o estado
efetivamente usado na listagem. Isso evita refiltrar a cada interação com os
widgets.
"""

import base64
from datetime import timedelta

import streamlit as st
import streamlit.components.v1 as components
from st_keyup import st_keyup
from controller.arquivo_controller import ArquivoController
from view.ui import set_toast, render_toast, get_usuario_id, paginacao

POR_PAGINA   = 5
OPCOES_ORDEM = ["Nome", "Data de envio", "Tamanho", "Linhas", "Atualização"]

_CHAVES_DRAFT  = ["_d_data_ini", "_d_data_fim", "_d_ordenar_por", "_d_ordem_asc", "_d_apenas_atualizados"]
_CHAVES_FILTRO = ["filtro_data_ini", "filtro_data_fim", "filtro_ordenar_por", "filtro_ordem_asc", "filtro_apenas_atualizados"]


# ── Cache de conteúdo ─────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _buscar_conteudo(arquivo_id: int, usuario_id: int) -> tuple:
    """Recupera o conteúdo de um arquivo para download (cacheado).

    Args:
        arquivo_id: Id do arquivo.
        usuario_id: Id do usuário dono.

    Returns:
        tuple: `(conteudo, nome)`; ou `(None, mensagem)` se não encontrado.
    """
    return ArquivoController.baixar(arquivo_id, usuario_id)


# ── Callback de checkbox ──────────────────────────────────────────────────────

def _toggle_chk(arq_id: int, gen: int):
    """Sincroniza o conjunto de selecionados ao marcar/desmarcar um checkbox.

    Args:
        arq_id: Id do arquivo associado ao checkbox.
        gen: Geração atual dos checkboxes, usada para compor a key e forçar a
            recriação dos widgets após operações em massa.
    """
    key = f"chk_{arq_id}_{gen}"
    sel = st.session_state.setdefault("selecionados", set())
    if st.session_state.get(key, False):
        sel.add(arq_id)
    else:
        sel.discard(arq_id)


# ── Dialog de edição ──────────────────────────────────────────────────────────

@st.dialog("Editar arquivo")
def _dialogo_editar(arquivo_id: int, usuario_id: int):
    """Exibe o diálogo de edição de um arquivo (metadados e substituição).

    Permite alterar nome e descrição e, opcionalmente, substituir o conteúdo por
    um novo `.txt`. Ao salvar, escolhe entre substituir o conteúdo ou apenas os
    metadados conforme um novo arquivo tenha sido enviado.

    Args:
        arquivo_id: Id do arquivo a editar.
        usuario_id: Id do usuário dono.
    """
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
        help="A extensão .txt é adicionada automaticamente ao salvar.",
    )
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
    if col1.button("Salvar", type="primary", width="stretch"):
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

    if col2.button("Cancelar", width="stretch"):
        st.session_state.pop("editando_id", None)
        st.rerun()


# ── Diálogos de exclusão ──────────────────────────────────────────────────────

@st.dialog("Excluir arquivo")
def _dialogo_excluir(arquivo_id: int, usuario_id: int, nome: str):
    """Exibe o diálogo de confirmação de exclusão de um arquivo.

    Ao confirmar, remove o arquivo, descarta-o da seleção, limpa o cache de
    conteúdo e agenda o toast de resultado.

    Args:
        arquivo_id: Id do arquivo a excluir.
        usuario_id: Id do usuário dono.
        nome: Nome do arquivo, exibido na confirmação.
    """
    st.write(f"Tem certeza que deseja excluir **{nome}**?")
    st.caption("Esta ação não pode ser desfeita.")
    col1, col2 = st.columns(2)
    if col1.button("Excluir", type="primary", width="stretch"):
        ok, msg = ArquivoController.deletar(arquivo_id, usuario_id)
        st.session_state.get("selecionados", set()).discard(arquivo_id)
        st.cache_data.clear()
        st.session_state.pop("confirm_delete", None)
        set_toast(msg) if ok else st.error(msg)
        st.rerun()
    if col2.button("Cancelar", width="stretch"):
        st.session_state.pop("confirm_delete", None)
        st.rerun()


@st.dialog("Excluir arquivos")
def _dialogo_excluir_em_massa(ids: list, usuario_id: int, nomes: list):
    """Exibe o diálogo de confirmação de exclusão em massa.

    Mostra uma prévia de até cinco nomes e, ao confirmar, remove todos os
    arquivos, atualiza a seleção, incrementa a geração de checkboxes e limpa o
    cache.

    Args:
        ids: Ids dos arquivos a excluir.
        usuario_id: Id do usuário dono.
        nomes: Nomes dos arquivos (para a prévia).
    """
    n = len(ids)
    st.write(f"Tem certeza que deseja excluir **{n}** arquivo(s)?")
    preview = nomes[:5]
    st.markdown("\n".join(f"- {nome}" for nome in preview) + (f"\n- … e mais {n - 5}" if n > 5 else ""))
    st.caption("Esta ação não pode ser desfeita.")
    col1, col2 = st.columns(2)
    if col1.button(f"Excluir {n}", type="primary", width="stretch"):
        for arq_id in ids:
            ArquivoController.deletar(arq_id, usuario_id)
        st.session_state["selecionados"] -= set(ids)
        st.session_state["chk_gen"] += 1
        st.cache_data.clear()
        st.session_state.pop("bulk_delete_ids", None)
        set_toast(f"{n} arquivo(s) excluído(s).")
        st.rerun()
    if col2.button("Cancelar", width="stretch"):
        st.session_state.pop("bulk_delete_ids", None)
        st.rerun()


# ── Página principal ──────────────────────────────────────────────────────────

def conjunto_de_dados_page():
    """Renderiza a página de conjunto de dados.

    Aplica o guard de autenticação, processa os diálogos pendentes (edição e
    exclusões), exibe métricas-resumo e monta as abas de listagem e de upload.
    """
    st.title("🗃️ Conjunto de dados")

    usuario_id = get_usuario_id()
    if not usuario_id:
        return

    render_toast()

    arquivos = ArquivoController.listar(usuario_id)

    if "editando_id" in st.session_state:
        _dialogo_editar(st.session_state["editando_id"], usuario_id)

    if "confirm_delete" in st.session_state:
        arq_id = st.session_state["confirm_delete"]
        arquivo = next((a for a in arquivos if a["id"] == arq_id), None)
        if arquivo:
            _dialogo_excluir(arq_id, usuario_id, arquivo["nome"])
        else:
            st.session_state.pop("confirm_delete", None)

    if "bulk_delete_ids" in st.session_state:
        ids_del   = st.session_state["bulk_delete_ids"]
        nomes_del = [a["nome"] for a in arquivos if a["id"] in ids_del]
        _dialogo_excluir_em_massa(ids_del, usuario_id, nomes_del)

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
    """Resume os resultados de um lote de uploads em uma única notificação.

    Args:
        msgs: Lista de pares `(ok, mensagem)`, um por arquivo enviado.

    Returns:
        tuple[str, str]: `(tipo, texto)`, onde `tipo` é ``"success"``,
        ``"error"`` ou ``"warning"`` conforme o resultado agregado.
    """
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
    """Renderiza a aba de envio de arquivos.

    Aceita um ou vários `.txt`, com descrição por arquivo, e processa o lote
    exibindo um resumo. Um contador de geração nas keys dos widgets força a
    limpeza do uploader após cada envio.

    Args:
        usuario_id: Id do usuário dono.
    """
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

        st.session_state["upload_msg"]     = _resumir_upload(msgs)
        st.session_state["upload_counter"] = counter + 1
        st.session_state["pag_arquivos"]   = 0
        st.rerun()


# ── Listagem ──────────────────────────────────────────────────────────────────

def _secao_listagem(usuario_id: int, arquivos: list):
    """Renderiza a aba de listagem de arquivos.

    Aplica filtros e ordenação, pagina o resultado, oferece seleção em massa
    (download compactado e exclusão) e dispara o download automático do ZIP
    pronto. Mantém o conjunto de selecionados coerente com os arquivos atuais.

    Args:
        usuario_id: Id do usuário dono.
        arquivos: Lista de metadados dos arquivos do usuário.
    """
    n = len(arquivos)

    if not arquivos:
        st.subheader("Meus arquivos (0)")
        st.info("Nenhum arquivo enviado ainda. Use o painel acima para fazer upload.")
        return

    ids_atuais = {arq["id"] for arq in arquivos}
    sel: set   = st.session_state.setdefault("selecionados", set())
    sel        &= ids_atuais
    gen: int   = st.session_state.setdefault("chk_gen", 0)

    # Dispara download automático após ZIP gerado
    if "zip_pronto" in st.session_state:
        zip_bytes, zip_nome, n_zip = st.session_state.pop("zip_pronto")
        b64 = base64.b64encode(zip_bytes).decode()
        components.html(
            f"""<script>
            (function() {{
                var a = window.parent.document.createElement('a');
                a.href = 'data:application/zip;base64,{b64}';
                a.download = '{zip_nome}';
                window.parent.document.body.appendChild(a);
                a.click();
                window.parent.document.body.removeChild(a);
            }})();
            </script>""",
            height=0,
        )
        st.toast(f"{n_zip} arquivo(s) compactado(s). Download iniciado.", icon="✅")

    _painel_filtros()

    busca     = st.session_state.get("busca_arquivo", "")
    data_ini  = st.session_state.get("filtro_data_ini")
    data_fim  = st.session_state.get("filtro_data_fim")
    apenas_at = st.session_state.get("filtro_apenas_atualizados", False)
    ordenar   = st.session_state.get("filtro_ordenar_por", "Nome")
    asc       = st.session_state.get("filtro_ordem_asc", True)

    if busca != st.session_state.get("_busca_anterior", ""):
        st.session_state["pag_arquivos"]    = 0
        st.session_state["_busca_anterior"] = busca

    arquivos_filtrados = _aplicar_filtros(arquivos, busca, data_ini, data_fim, apenas_at, ordenar, asc)
    n_filtrado = len(arquivos_filtrados)

    n_paginas = max(1, (n_filtrado + POR_PAGINA - 1) // POR_PAGINA)
    pagina    = min(max(st.session_state.get("pag_arquivos", 0), 0), n_paginas - 1)
    st.session_state["pag_arquivos"] = pagina
    inicio          = pagina * POR_PAGINA
    arquivos_pagina = arquivos_filtrados[inicio : inicio + POR_PAGINA]

    # Título + controles de seleção na mesma linha
    ha_filtros = any([busca, data_ini, data_fim, apenas_at])
    if ha_filtros:
        titulo = f"Meus arquivos — {n_filtrado} de {n} resultado(s)"
    elif n_paginas > 1:
        titulo = f"Meus arquivos — página {pagina + 1} de {n_paginas} ({n} no total)"
    else:
        titulo = f"Meus arquivos ({n})"

    n_sel = len(sel)
    col_titulo, col_sel_all, col_desel = st.columns([5, 1.5, 1.5])
    col_titulo.subheader(titulo)
    if col_sel_all.button("Selecionar todos", width="stretch", key="btn_sel_all"):
        st.session_state["selecionados"] = ids_atuais.copy()
        st.session_state["chk_gen"]      = gen + 1
        st.rerun()
    if col_desel.button("Limpar seleção", width="stretch", key="btn_des_all", disabled=n_sel == 0):
        st.session_state["selecionados"] = set()
        st.session_state["chk_gen"]      = gen + 1
        st.rerun()

    if n_filtrado == 0:
        st.info("Nenhum arquivo corresponde aos filtros aplicados.")
        return

    # Barra de ações em massa — visível apenas quando há itens selecionados
    if n_sel > 0:
        with st.container(border=True):
            c_info, c_dl, c_del = st.columns([4, 2, 2])
            c_info.markdown(f"**{n_sel}** arquivo(s) selecionado(s)")
            if c_dl.button("⬇️  Download", type="primary", width="stretch", key="btn_bulk_dl"):
                with st.spinner("Compactando arquivos..."):
                    zip_bytes, zip_nome, n = ArquivoController.gerar_zip(list(sel), usuario_id)
                if zip_bytes:
                    st.session_state["zip_pronto"] = (zip_bytes, zip_nome, n)
                else:
                    st.error("Nenhum arquivo pôde ser compactado.")
                st.rerun()
            if c_del.button("🗑️  Excluir", width="stretch", key="btn_bulk_del"):
                st.session_state["bulk_delete_ids"] = list(sel)
                st.rerun()

    cols_h = st.columns([0.5, 4, 2.5, 1.8, 1, 1, 1])
    for col, h in zip(cols_h, ["", "Nome do arquivo", "Descrição", "Atualização", "", "", ""]):
        if h:
            col.markdown(f"**{h}**")

    for arq in arquivos_pagina:
        _linha_arquivo(arq, usuario_id, gen)

    paginacao(pagina, n_paginas, "pag_arquivos")


# ── Painel de filtros ─────────────────────────────────────────────────────────

def _painel_filtros() -> None:
    """Renderiza a busca reativa e o expander de filtros (padrão draft/aplicado).

    A busca textual fica sempre visível; os filtros de data, ordenação e
    checkboxes ficam em um expander e só passam a valer ao clicar em "Aplicar".
    """
    _init_draft()

    st_keyup(
        "Buscar por nome ou descrição",
        placeholder="Nome do arquivo ou trecho da descrição...",
        key="busca_arquivo",
    )

    tem_filtros = _tem_filtros_ativos()
    label_exp   = "Filtros" if not tem_filtros else "Filtros (ativos)"
    with st.expander(label_exp):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.date_input("De", key="_d_data_ini", format="DD/MM/YYYY")
        with c2:
            st.date_input("Até", key="_d_data_fim", format="DD/MM/YYYY")
        with c3:
            st.selectbox("Ordenar por", OPCOES_ORDEM, key="_d_ordenar_por")

        c4, c5, c6, c7 = st.columns([2, 2, 1.5, 1.5])
        c4.checkbox("Crescente", key="_d_ordem_asc")
        c5.checkbox("Só atualizados", key="_d_apenas_atualizados")
        if c6.button("Aplicar", type="primary", width="stretch"):
            _commit_draft()
            st.rerun()
        if c7.button("Limpar", width="stretch", disabled=not tem_filtros):
            _limpar_filtros()
            st.rerun()

    _caption_filtros_ativos()


# ── Estado dos filtros (draft / aplicado) ─────────────────────────────────────

def _init_draft() -> None:
    """Inicializa os widgets de filtro (chaves `_d_*`) a partir do estado aplicado.

    Garante que, ao abrir o painel, os widgets reflitam os filtros atualmente em
    vigor.
    """
    st.session_state.setdefault("_d_data_ini",           st.session_state.get("filtro_data_ini"))
    st.session_state.setdefault("_d_data_fim",           st.session_state.get("filtro_data_fim"))
    st.session_state.setdefault("_d_ordenar_por",        st.session_state.get("filtro_ordenar_por", "Nome"))
    st.session_state.setdefault("_d_ordem_asc",          st.session_state.get("filtro_ordem_asc", True))
    st.session_state.setdefault("_d_apenas_atualizados", st.session_state.get("filtro_apenas_atualizados", False))


def _commit_draft() -> None:
    """Promove o estado dos widgets (`_d_*`) para os filtros aplicados (`filtro_*`).

    Chamado ao clicar em "Aplicar"; também reseta a paginação para a primeira
    página.
    """
    st.session_state["filtro_data_ini"]           = st.session_state.get("_d_data_ini")
    st.session_state["filtro_data_fim"]           = st.session_state.get("_d_data_fim")
    st.session_state["filtro_ordenar_por"]        = st.session_state.get("_d_ordenar_por", "Nome")
    st.session_state["filtro_ordem_asc"]          = st.session_state.get("_d_ordem_asc", True)
    st.session_state["filtro_apenas_atualizados"] = st.session_state.get("_d_apenas_atualizados", False)
    st.session_state["pag_arquivos"] = 0


def _limpar_filtros() -> None:
    """Remove todos os filtros (draft e aplicados), a busca e reseta a paginação."""
    for k in _CHAVES_DRAFT + _CHAVES_FILTRO + ["busca_arquivo", "_busca_anterior"]:
        st.session_state.pop(k, None)
    st.session_state["pag_arquivos"] = 0


def _tem_filtros_ativos() -> bool:
    """Indica se há algum filtro aplicado ou busca em vigor.

    Returns:
        bool: True se data, "só atualizados", ordenação não padrão ou busca
        estiverem ativos.
    """
    return any([
        st.session_state.get("filtro_data_ini"),
        st.session_state.get("filtro_data_fim"),
        st.session_state.get("filtro_apenas_atualizados"),
        st.session_state.get("filtro_ordenar_por", "Nome") != "Nome",
        not st.session_state.get("filtro_ordem_asc", True),
        st.session_state.get("busca_arquivo", ""),
    ])


def _caption_filtros_ativos() -> None:
    """Exibe um resumo textual dos filtros e da busca atualmente ativos."""
    partes = []
    busca  = st.session_state.get("busca_arquivo", "")
    ini    = st.session_state.get("filtro_data_ini")
    fim    = st.session_state.get("filtro_data_fim")
    apenas = st.session_state.get("filtro_apenas_atualizados", False)
    ord_p  = st.session_state.get("filtro_ordenar_por", "Nome")
    asc    = st.session_state.get("filtro_ordem_asc", True)

    if busca:  partes.append(f'busca: "{busca}"')
    if ini:    partes.append(f"de {ini.strftime('%d/%m/%Y')}")
    if fim:    partes.append(f"até {fim.strftime('%d/%m/%Y')}")
    if apenas: partes.append("só atualizados")
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
    """Aplica busca, filtros de data, "só atualizados" e ordenação à lista.

    Args:
        arquivos: Lista de metadados dos arquivos.
        busca: Termo de busca por nome ou descrição (case-insensitive).
        data_ini: Data inicial (inclusive) de criação, ou None.
        data_fim: Data final (inclusive) de criação, ou None.
        apenas_atualizados: Se True, mantém só arquivos editados após o envio.
        ordenar_por: Critério de ordenação (chave de `OPCOES_ORDEM`).
        ordem_asc: Se True, ordena de forma crescente; senão, decrescente.

    Returns:
        list: Lista filtrada e ordenada (cópia; a entrada não é modificada).
    """
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


# ── Linha de arquivo ──────────────────────────────────────────────────────────

def _linha_arquivo(arq: dict, usuario_id: int, gen: int):
    """Renderiza uma linha da listagem de arquivos (seleção, dados e ações).

    Args:
        arq: Dicionário de metadados do arquivo.
        usuario_id: Id do usuário dono (usado no download).
        gen: Geração atual dos checkboxes, para compor a key de seleção.
    """
    st.divider()
    # Larguras proporcionais ao cabeçalho [0.5, 4, 2.5, 1.8, 3]: os 3 botões finais somam 3.
    cols = st.columns([0.5, 4, 2.5, 1.8, 1, 1, 1])

    cols[0].checkbox(
        "Selecionar", value=arq["id"] in st.session_state.get("selecionados", set()),
        key=f"chk_{arq['id']}_{gen}", on_change=_toggle_chk,
        kwargs={"arq_id": arq["id"], "gen": gen}, label_visibility="collapsed",
    )

    cols[1].write(f"**{arq['nome']}**")
    partes = []
    if linhas := arq.get("num_linhas"):
        partes.append(f"{linhas:,} linhas")
    partes.append(_formatar_bytes(arq["tamanho_bytes"]))
    partes.append(arq["criado_em"].strftime("%d/%m/%Y"))
    cols[1].caption("  ·  ".join(partes))

    cols[2].write(arq.get("descricao") or "—")

    foi_atualizado = (arq["atualizado_em"] - arq["criado_em"]) > timedelta(seconds=1)
    cols[3].write(arq["atualizado_em"].strftime("%d/%m/%Y %H:%M") if foi_atualizado else "—")

    conteudo, nome_arq = _buscar_conteudo(arq["id"], usuario_id)
    if conteudo:
        cols[4].download_button(
            "Baixar", data=conteudo, file_name=nome_arq, mime="text/plain",
            key=f"dl_{arq['id']}", width="stretch",
        )

    if cols[5].button("Editar", key=f"ed_{arq['id']}", width="stretch"):
        st.session_state["editando_id"] = arq["id"]
        st.rerun()

    if cols[6].button("Excluir", key=f"del_{arq['id']}", width="stretch"):
        st.session_state["confirm_delete"] = arq["id"]
        st.rerun()


# ── Helper ────────────────────────────────────────────────────────────────────

def _formatar_bytes(n: int) -> str:
    """Formata um tamanho em bytes como texto legível (B, KB ou MB).

    Args:
        n: Tamanho em bytes.

    Returns:
        str: Tamanho com a unidade apropriada (ex.: ``"1.5 MB"``).
    """
    if n < 1_024:
        return f"{n} B"
    if n < 1_024 ** 2:
        return f"{n / 1_024:.1f} KB"
    return f"{n / 1_024 ** 2:.1f} MB"
