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

# =========================
# Configuração da página
# =========================
st.set_page_config(page_title="Processamento de Fornecedores", layout="wide")

# =========================
# Inicializa o estado
# =========================
if "iniciado" not in st.session_state:
    st.session_state.iniciado = False

# =========================
# Tela inicial com GIF animado + botão
# =========================
if not st.session_state.iniciado:
    github_gif_url = "https://github.com/SandersonSB/Imile_Fonecedores_Custos/blob/main/Gemini_Generated_Image_wjo0iiwjo0iiwjo0.png?raw=true"

    st.markdown(f"""
<style>
    .splash-container {{
        text-align: center;
        animation: fadeIn 1.5s ease-in-out;
        margin-top: 50px;
    }}

    @keyframes fadeIn {{
        0% {{ opacity: 0; transform: translateY(-20px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}

    .desc-text {{
        color: #34495E;
        font-size: 18px;
        max-width: 700px;
        display: inline-block;       /* Força o bloco a ficar centralizado */
        text-align: center;          /* Centraliza o texto dentro do bloco */
        margin: 10px auto 30px auto; /* Espaçamento */
    }}

    .start-btn {{
        background-color: #2C3E50;
        color: white;
        padding: 12px 30px;
        border: none;
        border-radius: 10px;
        font-size: 18px;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-top: 20px;
    }}

    .start-btn:hover {{
        background-color: #34495E;
        transform: scale(1.05);
    }}
</style>

<div class="splash-container">
    <h1 style="color: #2C3E50;">📊 Sistema de Processamento de Dados de Fornecedores</h1>
    <p class="desc-text">
        Este aplicativo processa apontamentos de funcionários em PDF, aplica regras de validação de horários e situações, e gera relatórios finais prontos para análise.
    </p>
    <img src="{github_gif_url}" width="600">
</div>
""", unsafe_allow_html=True)

    # Botão animado centralizado usando colunas
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Iniciar 🚀", key="start_btn"):
            st.session_state.iniciado = True

# =========================
# Resto do app só roda depois de iniciar
# =========================
else:
    tab1, tab2 = st.tabs(["📂 Blitz", "🚧 Demais Fornecedores"])


    # -------------------------
    # Aba Blitz
    # -------------------------
    with tab1:
        st.header("📂 Upload do PDF de Apontamentos")
        uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])

        if uploaded_file:
            st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")

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

            with pdfplumber.open(uploaded_file) as pdf:
                for i, pagina in enumerate(pdf.pages):
                    texto = pagina.extract_text()
                    tabela = pagina.extract_table()
                    if not texto and not tabela:
                        continue
                    linhas = texto.split("\n") if texto else []

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

            # =========================
            # Criação dos DataFrames
            # =========================
            df = pd.DataFrame(dados_funcionarios).fillna(0)
            df_detalhe = pd.DataFrame(detalhes)
            colunas_justificativas = lista_temas_mestra
            df_consolidado = df.drop(columns=colunas_justificativas)

            # =========================
            # Validações e regras do df_detalhe
            # =========================
            valores_validacao = []
            for _, row in df_detalhe.iterrows():
                total_minutos = (
                    hora_para_minutos(limpa_valor(row.get("sai_1"))) - hora_para_minutos(limpa_valor(row.get("ent_1"))) +
                    hora_para_minutos(limpa_valor(row.get("sai_2"))) - hora_para_minutos(limpa_valor(row.get("ent_2")))
                )
                previsto_minutos = hora_para_minutos(limpa_valor(row.get("horas_previstas")))
                if total_minutos > previsto_minutos:
                    status = "Carga Horaria Completa - Fez Hora Extra"
                elif total_minutos == previsto_minutos:
                    status = "Carga Horaria Completa"
                else:
                    status = "Carga Horaria Incompleta"
                valores_validacao.append(status)
            df_detalhe["Validação da hora trabalhada"] = valores_validacao

            for col in ["ent_1", "sai_1", "ent_2", "sai_2"]:
                df_detalhe[col + "_valido"] = df_detalhe[col].apply(lambda x: eh_horario(limpa_valor(x)))

            def determinar_situacao(row):
                valores = [limpa_valor(row["ent_1"]), limpa_valor(row["sai_1"]), limpa_valor(row["ent_2"]), limpa_valor(row["sai_2"])]
                textos = [v for v in valores if v and not eh_horario(v)]
                if textos:
                    return textos[0].upper()
                horarios_validos = [row["ent_1_valido"], row["sai_1_valido"], row["ent_2_valido"], row["sai_2_valido"]]
                if all(horarios_validos):
                    return "Dia normal de trabalho"
                if any(horarios_validos):
                    return "Presença parcial"
                return "Dia incompleto"

            df_detalhe["Situação"] = df_detalhe.apply(determinar_situacao, axis=1)
            df_detalhe.drop(columns=["ent_1_valido", "sai_1_valido", "ent_2_valido", "sai_2_valido"], inplace=True)

            df_incompletos = df_detalhe[df_detalhe["Situação"] == "Dia incompleto"].copy()
            def reavaliar_situacao(row):
                if eh_horario(limpa_valor(row.get("total_trabalhado"))) and limpa_valor(row.get("total_trabalhado")) != "00:00":
                    return "Dia normal de trabalho"
                entradas_saidas = [limpa_valor(row.get("ent_1")), limpa_valor(row.get("sai_1")),
                                   limpa_valor(row.get("ent_2")), limpa_valor(row.get("sai_2"))]
                if all(v == "" for v in entradas_saidas):
                    return "Dia não previsto"
                textos = [v for v in entradas_saidas if v and not eh_horario(v)]
                if textos:
                    return textos[0].upper()
                return "Presença parcial"
            df_detalhe.loc[df_incompletos.index, "Situação"] = df_incompletos.apply(reavaliar_situacao, axis=1)

            df_detalhe.loc[df_detalhe["ent_1"].str.contains("-", na=False), "Situação"] = "Dia não previsto"
            def pegar_correcao(row):
                for col in ["ent_1", "sai_1", "ent_2", "sai_2"]:
                    val = limpa_valor(row.get(col))
                    if val:
                        return val
                return ""
            df_detalhe["correção"] = df_detalhe.apply(pegar_correcao, axis=1)
            df_detalhe.loc[df_detalhe["Situação"].apply(eh_horario), "Situação"] = df_detalhe["correção"]

            def regra_numero_inicio(row):
                situacao = limpa_valor(row["Situação"])
                if situacao and situacao[0].isdigit():
                    total_trab = limpa_valor(row.get("total_trabalhado"))
                    if eh_horario(total_trab) and total_trab != "00:00":
                        return "Dia normal de trabalho"
                    else:
                        previsto = limpa_valor(row.get("previsto")).upper()
                        return previsto if previsto else "Dia não previsto"
                return situacao
            df_detalhe["Situação"] = df_detalhe.apply(regra_numero_inicio, axis=1)

            situacoes_unicas = df_detalhe["Situação"].unique()
            for sit in situacoes_unicas:
                nome_col = f"Qtd - {sit}"
                df_detalhe[nome_col] = df_detalhe.groupby("cpf")["Situação"].transform(lambda x: (x == sit).sum())

            # =========================
            # Botões de download
            # =========================
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
