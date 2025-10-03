# =========================
# fornecedores_streamlit.py
# =========================

import streamlit as st
import pandas as pd
import pdfplumber
import re
from difflib import SequenceMatcher
from io import BytesIO
import numpy as np

# =========================
# Funções auxiliares
# =========================

def normalizar_nome_coluna(nome):
    """Padroniza os nomes das colunas do PDF"""
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
    """Garantir que o valor de tempo esteja no formato HH:MM"""
    if not valor:
        return "00:00"
    if re.match(r"^\d{1,3}:\d{2}$", valor.strip()):
        return valor.strip()
    return "00:00"

def limpar_texto(texto):
    """Remove caracteres especiais e deixa em maiúsculas"""
    texto = texto.upper()
    texto = re.sub(r'[^A-Z0-9 ]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def achar_tema_mais_proximo(linha, lista_temas, limiar=0.6):
    """Encontra o tema mais próximo da linha de texto usando similaridade"""
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
    """Converte HH:MM em minutos"""
    if not hora or hora.strip() == "":
        return 0
    try:
        h, m = map(int, hora.split(":"))
        return h * 60 + m
    except:
        return 0

def limpa_valor(v):
    """Transforma valor em string limpa"""
    return str(v or "").strip()

def eh_horario(valor):
    """Verifica se o valor está no formato de horário válido HH:MM"""
    if not isinstance(valor, str):
        return False
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
# Configuração da página
# =========================
st.set_page_config(page_title="Processamento de Fornecedores", layout="wide")

# Controle do estado de início
if "start" not in st.session_state:
    st.session_state.start = False

# =========================
# Tela inicial com imagem
# =========================
if not st.session_state.start:
    st.image(
        "https://github.com/SandersonSB/Imile_Fonecedores_Custos/blob/main/Gemini_Generated_Image_wjo0iiwjo0iiwjo0.png",
        use_column_width=True
    )
    st.markdown("""
        # 📊 Sistema de Processamento de Dados de Fornecedores
        Este aplicativo processa apontamentos de funcionários em PDF, 
        aplica regras de validação de horários e situações, 
        e gera relatórios finais prontos para análise.
    """)
    if st.button("Iniciar"):
        st.session_state.start = True
        st.experimental_rerun()  # Recarrega a página para mostrar o app
    st.stop()  # Evita que o resto do app carregue antes do clique

# =========================
# Abas do Streamlit
# =========================
tab1, tab2 = st.tabs(["Blitz", "Demais fornecedores"])

# -------------------------
# Aba Blitz
# -------------------------
with tab1:
    st.header("📂 Upload do PDF de Apontamentos")
    uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
    if uploaded_file:
        st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")

        # Lista de temas possíveis no PDF
        lista_temas_mestra = [
            "FALTA SEM JUSTIFICATIVA", "ABONO DE HORAS", "DECLARAÇÃO DE HORAS",
            "AJUSTE DE HORAS", "ATESTADO MÉDICO", "FOLGA HABILITADA",
            "SAÍDA ANTECIPADA"
        ]

        dados_funcionarios = []
        detalhes = []

        # Leitura do PDF
        with pdfplumber.open(uploaded_file) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                tabela = pagina.extract_table()
                if not texto and not tabela:
                    continue
                linhas = texto.split("\n") if texto else []

                funcionario = {
                    "pagina": i + 1,
                    "nome": None, "cpf": None, "matricula": None,
                    "cargo": None, "centro_custo": None,
                    "total_trabalhado": "00:00", "total_noturno": "00:00",
                    "horas_previstas": "00:00", "faltas": 0,
                    "horas_atraso": "00:00", "extra_50": "00:00",
                    "desconta_dsr": 0, "status": None,
                }

                for tema in lista_temas_mestra:
                    funcionario[tema] = 0

                # Cabeçalho
                for linha in linhas:
                    if "NOME DO FUNCIONÁRIO:" in linha:
                        funcionario["nome"] = linha.split("NOME DO FUNCIONÁRIO:")[-1].split("CPF")[0].strip()
                        funcionario["cpf"] = linha.split("CPF DO FUNCIONÁRIO:")[-1].split("SEG")[0].strip()
                    elif "NÚMERO DE MATRÍCULA:" in linha:
                        funcionario["matricula"] = linha.split("NÚMERO DE MATRÍCULA:")[-1].split("NOME DO DEPARTAMENTO")[0].strip()
                    elif "NOME DO CARGO:" in linha:
                        funcionario["cargo"] = linha.split("NOME DO CARGO:")[-1].split("QUI")[0].strip()
                    elif "NOME DO CENTRO DE CUSTO:" in linha:
                        funcionario["centro_custo"] = linha.split("NOME DO CENTRO DE CUSTO:")[-1].split("DOM")[0].strip()

                # Totais tabela
                if tabela:
                    cabecalho = tabela[0]
                    for linha_tabela in tabela:
                        if linha_tabela[0] and "TOTAIS" in linha_tabela[0].upper():
                            for titulo, valor in zip(cabecalho, linha_tabela):
                                chave = normalizar_nome_coluna(titulo)
                                if chave:
                                    if chave in ["faltas", "desconta_dsr"]:
                                        funcionario[chave] = int(valor) if valor and valor.isdigit() else 0
                                    else:
                                        funcionario[chave] = padronizar_tempo(valor)
                    if funcionario["extra_50"] == funcionario["horas_previstas"]:
                        funcionario["extra_50"] = "00:00"

                # Alterações / justificativas
                encontrou_alteracoes = False
                for linha_texto in linhas:
                    linha_clean = limpar_texto(linha_texto)
                    if not encontrou_alteracoes:
                        if "ALTERACAO" in linha_clean:
                            encontrou_alteracoes = True
                            continue
                    if "BLITZ RECURSOS HUMANOS" in linha_clean:
                        break
                    linha_final = re.sub(r'\d{2}/\d{2}/\d{4}', '', linha_texto)
                    linha_final = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', linha_final)
                    linha_final = re.sub(r'\d+', '', linha_final).strip()
                    if not linha_final:
                        continue
                    tema_encontrado = achar_tema_mais_proximo(linha_final, lista_temas_mestra)
                    if tema_encontrado:
                        funcionario[tema_encontrado] += 1

                # Status OK/NOK
                if funcionario["faltas"] > 0 or funcionario["desconta_dsr"] > 0:
                    funcionario["status"] = "NOK"
                else:
                    funcionario["status"] = "OK"

                dados_funcionarios.append(funcionario)

        # Criação dos DataFrames
        df = pd.DataFrame(dados_funcionarios).fillna(0)
        df_detalhe = pd.DataFrame(detalhes)
        colunas_justificativas = lista_temas_mestra
        df_consolidado = df.drop(columns=colunas_justificativas)

        # Botões de download
        output_consolidado = BytesIO()
        df_consolidado.to_excel(output_consolidado, index=False)
        output_consolidado.seek(0)

        output_detalhe = BytesIO()
        df_detalhe.to_excel(output_detalhe, index=False)
        output_detalhe.seek(0)

        st.download_button(
            label="⬇️ Baixar consolidado_blitz.xlsx",
            data=output_consolidado,
            file_name="consolidado_blitz.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.download_button(
            label="⬇️ Baixar detalhe_funcionarios.xlsx",
            data=output_detalhe,
            file_name="detalhe_funcionarios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# -------------------------
# Aba Demais fornecedores
# -------------------------
with tab2:
    st.header("🚧 Em desenvolvimento")
    st.info("Esta aba ainda está em desenvolvimento e será liberada em breve.")
