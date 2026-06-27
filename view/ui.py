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

"""Utilitários de UI compartilhados entre as views.

Reúne tudo que é reutilizável na camada de apresentação, para não duplicar código
nas páginas individuais: o enum de profissões, formatadores (CPF, telefone),
avaliação de força de senha, helpers de avatar/imagem, guard de autenticação,
paginação, toasts entre renders e os blocos de construção dos gráficos de
actigrafia (cores, constantes e as funções de `BaseRaw`/Plotly).
"""

from __future__ import annotations

import re
import base64
from datetime import date, datetime
from enum import Enum

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
from pyActigraphy.io import BaseRaw
from controller.arquivo_controller import ArquivoController


# ── Enums de domínio ──────────────────────────────────────────────────────────

class Profissao(str, Enum):
    """Profissões válidas para cadastro e edição de perfil.

    Herda de `str`, de modo que cada membro equivale ao seu próprio texto (ex.:
    `Profissao.MEDICO == "Médico"`), podendo ser usado diretamente em selectboxes
    e comparações com valores do banco.
    """
    MEDICO         = "Médico"
    ENFERMEIRO     = "Enfermeiro"
    FISIOTERAPEUTA = "Fisioterapeuta"
    PESQUISADOR    = "Pesquisador"
    ADMIN          = "Admin"

    @classmethod
    def opcoes(cls) -> list[str]:
        """Lista os valores das profissões para uso em selectbox.

        Returns:
            list[str]: Rótulos de todas as profissões, na ordem de declaração.
        """
        return [p.value for p in cls]


# ── Tamanhos de avatar (px) ───────────────────────────────────────────────────

AVATAR_NAV = 36   # navbar
AVATAR_SM  = 80   # cabeçalho de perfil
AVATAR_LG  = 120  # seção de foto


# ── Formatadores ──────────────────────────────────────────────────────────────

def fmt_cpf(cpf: str) -> str:
    """Formata um CPF como ``000.000.000-00``.

    Args:
        cpf: CPF com ou sem máscara.

    Returns:
        str: CPF formatado se houver 11 dígitos; caso contrário, a entrada
        original inalterada.
    """
    d = re.sub(r"\D", "", cpf or "")
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}" if len(d) == 11 else (cpf or "")


def fmt_telefone(tel: str) -> str:
    """Formata um telefone como ``(00) 00000-0000`` (celular) ou ``(00) 0000-0000`` (fixo).

    Args:
        tel: Telefone com ou sem máscara.

    Returns:
        str: Telefone formatado para 10 ou 11 dígitos; caso contrário, a entrada
        original inalterada.
    """
    d = re.sub(r"\D", "", tel or "")
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel or ""


# ── Força de senha ────────────────────────────────────────────────────────────

def forca_senha(senha: str) -> tuple[int, str, str]:
    """Avalia a força de uma senha por comprimento e variedade de caracteres.

    Pontua tamanho (>= 6 e >= 10), presença de letra maiúscula e presença de
    dígito ou caractere não alfanumérico.

    Args:
        senha: Senha em texto puro a avaliar.

    Returns:
        tuple[int, str, str]: `(score, label, emoji)`, com `score` de 0 a 4 e
        `label`/`emoji` correspondentes ao nível de força.
    """
    score = 0
    if len(senha) >= 6:  score += 1
    if len(senha) >= 10: score += 1
    if any(c.isupper() for c in senha):               score += 1
    if any(c.isdigit() or not c.isalnum() for c in senha): score += 1
    tabela = {
        0: ("🔴", "Muito fraca"), 1: ("🔴", "Fraca"),
        2: ("🟠", "Razoável"),    3: ("🟡", "Boa"),
        4: ("🟢", "Forte"),
    }
    emoji, label = tabela[score]
    return score, label, emoji


# ── Dados de sujeito (Condor) ────────────────────────────────────────────────

def rotulo_genero(valor: str | None) -> str:
    """Normaliza o campo `SUBJECT_GENDER` do Condor para um rótulo exibível.

    Args:
        valor: Valor bruto do gênero (ex.: ``"M"``, ``"F"``), ou None.

    Returns:
        str: ``"MASCULINO"``, ``"FEMININO"``, o próprio valor em maiúsculas para
        outros casos, ou ``"—"`` se vazio/None.
    """
    if not valor:
        return "—"
    inicial = valor.strip().upper()[:1]
    if inicial == "M":
        return "MASCULINO"
    if inicial == "F":
        return "FEMININO"
    return valor.strip().upper()


def calcular_idade(data_nascimento: str | None) -> str:
    """Calcula a idade a partir do campo `SUBJECT_DATE_OF_BIRTH` do Condor.

    Args:
        data_nascimento: Data de nascimento no formato ``DD/MM/YYYY``, ou None.

    Returns:
        str: Idade no formato ``"N anos"``; ``"—"`` se vazia ou em formato
        inválido.
    """
    if not data_nascimento:
        return "—"
    try:
        nascimento = datetime.strptime(data_nascimento.strip(), "%d/%m/%Y").date()
    except ValueError:
        return "—"
    hoje = date.today()
    idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
    return f"{idade} anos"


def coluna_numerica_utilizavel(df: pd.DataFrame, nome_coluna: str) -> pd.Series | None:
    """Retorna uma coluna como série numérica, se for utilizável.

    Args:
        df: DataFrame de origem.
        nome_coluna: Nome da coluna desejada.

    Returns:
        pandas.Series | None: A coluna convertida para numérica (valores não
        numéricos viram NaN) se existir e tiver ao menos um valor não nulo; None
        se a coluna estiver ausente ou for totalmente nula.
    """
    if nome_coluna not in df.columns:
        return None
    valores = pd.to_numeric(df[nome_coluna], errors="coerce")
    return valores if valores.notna().any() else None


# ── Gráficos de actigrafia ────────────────────────────────────────────────────
# Compartilhado entre view/pages/analises.py e view/pages/comparacao.py.

COR_LINHA = "#234cbe"
COR_LUZ = "#ffb433"
COR_TEMPERATURA = "#c43903"
COR_LEGENDA = "black"
COR_SOMBRA_NOITE = "rgba(25, 35, 90, 0.12)"
COR_SOMBRA_EVENTO = "rgba(34, 139, 34, 0.18)"

MODOS_ATIVIDADE = ["PIM", "TAT", "ZCM"]

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

LARGURA_EIXO_EXTRA = 0.08


@st.cache_data(ttl=120)
def carregar_actigrafia_cached(arquivo_id: int, usuario_id: int) -> tuple:
    """Versão cacheada de `ArquivoController.carregar_actigrafia`.

    Args:
        arquivo_id: Id do arquivo.
        usuario_id: Id do usuário dono.

    Returns:
        tuple[dict, pandas.DataFrame]: Par `(metadata, df)` do parser Condor.
    """
    return ArquivoController.carregar_actigrafia(arquivo_id, usuario_id)


def construir_raw(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    """Constrói um objeto `BaseRaw` do pyActigraphy a partir do DataFrame.

    Indexa a coluna de atividade por `DATE/TIME`, infere a frequência de
    amostragem pela mediana das diferenças entre timestamps e reamostra a série
    para essa frequência antes de montar o `BaseRaw`.

    Args:
        nome: Nome/identificador do registro (usado em `name` e `uuid`).
        df: DataFrame Condor com a coluna `DATE/TIME` e a coluna de atividade.
        coluna: Nome da coluna de atividade a usar (ex.: ``"PIM"``).

    Returns:
        BaseRaw: Objeto pronto para o cálculo de métricas de ritmo e gráficos.
    """
    serie = pd.Series(df[coluna].to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="Activity")
    frequencia = pd.Timedelta(serie.index.to_series().diff().median())
    serie = serie.asfreq(frequencia)
    return BaseRaw(
        name=nome, uuid=nome, format="CONDOR", axial_mode=None,
        start_time=serie.index[0], period=serie.index[-1] - serie.index[0],
        frequency=frequencia, data=serie, light=None,
    )


@st.cache_data(ttl=120, show_spinner=False)
def construir_raw_cached(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    """Versão cacheada de `construir_raw`.

    Args:
        nome: Nome/identificador do registro.
        df: DataFrame Condor.
        coluna: Nome da coluna de atividade.

    Returns:
        BaseRaw: Mesmo resultado de `construir_raw`, memorizado por 120 s.
    """
    return construir_raw(nome, df, coluna)


def _intervalos_marcados(mascara: pd.Series) -> list[tuple]:
    """Agrupa posições marcadas de uma máscara booleana em intervalos contínuos.

    Args:
        mascara: Série booleana indexada por timestamp; True indica posição
            marcada.

    Returns:
        list[tuple]: Lista de pares `(inicio, fim)` para cada sequência contígua
        de valores True.
    """
    intervalos: list[tuple] = []
    em_intervalo = False
    inicio = anterior = None
    for ts, valor in mascara.items():
        if valor and not em_intervalo:
            inicio, em_intervalo = ts, True
        elif not valor and em_intervalo:
            intervalos.append((inicio, anterior))
            em_intervalo = False
        anterior = ts
    if em_intervalo:
        intervalos.append((inicio, anterior))
    return intervalos


def sombrear_periodo_noturno(
    fig: go.Figure, inicio: pd.Timestamp,
    row: int | str = "all", col: int | str = "all",
) -> None:
    """Sombreia o período noturno (antes das 6h e após as 18h) em uma figura.

    Args:
        fig: Figura Plotly a anotar (modificada in place).
        inicio: Timestamp da meia-noite do dia representado.
        row: Linha do subplot a anotar (``"all"`` para todas).
        col: Coluna do subplot a anotar (``"all"`` para todas).
    """
    for ini, fim in (
        (inicio,                              inicio + pd.Timedelta(hours=6)),
        (inicio + pd.Timedelta(hours=18),     inicio + pd.Timedelta(days=1)),
    ):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_NOITE, line_width=0, layer="below", row=row, col=col)


def _sombrear_eventos(
    fig: go.Figure, serie_evento: pd.Series, dia: str,
    row: int | str = "all", col: int | str = "all",
) -> None:
    """Sombreia, em uma figura, os intervalos com evento marcado em um dia.

    Args:
        fig: Figura Plotly a anotar (modificada in place).
        serie_evento: Série de marcações de evento indexada por timestamp; valores
            diferentes de zero indicam evento.
        dia: Data alvo (``YYYY-MM-DD``) usada para fatiar a série.
        row: Linha do subplot a anotar (``"all"`` para todas).
        col: Coluna do subplot a anotar (``"all"`` para todas).
    """
    try:
        fatia = serie_evento.loc[dia]
    except KeyError:
        return
    marcado = fatia.fillna(0) != 0
    for ini, fim in _intervalos_marcados(marcado):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_EVENTO, line_width=0, layer="below", row=row, col=col)


def rotulo_dia(numero_dia: int, dia: str) -> str:
    """Monta o rótulo de título de um dia, com número, data e dia da semana.

    Args:
        numero_dia: Número sequencial do dia dentro do registro ("Dia N").
        dia: Data do dia no formato ``YYYY-MM-DD``.

    Returns:
        str: Rótulo no formato ``"Dia N — dd/mm/aaaa · <dia da semana>"``.
    """
    ts = pd.Timestamp(dia)
    idx = int(ts.weekday())
    dia_semana = DIAS_SEMANA[idx] + ("-feira" if idx < 5 else "")
    return f"Dia {numero_dia} — {ts.strftime('%d/%m/%Y')} · {dia_semana}"


@st.cache_data(ttl=120, show_spinner=False)
def grafico_combinado_dia(
    dia: str,
    numero_dia: int,
    serie_atividade: pd.Series,
    escala_atividade: tuple[float, float],
    rotulo_atividade: str,
    cor_atividade: str = COR_LINHA,
    mostrar_atividade: bool = True,
    serie_luz: pd.Series | None = None,
    serie_temp: pd.Series | None = None,
    serie_evento: pd.Series | None = None,
    escala_luz: tuple[float, float] | None = None,
    escala_temperatura: tuple[float, float] | None = None,
    hora_inicio: int = 0,
    hora_fim: int = 24,
    serie_luz_filtro: pd.Series | None = None,
    faixa_luz_filtro: tuple[float, float] | None = None,
) -> go.Figure:
    """Monta o gráfico Plotly combinado de um dia de actigrafia.

    Desenha a linha de atividade e, quando fornecidas, sobrepõe luz e temperatura
    como eixos y extras à direita; aplica o sombreamento noturno e, opcionalmente,
    o de eventos. Recorta as séries ao intervalo de horas pedido e, se um filtro
    de luz for informado, oculta os pontos de atividade e temperatura fora da
    faixa.

    Args:
        dia: Data do dia (``YYYY-MM-DD``).
        numero_dia: Número sequencial do dia no registro ("Dia N"), usado no título.
        serie_atividade: Série de atividade indexada por timestamp.
        escala_atividade: Par `(min, max)` do eixo y de atividade.
        rotulo_atividade: Rótulo do eixo/linha de atividade (ex.: ``"PIM"``).
        cor_atividade: Cor da linha de atividade.
        mostrar_atividade: Se False, omite a linha de atividade (mantendo os eixos
            extras).
        serie_luz: Série de luz a sobrepor, ou None.
        serie_temp: Série de temperatura a sobrepor, ou None.
        serie_evento: Série de marcações de evento para sombreamento, ou None.
        escala_luz: Par `(min, max)` do eixo de luz, ou None.
        escala_temperatura: Par `(min, max)` do eixo de temperatura, ou None.
        hora_inicio: Hora inicial (0–24) do recorte exibido.
        hora_fim: Hora final (0–24) do recorte exibido.
        serie_luz_filtro: Série de luz usada para filtrar por faixa, ou None.
        faixa_luz_filtro: Par `(min, max)` de luz; pontos fora da faixa são
            ocultados de atividade e temperatura.

    Returns:
        plotly.graph_objs.Figure: Figura combinada do dia.
    """
    inicio_dia = pd.Timestamp(dia)
    inicio = inicio_dia + pd.Timedelta(hours=hora_inicio)
    fim    = inicio_dia + pd.Timedelta(hours=hora_fim) - pd.Timedelta(seconds=1)

    serie_atividade = serie_atividade.loc[inicio:fim]

    mascara_luz = None
    if serie_luz_filtro is not None and faixa_luz_filtro is not None:
        fatia_luz_filtro = serie_luz_filtro.loc[inicio:fim]
        mascara_luz = fatia_luz_filtro.between(*faixa_luz_filtro)
        serie_atividade = serie_atividade.where(mascara_luz)

    extras = [
        (rotulo, cor, serie, faixa)
        for rotulo, cor, serie, faixa in (
            ("Luz (Lux)",        COR_LUZ,         serie_luz,  escala_luz),
            ("Temperatura (°C)", COR_TEMPERATURA, serie_temp, escala_temperatura),
        )
        if serie is not None
    ]

    fim_dominio_x = 1 - LARGURA_EIXO_EXTRA * len(extras)

    fig = go.Figure()
    if mostrar_atividade:
        fig.add_trace(go.Scatter(
            x=serie_atividade.index, y=serie_atividade.values, mode="lines",
            name=rotulo_atividade, line=dict(color=cor_atividade),
        ))

    layout = dict(
        title=dict(text=rotulo_dia(numero_dia, dia), x=0.01, xanchor="left", font=dict(size=14, color=COR_LEGENDA)),
        xaxis=dict(
            title="Hora", domain=[0, fim_dominio_x], range=[inicio, fim], tickformat="%H:%M",
            dtick=3600000, showgrid=True, gridcolor="rgba(0, 0, 0, 0.15)", griddash="dot",
        ),
        yaxis=dict(
            title=dict(text=rotulo_atividade, font=dict(color=cor_atividade)),
            tickfont=dict(color=cor_atividade),
            range=escala_atividade,
        ),
        height=340,
        margin=dict(l=0, r=0, t=60, b=0),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(255, 255, 255, 0.75)",
            bordercolor="rgba(0, 0, 0, 0.15)", borderwidth=1,
            font=dict(size=11, color=COR_LEGENDA),
        ),
    )

    for i, (rotulo, cor, serie, faixa) in enumerate(extras):
        indice_eixo = i + 2
        eixo_id = f"y{indice_eixo}"
        fatia = serie.loc[inicio:fim]
        if mascara_luz is not None and rotulo == "Temperatura (°C)":
            fatia = fatia.where(mascara_luz)
        fig.add_trace(go.Scatter(
            x=fatia.index, y=fatia.values, mode="lines",
            name=rotulo, line=dict(color=cor, dash="dot"), yaxis=eixo_id,
        ))
        eixo: dict = dict(
            title=dict(text=rotulo, font=dict(color=cor)),
            tickfont=dict(color=cor),
            range=faixa, overlaying="y", side="right",
        )
        if i > 0:
            eixo["anchor"]   = "free"
            eixo["position"] = fim_dominio_x + LARGURA_EIXO_EXTRA * i
        layout[f"yaxis{indice_eixo}"] = eixo

    fig.update_layout(**layout)
    sombrear_periodo_noturno(fig, inicio_dia)
    if serie_evento is not None:
        _sombrear_eventos(fig, serie_evento, dia)
    return fig


# ── Avatar / imagem ───────────────────────────────────────────────────────────

def img_b64_tag(foto_bytes: bytes, foto_tipo: str, tamanho: int, caption: str = "") -> str:
    """Gera o HTML de uma imagem circular embutida em base64.

    Args:
        foto_bytes: Conteúdo binário da imagem.
        foto_tipo: Tipo MIME da imagem (ex.: ``image/png``).
        tamanho: Largura e altura, em pixels (imagem quadrada/circular).
        caption: Legenda opcional, exibida centralizada abaixo da imagem.

    Returns:
        str: Marcação HTML pronta para `unsafe_allow_html=True`.
    """
    b64 = base64.b64encode(foto_bytes).decode()
    html = (
        f'<img src="data:{foto_tipo};base64,{b64}" '
        f'width="{tamanho}" height="{tamanho}" '
        f'style="border-radius:50%;object-fit:cover;display:inline-block;">'
    )
    if caption:
        html += (
            f'<p style="text-align:center;font-size:11px;'
            f'color:#888;margin-top:4px;">{caption}</p>'
        )
    return html


def avatar_html(nome: str, foto: bytes | None, foto_tipo: str | None, tamanho: int) -> str:
    """Gera o HTML de um avatar circular, com foto ou inicial do nome.

    Serve tanto inline (navbar) quanto em bloco (cabeçalho de perfil).

    Args:
        nome: Nome do usuário; sua inicial é usada quando não há foto.
        foto: Conteúdo binário da foto, ou None.
        foto_tipo: Tipo MIME da foto; assume ``image/jpeg`` se ausente.
        tamanho: Diâmetro do avatar, em pixels.

    Returns:
        str: Marcação HTML do avatar. Com foto, uma `<img>` recortada; sem foto,
        um `<div>` colorido com a inicial.
    """
    if foto:
        return img_b64_tag(bytes(foto), foto_tipo or "image/jpeg", tamanho)

    inicial = (nome or "U")[0].upper()
    font    = max(tamanho // 2, 10)
    return (
        f'<div style="width:{tamanho}px;height:{tamanho}px;border-radius:50%;'
        f'background:#4F8BF9;display:inline-flex;align-items:center;'
        f'justify-content:center;font-size:{font}px;color:white;font-weight:bold;">'
        f'{inicial}</div>'
    )


# ── Auth guard ───────────────────────────────────────────────────────────────

def get_usuario_id() -> int | None:
    """Retorna o id do usuário logado, servindo como guard de página.

    Quando não há usuário autenticado, exibe automaticamente um aviso, de modo
    que o chamador só precisa interromper a renderização ao receber None.

    Returns:
        int | None: Id do usuário logado, ou None se não houver autenticação.

    Examples:
        >>> usuario_id = get_usuario_id()
        >>> if not usuario_id:
        ...     return
    """
    uid = st.session_state.get("usuario", {}).get("id")
    if not uid:
        st.info("Esta funcionalidade está disponível apenas para usuários autenticados.")
    return uid


# ── Paginação ─────────────────────────────────────────────────────────────────

def paginacao(pagina: int, n_paginas: int, chave: str) -> None:
    """Renderiza os controles de paginação (Anterior / info / Próxima).

    Não desenha nada quando há uma única página. Os botões de navegação
    atualizam o índice no estado da sessão e forçam o rerun.

    Args:
        pagina: Índice (base 0) da página atual.
        n_paginas: Número total de páginas.
        chave: Chave de `session_state` que guarda o índice atual; também serve
            de prefixo das keys dos botões, evitando conflito entre múltiplas
            paginações na mesma tela.
    """
    if n_paginas <= 1:
        return
    st.divider()
    col_prev, col_info, col_next = st.columns([2, 3, 2])
    if col_prev.button("◀  Anterior", disabled=pagina == 0, width="stretch", key=f"{chave}_prev"):
        st.session_state[chave] = pagina - 1
        st.rerun()
    col_info.button(
        f"Página {pagina + 1} de {n_paginas}",
        disabled=True, width="stretch", key=f"{chave}_info",
    )
    if col_next.button("Próxima  ▶", disabled=pagina >= n_paginas - 1, width="stretch", key=f"{chave}_next"):
        st.session_state[chave] = pagina + 1
        st.rerun()


# ── Toast ─────────────────────────────────────────────────────────────────────

_TOAST_KEY = "_toast"


def set_toast(msg: str, icon: str = "✅") -> None:
    """Agenda um toast para o próximo render (sobrevive a `st.rerun`).

    Args:
        msg: Mensagem a exibir.
        icon: Ícone do toast.
    """
    st.session_state[_TOAST_KEY] = (msg, icon)


def render_toast() -> None:
    """Consome e exibe o toast pendente, se houver.

    Deve ser chamado no início de cada página, formando o par de `set_toast` no
    padrão de notificação entre renders.
    """
    if item := st.session_state.pop(_TOAST_KEY, None):
        msg, icon = item
        st.toast(msg, icon=icon)