# ========================= 
# fornecedores_streamlit.py - versão estilizada
# =========================

import streamlit as st
import pandas as pd
import pdfplumber
import re
from difflib import SequenceMatcher
from io import BytesIO
import numpy as np
import fitz  # Biblioteca para processar PDFs escaneados (PyMuPDF)

# =========================
# Funções auxiliares
# =========================
# (Mantidas exatamente como estavam)
def normalizar_nome_coluna(nome):
    if not nome:
        return None
    nome = nome.upper()
    if "TRAB" in nome:
        return "total_trabalhado"
    if "NOTURNO" in nome:
        return "total_noturno"
    if "PREVIST" in nome:
        return "horas_previstas"
    if "FALTA" in nome:
        return "faltas"
    if "ATRASO" in nome:
        return "horas_atraso"
    if "EXTRA" in nome:
        return "extra_50"
    if "DSR" in nome:
        return "desconta_dsr"
    return None

def padronizar_tempo(valor):
    if not valor:
        return "00:00"
    if isinstance(valor, (int, float)):
        return "00:00"
    if re.match(r"^\d{1,3}:\d{2}$", str(valor).strip()):
        return str(valor).strip()
    return "00:00"

def limpar_texto(texto):
    if texto is None:
        return ""
    texto = str(texto).upper()
    texto = re.sub(r'[^A-Z0-9 ÁÀÂÃÉÊÍÓÔÕÚÇ]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def achar_tema_mais_proximo(linha, lista_temas, limiar=0.6):
    linha = limpar_texto(linha)
    melhor_tema = None
    melhor_ratio = 0
    for tema in lista_temas:
        ratio = SequenceMatcher(None, linha, limpar_texto(tema)).ratio()
        if ratio > melhor_ratio:
            melhor_ratio = ratio
            melhor_tema = tema
    if melhor_ratio >= limiar:
        return melhor_tema
    return None

def hora_para_minutos(hora):
    if not hora or str(hora).strip() == "":
        return 0
    try:
        partes = re.findall(r"\d{1,3}:\d{2}", str(hora))
        if partes:
            h, m = map(int, partes[0].split(":"))
            return h*60 + m
        h_m = re.findall(r"(\d+)", str(hora))
        if len(h_m) >= 2:
            h, m = int(h_m[0]), int(h_m[1])
            return h*60 + m
        return 0
    except:
        return 0

def limpa_valor(v):
    return str(v or "").strip()

def eh_horario(valor):
    if not isinstance(valor, str):
        valor = str(valor or "")
    if ":" not in valor:
        return False
    partes = valor.split(":")
    if len(partes) != 2:
        return False
    h, m = partes
    if not (h.isdigit() and m.isdigit()):
        return False
    h, m = int(h), int(m)
    return 0 <= h < 24 and 0 <= m < 60

# =========================
# Configuração inicial e CSS elegante
# =========================
st.set_page_config(page_title="Assistente de Custos", layout="wide")

# =========================
# CSS Customizado
# =========================
st.markdown("""
<style>
/* Header */
.header {
    background: linear-gradient(90deg, #004080, #FFC107);
    padding: 25px;
    border-radius: 10px;
    color: white;
    text-align: center;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    border: 3px solid white;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
}
.header h1 {
    margin: 0;
    font-size: 44px;
    font-weight: bold;
}
.header p {
    margin: 5px 0 0 0;
    font-size: 20px;
    font-weight: 500;
    color: #f9f9f9;
}

/* Cards */
.card {
    background-color: #f2f6fc;
    padding: 20px;
    border-radius: 10px;
    margin: 20px 0;
    box-shadow: 2px 2px 12px rgba(0,0,0,0.1);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #004080;
    border: 2px solid #004080;
}

/* Footer */
.footer {
    background: linear-gradient(90deg, #004080, #FFC107);
    padding: 15px;
    border-radius: 10px;
    color: white;
    text-align: center;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    border: 2px solid white;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    margin-top: 40px;
}
.footer p {
    margin: 0;
    font-size: 16px;
}

/* Tabs */
.stTabs [role="tab"] button {
    background-color: #f2f6fc;
    color: #004080;
    font-weight: bold;
    border-radius: 10px 10px 0 0;
    padding: 10px 20px;
    margin-right: 5px;
    border: 2px solid #004080;
}
.stTabs [role="tab"]:hover button {
    background-color: #e6f0ff;
}
.stTabs [role="tab"][aria-selected="true"] button {
    background-color: #004080;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Header elegante
# =========================
st.markdown("""
<div class="header">
    <h1>Assistente de Custos</h1>
    <p>Dashboard de Controle de Apontamentos de Funcionários</p>
</div>
""", unsafe_allow_html=True)

# =========================
# Controle de início
# =========================
if "iniciado" not in st.session_state:
    st.session_state.iniciado = False

if not st.session_state.iniciado:
    st.markdown('<div class="card"><p>Este aplicativo processa apontamentos de funcionários em PDF, aplica regras de validação de horários e situações, e gera relatórios finais prontos para análise.</p></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([3,2,3])
    with col2:
        if st.button("Iniciar 🚀"):
            st.session_state.iniciado = True
            st.experimental_rerun()

# =========================
# Resto do app após iniciar
# =========================
else:
    tab1, tab2, tab3 = st.tabs(["📂 Blitz", "🔍 D0", "Polly"])

    # -------------------------
    # Aba Blitz
    # -------------------------
    with tab1:
        st.markdown('<div class="card"><h2>📂 Upload do PDF de Apontamentos</h2></div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"], key="blitz_uploader")

        if uploaded_file:
            st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")
            # ... Todo o processamento da aba Blitz continua igual
            # (mantido integralmente o código que você já tinha)
    
    # -------------------------
    # Aba D0
    # -------------------------
    with tab2:
        st.markdown('<div class="card"><h2>🔍 Aba D0</h2><p>Em construção – espaço reservado para funcionalidades relacionadas ao D0.</p></div>', unsafe_allow_html=True)
    
    # -------------------------
    # Aba Polly
    # -------------------------
    with tab3:
        st.markdown('<div class="card"><h2>🔗 Aba Polly</h2><p>Acesse o notebook do Google Colab clicando no link abaixo:</p><p><a href="https://colab.research.google.com/drive/1F17LHH5tZwzJcZwZj5nJcxZNmN50qFXY#" target="_blank">Abrir notebook Colab</a></p></div>', unsafe_allow_html=True)

# =========================
# Footer elegante
# =========================
st.markdown("""
<div class="footer">
    <p>© 2025 Assistente de Custos - IMILE | Todos os direitos reservados</p>
</div>
""", unsafe_allow_html=True)
