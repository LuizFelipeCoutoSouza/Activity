
"""
view/ui.py — Utilitários de UI compartilhados entre as views.

Exporta:
  Enums   : Profissao
  Tamanhos: AVATAR_NAV, AVATAR_SM, AVATAR_LG
  Helpers : fmt_cpf, fmt_telefone, forca_senha
  Avatar  : img_b64_tag, avatar_html
  Toast   : set_toast, render_toast
"""

import re
import base64
from enum import Enum

import streamlit as st


# ── Enums de domínio ──────────────────────────────────────────────────────────

class Profissao(str, Enum):
    """
    Profissões válidas para cadastro e edição de perfil.
    Herda de str para que os valores possam ser usados diretamente como texto
    (ex.: comparação com banco de dados, selectbox, etc.).
    """
    MEDICO         = "Médico"
    ENFERMEIRO     = "Enfermeiro"
    FISIOTERAPEUTA = "Fisioterapeuta"
    PESQUISADOR    = "Pesquisador"
    ADMIN          = "Admin"

    @classmethod
    def opcoes(cls) -> list[str]:
        """Retorna a lista de valores para uso em selectbox."""
        return [p.value for p in cls]


# ── Tamanhos de avatar (px) ───────────────────────────────────────────────────

AVATAR_NAV = 36   # navbar
AVATAR_SM  = 80   # cabeçalho de perfil
AVATAR_LG  = 120  # seção de foto


# ── Formatadores ──────────────────────────────────────────────────────────────

def fmt_cpf(cpf: str) -> str:
    """Retorna o CPF no formato 000.000.000-00. Aceita entrada com ou sem máscara."""
    d = re.sub(r"\D", "", cpf or "")
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}" if len(d) == 11 else (cpf or "")


def fmt_telefone(tel: str) -> str:
    """
    Formata um telefone para (00) 00000-0000 (celular) ou (00) 0000-0000 (fixo).
    Aceita entrada com ou sem máscara.
    """
    d = re.sub(r"\D", "", tel or "")
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel or ""


# ── Força de senha ────────────────────────────────────────────────────────────

def forca_senha(senha: str) -> tuple[int, str, str]:
    """
    Avalia a força de uma senha.
    Retorna (score: 0–4, label: str, emoji: str).
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


# ── Avatar / imagem ───────────────────────────────────────────────────────────

def img_b64_tag(foto_bytes: bytes, foto_tipo: str, tamanho: int, caption: str = "") -> str:
    """
    Gera HTML de <img> circular com dimensões fixas, codificado em base64.
    Parâmetro caption opcional exibe um texto centralizado abaixo da imagem.
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
    """
    Gera HTML de avatar circular.
    - Se foto estiver disponível: <img> com object-fit:cover.
    - Caso contrário: div colorido com a inicial do nome.
    Funciona tanto inline (navbar) quanto como bloco (páginas de perfil).
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


# ── Toast ─────────────────────────────────────────────────────────────────────

_TOAST_KEY = "_toast"


def set_toast(msg: str, icon: str = "✅") -> None:
    """Agenda um toast para ser exibido no próximo ciclo de render (após st.rerun)."""
    st.session_state[_TOAST_KEY] = (msg, icon)


def render_toast() -> None:
    """Consome e exibe o toast pendente, se houver. Deve ser chamado no início da página."""
    if item := st.session_state.pop(_TOAST_KEY, None):
        msg, icon = item
        st.toast(msg, icon=icon)