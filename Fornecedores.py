# =====================================================
# fornecedores.py - App Streamlit
# =====================================================
import streamlit as st
import pandas as pd
import pdfplumber
import re
from difflib import SequenceMatcher
import numpy as np

# =====================================================
# Funções auxiliares
# =====================================================
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

# =====================================================
# Função principal de processamento
# =====================================================
def processar_pdf(pdf_file):
    lista_temas_mestra = [
        "FALTA SEM JUSTIFICATIVA",
        "ABONO DE HORAS",
        "DECLARAÇÃO DE HORAS",
        "AJUSTE DE HORAS",
        "ATESTADO MÉDICO",
        "FOLGA HABILITADA",
        "SAÍDA ANTECIPADA"
    ]

    dados_funcionarios = []
    detalhes = []

    with pdfplumber.open(pdf_file) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text()
            tabela = pagina.extract_table()
            if not texto and not tabela:
                continue
            linhas = texto.split("\n") if texto else []

            funcionario = {
                "pagina": i+1, "nome": None, "cpf": None, "matricula": None,
                "cargo": None, "centro_custo": None, "total_trabalhado": "00:00",
                "total_noturno": "00:00", "horas_previstas": "00:00", "faltas": 0,
                "horas_atraso": "00:00", "extra_50": "00:00", "desconta_dsr": 0,
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

            if funcionario["faltas"] > 0 or funcionario["desconta_dsr"] > 0:
                funcionario["status"] = "NOK"
            else:
                funcionario["status"] = "OK"

            dados_funcionarios.append(funcionario)

            # Detalhe diário
            if tabela:
                for linha_detalhe in tabela[1:]:
                    linha_detalhe = [celula for celula in linha_detalhe if celula not in [None, '']]
                    if not linha_detalhe or linha_detalhe[0].upper() == "TOTAIS":
                        continue
                    data_split = linha_detalhe[0].split(" - ")
                    data = data_split[0].strip()
                    semana = data_split[1].strip() if len(data_split) > 1 else ""
                    registro = {
                        "pagina": i+1,
                        "nome": funcionario["nome"],
                        "cpf": funcionario["cpf"],
                        "data": data,
                        "semana": semana,
                        "previsto": linha_detalhe[1] if len(linha_detalhe) > 1 else "",
                        "ent_1": linha_detalhe[2] if len(linha_detalhe) > 2 else "",
                        "sai_1": linha_detalhe[3] if len(linha_detalhe) > 3 else "",
                        "ent_2": linha_detalhe[4] if len(linha_detalhe) > 4 else "",
                        "sai_2": linha_detalhe[5] if len(linha_detalhe) > 5 else "",
                        "total_trabalhado": linha_detalhe[6] if len(linha_detalhe) > 6 else "",
                        "total_noturno": linha_detalhe[7] if len(linha_detalhe) > 7 else "",
                        "horas_previstas": linha_detalhe[8] if len(linha_detalhe) > 8 else "",
                        "faltas": linha_detalhe[9] if len(linha_detalhe) > 9 else "",
                        "horas_atraso": linha_detalhe[10] if len(linha_detalhe) > 10 else "",
                        "extra_50": linha_detalhe[11] if len(linha_detalhe) > 11 else "",
                        "desconta_dsr": linha_detalhe[12] if len(linha_detalhe) > 12 else "",
                    }
                    detalhes.append(registro)

    # Criação dos DataFrames
    df = pd.DataFrame(dados_funcionarios)
    df.fillna(0, inplace=True)
    df_detalhe = pd.DataFrame(detalhes)

    # Consolidado sem justificativas
    colunas_justificativas = [
        "FALTA SEM JUSTIFICATIVA", "ABONO DE HORAS", "DECLARAÇÃO DE HORAS",
        "AJUSTE DE HORAS", "ATESTADO MÉDICO", "FOLGA HABILITADA", "SAÍDA ANTECIPADA"
    ]
    df_consolidado_sem_justificativas = df.drop(columns=colunas_justificativas)

    # Retorna os DataFrames finais
    return df_consolidado_sem_justificativas, df_detalhe

# =====================================================
# Streamlit Interface
# =====================================================
st.set_page_config(page_title="Fornecedores", layout="wide")
st.title("Sistema de Apontamentos - Fornecedores")
st.markdown("Este aplicativo processa apontamentos de funcionários a partir de PDFs e gera relatórios consolidados.")

if st.button("Iniciar"):
    aba = st.tabs(["Blitz", "Demais Fornecedores"])

    with aba[0]:
        st.subheader("Blitz")
        pdf_file = st.file_uploader("📂 Selecione o PDF de apontamentos", type=["pdf"])
        if pdf_file:
            st.info("Processando PDF, aguarde...")
            df_consolidado, df_detalhe = processar_pdf(pdf_file)
            df_consolidado.to_excel("consolidado_blitz.xlsx", index=False)
            df_detalhe.to_excel("detalhe_funcionarios.xlsx", index=False)
            st.success("✅ Relatórios gerados com sucesso!")
            st.download_button("⬇️ Baixar consolidado_blitz.xlsx", "consolidado_blitz.xlsx")
            st.download_button("⬇️ Baixar detalhe_funcionarios.xlsx", "detalhe_funcionarios.xlsx")

    with aba[1]:
        st.subheader("Demais Fornecedores")
        st.warning("Esta aba ainda está em desenvolvimento.")
