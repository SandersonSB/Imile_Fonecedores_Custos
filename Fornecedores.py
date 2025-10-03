# =====================================================
# fornecedores.py - App Streamlit para processar PDFs de apontamentos
# =====================================================

import streamlit as st
import pandas as pd
import pdfplumber
import re
from difflib import SequenceMatcher

# -------------------------------
# Funções auxiliares (mesmas do código original)
# -------------------------------
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
    if re.match(r"^\d{1,3}:\d{2}$", valor.strip()):
        return valor.strip()
    return "00:00"

def limpar_texto(texto):
    texto = texto.upper()
    texto = re.sub(r'[^A-Z0-9 ]', '', texto)
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
    if not hora or hora.strip() == "":
        return 0
    try:
        h, m = map(int, hora.split(":"))
        return h*60 + m
    except:
        return 0

def limpa_valor(v):
    return str(v or "").strip()

def eh_horario(valor):
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

# -------------------------------
# Lista de temas padronizados (tabela mestre)
# -------------------------------
lista_temas_mestra = [
    "FALTA SEM JUSTIFICATIVA",
    "ABONO DE HORAS",
    "DECLARAÇÃO DE HORAS",
    "AJUSTE DE HORAS",
    "ATESTADO MÉDICO",
    "FOLGA HABILITADA",
    "SAÍDA ANTECIPADA"
]

# =====================================================
# Interface inicial do Streamlit
# =====================================================
st.set_page_config(page_title="Processamento de Apontamentos", layout="wide")

st.title("Bem-vindo ao Processamento de Apontamentos")
st.write("Este sistema permite processar arquivos de apontamentos de funcionários e gerar relatórios prontos para análise.")

# Botão para iniciar
if st.button("Iniciar"):
    st.success("✅ Sistema iniciado! Escolha a aba desejada para continuar.")

# =====================================================
# Abas do sistema
# =====================================================
abas = st.tabs(["Blitz", "Demais Fornecedores"])

# ======================
# Aba 1 - Blitz
# ======================
with abas[0]:
    st.subheader("Processamento de Arquivo Blitz")
    st.write("Faça upload do PDF com os apontamentos dos funcionários.")

    uploaded_file = st.file_uploader("Selecione o arquivo PDF", type="pdf")

    if uploaded_file:
        st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")

        # -------------------------------
        # Processamento do PDF
        # -------------------------------
        dados_funcionarios = []
        detalhes = []

        with pdfplumber.open(uploaded_file) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                tabela = pagina.extract_table()
                if not texto and not tabela:
                    continue
                linhas = texto.split("\n") if texto else []

                # Dicionário do funcionário
                funcionario = {
                    "pagina": i+1,
                    "nome": None,
                    "cpf": None,
                    "matricula": None,
                    "cargo": None,
                    "centro_custo": None,
                    "total_trabalhado": "00:00",
                    "total_noturno": "00:00",
                    "horas_previstas": "00:00",
                    "faltas": 0,
                    "horas_atraso": "00:00",
                    "extra_50": "00:00",
                    "desconta_dsr": 0,
                    "status": None,
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

        # -------------------------------
        # Criação do DataFrame
        # -------------------------------
        df = pd.DataFrame(dados_funcionarios)
        df.fillna(0, inplace=True)

        st.success("✅ Processamento concluído!")

        # -------------------------------
        # Mostrar DataFrame no app
        # -------------------------------
        st.subheader("Resumo dos Funcionários")
        st.dataframe(df)

        # -------------------------------
        # Exportar para Excel
        # -------------------------------
        excel_filename = "resumo_funcionarios.xlsx"
        df.to_excel(excel_filename, index=False)
        st.download_button(
            label="📥 Baixar Excel",
            data=open(excel_filename, "rb"),
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ======================
# Aba 2 - Demais Fornecedores
# ======================
with abas[1]:
    st.warning("🚧 Em desenvolvimento. Esta funcionalidade estará disponível em breve.")
