import io
import zipfile
from datetime import datetime

import streamlit as st
from controller.ArquivoController import ArquivoController

POR_PAGINA = 5


# ── Cache de conteúdo ─────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _buscar_conteudo(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.baixar(arquivo_id, usuario_id)


# ── Callback de checkbox individual ──────────────────────────────────────────
# Chamado pelo Streamlit antes do rerun quando o usuário clica num checkbox.
# Lê o novo valor da widget key e sincroniza com o set "selecionados".

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
    arquivo = next((a for a in arquivos if a["id"] == arquivo_id), None)

    if not arquivo:
        st.error("Arquivo não encontrado.")
        return

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
            ok, msg = ArquivoController.substituir_arquivo(
                arquivo_id, usuario_id, novo_nome, nova_desc, novo_arq
            )
        else:
            ok, msg = ArquivoController.atualizar_metadados(
                arquivo_id, usuario_id, novo_nome, nova_desc
            )

        if ok:
            st.cache_data.clear()
            st.session_state.pop("editando_id", None)
            st.rerun()
        else:
            st.error(msg)

    if col2.button("Cancelar", use_container_width=True):
        st.session_state.pop("editando_id", None)
        st.rerun()


# ── Página principal ──────────────────────────────────────────────────────────

def conjunto_de_dados_page():
    st.title("🗃️ Conjunto de dados")

    usuario = st.session_state.get("usuario", {})
    usuario_id = usuario.get("id")

    if not usuario_id:
        st.info("Esta funcionalidade está disponível apenas para usuários cadastrados com e-mail.")
        return

    if "editando_id" in st.session_state:
        _dialogo_editar(st.session_state["editando_id"], usuario_id)

    _secao_upload(usuario_id)
    st.divider()
    _secao_listagem(usuario_id)


# ── Upload ────────────────────────────────────────────────────────────────────

def _resumir_upload(msgs: list) -> tuple:
    """Consolida N resultados de upload em (tipo, texto) para exibir uma única mensagem."""
    n = len(msgs)
    n_ok = sum(1 for ok, _ in msgs if ok)
    n_err = n - n_ok

    if n_err == 0:
        texto = msgs[0][1] if n == 1 else f"{n_ok} arquivo(s) enviado(s) com sucesso."
        return "success", texto

    if n_ok == 0:
        texto = msgs[0][1] if n == 1 else "Nenhum arquivo foi enviado. Verifique se os nomes já existem ou se os arquivos são .txt."
        return "error", texto

    return "warning", f"{n_ok} de {n} arquivo(s) enviado(s). {n_err} ignorado(s) — nome duplicado ou formato inválido."


def _secao_upload(usuario_id: int):
    counter = st.session_state.get("upload_counter", 0)

    # Mensagem do upload anterior (exibida após rerun, fora do spinner)
    if "upload_msg" in st.session_state:
        tipo, texto = st.session_state.pop("upload_msg")
        getattr(st, tipo)(texto)

    with st.expander("⬆️  Enviar arquivos", expanded=False):
        # Chaves dinâmicas garantem que a widget é recriada limpa após cada upload
        arquivos = st.file_uploader(
            "Selecione um ou mais arquivos .txt",
            type=["txt"],
            accept_multiple_files=True,
            key=f"uploader_{counter}",
        )
        descricao = st.text_input(
            "Descrição (opcional)",
            max_chars=200,
            placeholder="Ex: Coleta paciente João — nov/2025",
            key=f"desc_{counter}",
        )

        if st.button("Enviar", type="primary", disabled=not arquivos):
            msgs = []
            with st.spinner("Enviando..."):
                if len(arquivos) == 1:
                    ok, msg = ArquivoController.fazer_upload(usuario_id, arquivos[0], descricao)
                    msgs.append((ok, msg))
                else:
                    resultados, _ = ArquivoController.fazer_upload_em_massa(
                        usuario_id, arquivos, descricao
                    )
                    msgs.extend((ok, msg) for _, ok, msg in resultados)

            st.session_state["upload_msg"] = _resumir_upload(msgs)
            st.session_state["upload_counter"] = counter + 1
            st.session_state["pag_arquivos"] = 0
            st.rerun()


# ── Listagem ──────────────────────────────────────────────────────────────────

def _secao_listagem(usuario_id: int):
    arquivos = ArquivoController.listar(usuario_id)
    n = len(arquivos)
    st.subheader(f"Meus arquivos ({n})")

    if not arquivos:
        st.info("Nenhum arquivo enviado ainda. Use o painel acima para fazer upload.")
        return

    ids_atuais = {arq["id"] for arq in arquivos}

    # Inicializa e limpa IDs de arquivos que já não existem
    sel: set = st.session_state.setdefault("selecionados", set())
    sel &= ids_atuais

    gen: int = st.session_state.setdefault("chk_gen", 0)

    # Zip pronto para download
    if "zip_pronto" in st.session_state:
        dados_zip, nome_zip, n_zip = st.session_state.pop("zip_pronto")
        st.success(f"{n_zip} arquivo(s) compactado(s).")
        st.download_button(
            f"⬇️  Baixar  {nome_zip}",
            data=dados_zip,
            file_name=nome_zip,
            mime="application/zip",
            key="dl_zip_final",
            use_container_width=True,
        )

    n_sel = len(sel)

    # Controles de seleção
    c1, c2, *_ = st.columns([2.5, 2.5, 6])
    if c1.button("Selecionar todos", use_container_width=True, key="btn_sel_all"):
        st.session_state["selecionados"] = ids_atuais.copy()
        st.session_state["chk_gen"] = gen + 1
        st.rerun()
    if c2.button("Limpar seleção", use_container_width=True, key="btn_des_all", disabled=n_sel == 0):
        st.session_state["selecionados"] = set()
        st.session_state["chk_gen"] = gen + 1
        st.rerun()

    # Ações em massa
    if n_sel > 0:
        ba1, ba2 = st.columns(2)
        if ba1.button(
            f"⬇️  Download ({n_sel} arquivo(s))",
            type="primary",
            use_container_width=True,
            key="btn_bulk_dl",
        ):
            _preparar_zip(list(sel), usuario_id)

        if ba2.button(
            f"🗑️  Excluir ({n_sel} arquivo(s))",
            use_container_width=True,
            key="btn_bulk_del",
        ):
            st.session_state["bulk_delete_ids"] = list(sel)

    # Confirmação de exclusão em massa
    if "bulk_delete_ids" in st.session_state:
        ids_del = st.session_state["bulk_delete_ids"]
        nomes_del = [a["nome"] for a in arquivos if a["id"] in ids_del]
        preview = ", ".join(nomes_del[:3]) + (" ..." if len(nomes_del) > 3 else "")
        st.warning(f"Excluir **{len(ids_del)}** arquivo(s)? ({preview})")
        cd1, cd2 = st.columns(2)
        if cd1.button("✓ Confirmar exclusão", type="primary", key="conf_bulk_del", use_container_width=True):
            for arq_id in ids_del:
                ArquivoController.deletar(arq_id, usuario_id)
            st.session_state["selecionados"] -= set(ids_del)
            st.session_state["chk_gen"] = st.session_state["chk_gen"] + 1
            st.cache_data.clear()
            st.session_state.pop("bulk_delete_ids", None)
            st.success(f"{len(ids_del)} arquivo(s) excluído(s).")
            st.rerun()
        if cd2.button("✗ Cancelar", key="canc_bulk_del", use_container_width=True):
            st.session_state.pop("bulk_delete_ids", None)
            st.rerun()

    # Paginação
    n_paginas = max(1, (n + POR_PAGINA - 1) // POR_PAGINA)
    pagina = min(max(st.session_state.get("pag_arquivos", 0), 0), n_paginas - 1)
    st.session_state["pag_arquivos"] = pagina
    inicio = pagina * POR_PAGINA
    fim = min(inicio + POR_PAGINA, n)
    arquivos_pagina = arquivos[inicio:fim]

    # Cabeçalho
    cols_h = st.columns([0.5, 3, 1.5, 1.5, 1.5, 2, 2])
    for col, h in zip(cols_h, ["", "Nome / Descrição", "Linhas", "Tamanho", "Encoding", "Enviado em", "Ações"]):
        col.markdown(f"**{h}**")

    for arq in arquivos_pagina:
        _linha_arquivo(arq, usuario_id, gen)

    _controles_paginacao(pagina, n_paginas, n, inicio, fim)


def _controles_paginacao(pagina: int, n_paginas: int, n_total: int, inicio: int, fim: int):
    if n_paginas <= 1:
        return

    st.divider()
    col_prev, col_info, col_next = st.columns([1, 3, 1])

    if col_prev.button("◀  Anterior", disabled=pagina == 0, use_container_width=True, key="pag_prev"):
        st.session_state["pag_arquivos"] = pagina - 1
        st.rerun()

    col_info.markdown(
        f"Página **{pagina + 1}** de **{n_paginas}** "
        f"&nbsp;·&nbsp; exibindo {inicio + 1}–{fim} de {n_total} arquivos"
    )

    if col_next.button("Próxima  ▶", disabled=pagina >= n_paginas - 1, use_container_width=True, key="pag_next"):
        st.session_state["pag_arquivos"] = pagina + 1
        st.rerun()


def _preparar_zip(ids: list, usuario_id: int):
    buf = io.BytesIO()
    n = 0
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


# ── Linha de arquivo ──────────────────────────────────────────────────────────

def _linha_arquivo(arq: dict, usuario_id: int, gen: int):
    st.divider()
    cols = st.columns([0.5, 3, 1.5, 1.5, 1.5, 2, 2])

    # Checkbox com chave versionada: evita conflito com estado interno do Streamlit
    cols[0].checkbox(
        "",
        value=arq["id"] in st.session_state.get("selecionados", set()),
        key=f"chk_{arq['id']}_{gen}",
        on_change=_toggle_chk,
        kwargs={"arq_id": arq["id"], "gen": gen},
        label_visibility="collapsed",
    )

    cols[1].write(f"**{arq['nome']}**")
    if arq.get("descricao"):
        cols[1].caption(arq["descricao"])

    linhas = arq.get("num_linhas")
    cols[2].write(f"{linhas:,}" if linhas else "—")
    cols[3].write(_formatar_bytes(arq["tamanho_bytes"]))
    cols[4].write(arq.get("encoding") or "—")
    cols[5].write(arq["criado_em"].strftime("%d/%m/%Y %H:%M"))

    with cols[6]:
        c1, c2, c3 = st.columns(3)

        dl_key = f"dl_pronto_{arq['id']}"
        if c1.button("⬇️", key=f"dl_{arq['id']}", help="Download"):
            st.session_state[dl_key] = True
            st.rerun()

        if c2.button("✏️", key=f"ed_{arq['id']}", help="Editar"):
            st.session_state["editando_id"] = arq["id"]
            st.rerun()

        if st.session_state.get("confirm_delete") != arq["id"]:
            if c3.button("🗑️", key=f"del_{arq['id']}", help="Excluir"):
                st.session_state["confirm_delete"] = arq["id"]
                st.rerun()

    # Download individual
    if st.session_state.get(dl_key):
        conteudo, nome = _buscar_conteudo(arq["id"], usuario_id)
        if conteudo:
            st.download_button(
                f"⬇️  Baixar  {nome}",
                data=conteudo,
                file_name=nome,
                mime="text/plain",
                key=f"dl_real_{arq['id']}",
                use_container_width=True,
            )
        st.session_state.pop(dl_key, None)

    # Confirmação de exclusão individual
    if st.session_state.get("confirm_delete") == arq["id"]:
        st.warning(f"Tem certeza que deseja excluir **{arq['nome']}**?")
        cc1, cc2 = st.columns(2)
        if cc1.button("✓ Confirmar", key=f"conf_{arq['id']}", type="primary"):
            ok, msg = ArquivoController.deletar(arq["id"], usuario_id)
            st.session_state.get("selecionados", set()).discard(arq["id"])
            st.cache_data.clear()
            st.session_state.pop("confirm_delete", None)
            (st.success if ok else st.error)(msg)
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