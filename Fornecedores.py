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
    # ==============================
    # Card de upload
    # ==============================
    st.markdown(
        """
        <div class="card">
            <h2>📂 Upload do PDF de Apontamentos</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    uploaded_file = st.file_uploader(
        "Selecione o arquivo PDF que evidencia o ponto dos colaboradores blitz.",
        type=["pdf"],
        key="blitz_uploader"
    )

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
                texto = pagina.extract_text() or ""
                tabela = pagina.extract_table()
                if not texto and not tabela:
                    continue
                linhas = texto.split("\n") if texto else []

                funcionario = {
                    "pagina": i + 1,
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

                # =====================
                # Cabeçalho por página
                # =====================
                for linha in linhas:
                    if "NOME DO FUNCIONÁRIO:" in linha or "NOME DO FUNCIONARIO:" in linha:
                        try:
                            funcionario["nome"] = linha.split("NOME DO FUNCIONÁRIO:")[-1].split("CPF")[0].strip()
                        except:
                            funcionario["nome"] = linha.split("NOME DO FUNCIONARIO:")[-1].split("CPF")[0].strip() if "CPF" in linha else linha
                        if "CPF" in linha:
                            try:
                                funcionario["cpf"] = linha.split("CPF DO FUNCIONÁRIO:")[-1].split("SEG")[0].strip()
                            except:
                                funcionario["cpf"] = ""
                    elif "NÚMERO DE MATRÍCULA:" in linha or "NUMERO DE MATRICULA:" in linha:
                        parts = linha.split("NÚMERO DE MATRÍCULA:")[-1] if "NÚMERO DE MATRÍCULA:" in linha else linha.split("NUMERO DE MATRICULA:")[-1]
                        funcionario["matricula"] = parts.split("NOME DO DEPARTAMENTO")[0].strip() if "NOME DO DEPARTAMENTO" in parts else parts.strip()
                    elif "NOME DO CARGO:" in linha:
                        funcionario["cargo"] = linha.split("NOME DO CARGO:")[-1].split("QUI")[0].strip() if "NOME DO CARGO:" in linha else linha
                    elif "NOME DO CENTRO DE CUSTO:" in linha:
                        funcionario["centro_custo"] = linha.split("NOME DO CENTRO DE CUSTO:")[-1].split("DOM")[0].strip() if "NOME DO CENTRO DE CUSTO:" in linha else linha

                        # Totais tabela
                        if tabela:
                            cabecalho = tabela[0]
                            for linha_tabela in tabela:
                                if linha_tabela and linha_tabela[0] and "TOTAIS" in str(linha_tabela[0]).upper():
                                    for titulo, valor in zip(cabecalho, linha_tabela):
                                        chave = normalizar_nome_coluna(titulo)
                                        if chave:
                                            if chave in ["faltas", "desconta_dsr"]:
                                                funcionario[chave] = int(valor) if valor and str(valor).isdigit() else 0
                                            else:
                                                funcionario[chave] = padronizar_tempo(valor)
                            if funcionario.get("extra_50") == funcionario.get("horas_previstas"):
                                funcionario["extra_50"] = "00:00"

                        # Alterações / justificativas
                        encontrou_alteracoes = False
                        for linha_texto in linhas:
                            linha_clean = limpar_texto(linha_texto)
                            if not encontrou_alteracoes:
                                if "ALTERACAO" in linha_clean or "ALTERAÇÃO" in linha_clean:
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
                                if not linha_detalhe or (isinstance(linha_detalhe[0], str) and linha_detalhe[0].upper() == "TOTAIS"):
                                    continue
                                data_split = linha_detalhe[0].split(" - ")
                                data = data_split[0].strip()
                                semana = data_split[1].strip() if len(data_split) > 1 else ""
                                registro = {
                                    "pagina": i + 1,
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
            try:
                df_consolidado = df.drop(columns=colunas_justificativas)
            except Exception:
                df_consolidado = df.copy()

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
                valores = [limpa_valor(row.get("ent_1")), limpa_valor(row.get("sai_1")), limpa_valor(row.get("ent_2")), limpa_valor(row.get("sai_2"))]
                textos = [v for v in valores if v and not eh_horario(v)]
                if textos:
                    return textos[0].upper()
                horarios_validos = [row.get("ent_1_valido"), row.get("sai_1_valido"), row.get("ent_2_valido"), row.get("sai_2_valido")]
                if all(horarios_validos):
                    return "Dia normal de trabalho"
                if any(horarios_validos):
                    return "Presença parcial"
                return "Dia incompleto"

            df_detalhe["Situação"] = df_detalhe.apply(determinar_situacao, axis=1)
            df_detalhe.drop(columns=[c for c in ["ent_1_valido", "sai_1_valido", "ent_2_valido", "sai_2_valido"] if c in df_detalhe.columns], inplace=True)

            df_incompletos = df_detalhe[df_detalhe["Situação"] == "Dia incompleto"].copy()

            def reavaliar_situacao(row):
                if eh_horario(limpa_valor(row.get("total_trabalhado"))) and limpa_valor(row.get("total_trabalhado")) != "00:00":
                    return "Dia normal de trabalho"
                entradas_saidas = [limpa_valor(row.get("ent_1")), limpa_valor(row.get("sai_1")), limpa_valor(row.get("ent_2")), limpa_valor(row.get("sai_2"))]
                if all(v == "" for v in entradas_saidas):
                    return "Dia não previsto"
                textos = [v for v in entradas_saidas if v and not eh_horario(v)]
                if textos:
                    return textos[0].upper()
                return "Presença parcial"

            if not df_incompletos.empty:
                df_detalhe.loc[df_incompletos.index, "Situação"] = df_incompletos.apply(reavaliar_situacao, axis=1)

            df_detalhe.loc[df_detalhe.get("ent_1", "").astype(str).str.contains("-", na=False), "Situação"] = "Dia não previsto"

            def pegar_correcao(row):
                for col in ["ent_1", "sai_1", "ent_2", "sai_2"]:
                    val = limpa_valor(row.get(col))
                    if val:
                        return val
                return ""

            df_detalhe["correção"] = df_detalhe.apply(pegar_correcao, axis=1)
            df_detalhe.loc[df_detalhe["Situação"].apply(lambda x: eh_horario(str(x))), "Situação"] = df_detalhe["correção"]

            def regra_numero_inicio(row):
                situacao = limpa_valor(row.get("Situação"))
                if situacao and len(situacao) > 0 and situacao[0].isdigit():
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
            # ===============================
            # Correção final de folgas (pós-processamento)
            # ===============================
            # Mesmo após todas as regras, se o campo "previsto" indicar folga,
            # mas a situação ainda estiver como "Dia não previsto" ou vazia,
            # ela será corrigida para "Folga".
            
            if "previsto" in df_detalhe.columns and "Situação" in df_detalhe.columns:
                df_detalhe["previsto_limpo"] = df_detalhe["previsto"].astype(str).str.upper().str.strip()
            
                cond_folga = (
                    df_detalhe["previsto_limpo"].str.contains("FOLGA", na=False)
                    | df_detalhe["previsto_limpo"].isin(["-", "FOLGA HABILITADA", "FOLGA"])
                )
                cond_situacao_incorreta = df_detalhe["Situação"].isin(["Dia não previsto", "", None])
            
                df_detalhe.loc[cond_folga & cond_situacao_incorreta, "Situação"] = "Folga"
                df_detalhe.drop(columns=["previsto_limpo"], inplace=True)
            
                # Atualiza as contagens após a correção
                situacoes_unicas = df_detalhe["Situação"].unique()
                for sit in situacoes_unicas:
                    nome_col = f"Qtd - {sit}"
                    df_detalhe[nome_col] = df_detalhe.groupby("cpf")["Situação"].transform(lambda x: (x == sit).sum())
   

        # =========================
        # Botões de Download
        # =========================
        st.markdown(
            """
            <div class="card">
                <h3>📥 Baixar Relatórios</h3>
                <p>Após o processamento, você pode baixar os arquivos consolidados com um clique abaixo:</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        output_consolidado = BytesIO()
        df_consolidado.to_excel(output_consolidado, index=False)
        output_consolidado.seek(0)

        output_detalhe = BytesIO()
        df_detalhe.to_excel(output_detalhe, index=False)
        output_detalhe.seek(0)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="⬇️ Baixar consolidado_blitz.xlsx",
                data=output_consolidado,
                file_name="consolidado_blitz.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            st.download_button(
                label="⬇️ Baixar detalhe_funcionarios.xlsx",
                data=output_detalhe,
                file_name="detalhe_funcionarios.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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
