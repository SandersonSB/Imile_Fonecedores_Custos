# ==========================================================
# Fornecedores.py - Assistente de Custos | Imile
# ==========================================================

import streamlit as st
import pandas as pd
import pdfplumber
import re
from difflib import SequenceMatcher
from io import BytesIO
import numpy as np
import fitz  # Biblioteca para processar PDFs escaneados (PyMuPDF)
import os
import pytesseract
from PIL import Image

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
        # tenta extrair apenas números
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
# Configuração inicial
# =========================
st.set_page_config(page_title="Processamento de Fornecedores", layout="wide")

# usa session_state para manter o estado do botão Iniciar
if "iniciado" not in st.session_state:
    st.session_state.iniciado = False

# Splash / Home
if not st.session_state.iniciado:
    github_gif_url = "https://github.com/SandersonSB/Imile_Fonecedores_Custos/blob/main/Gemini_Generated_Image_wjo0iiwjo0iiwjo0.png?raw=true"

    st.markdown("""
    <style>
        .splash-container {
            display: flex;
            flex-direction: column;
            align-items: center; 
            justify-content: center; 
            text-align: center;
            min-height: 80vh;
        }

        .desc-text {
            color: #34495E;
            font-size: 18px;
            max-width: 700px;
            margin: 10px auto 30px auto;
        }

        /* Força o botão do Streamlit a centralizar */
        div.stButton {
            display: flex;
            justify-content: center;
        }

        div.stButton > button {
            height: 60px;
            width: 250px;
            font-size: 22px;
            background-color: #2C3E50;
            color: white;
        }

        div.stButton > button:hover {
            background-color: #34495E;
            transform: scale(1.05);
            transition: all 0.3s ease;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="splash-container">
        <h1 style="color: #2C3E50;">📊 Sistema de Processamento de Dados de Fornecedores</h1>
        <p class="desc-text">
            Este aplicativo processa apontamentos de funcionários em PDF, aplica regras de validação de horários e situações, e gera relatórios finais prontos para análise.
        </p>
        <img src="{github_gif_url}" width="600">
    </div>
    """, unsafe_allow_html=True)

    # Criar 3 colunas e colocar o botão no meio
    col1, col2, col3 = st.columns([3,2,3])
    with col2:
        if st.button("Iniciar 🚀"):
            st.session_state.iniciado = True
            st.experimental_rerun()

# =========================
# Resto do app só roda depois de iniciar
# =========================
else:
    # Cria as abas ao entrar no app (uma única vez)
    tab1, tab2, tab3 = st.tabs(["📂 Blitz", "🎙️ Polly", "🔍 D0"])

# =========================================================================
# PARTE 1: FUNÇÕES DE LÓGICA (COPIAR PARA O TOPO DO SEU ARQUIVO PYTHON)
# =========================================================================
try:
    os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
    pytesseract.get_tesseract_version()
    TESSERACT_INSTALADO = True
except pytesseract.TesseractNotFoundError:
    TESSERACT_INSTALADO = False


def extrair_dados_tabela(texto_pagina, status):
    dados = {
        'Nome': 'Não encontrado', 'Matrícula': 'Não encontrado', 'Dias Trabalhados': 0, 'Extras Total': '00:00',
        'Folga': 0, 'Atestado Médico': 0, 'Falta': 0, 'Abonar ausência': 0, 'Status': status
    }
    
    try:
        nome_match = re.search(r'(?:NOME DO FUNCIONARIO|NOME DO FUNCIONÁRIO):\s*(.*?)(?:\n|NÚMERO DE MATRÍCULA)', texto_pagina, re.DOTALL)
        if nome_match:
            dados['Nome'] = nome_match.group(1).split('\n')[0].strip()
        matr_match = re.search(r'NÚMERO DE MATRÍCULA:\s*(\d+)', texto_pagina)
        if matr_match:
            dados['Matrícula'] = matr_match.group(1).strip()
    except: pass
    
    try:
        linhas_totais = [l for l in texto_pagina.split('\n') if l.strip().startswith('TOTAIS')]
        if linhas_totais:
            campos = [c.strip() for c in linhas_totais[0].split() if c.strip() and c.strip() != 'TOTAIS']
            if len(campos) >= 3:
                dados['Dias Trabalhados'] = int(campos[-3].replace(',', '.').split('.')[0])
                dados['Extras Total'] = campos[-1].strip() 
    except: pass

    texto_maiusculo = texto_pagina.upper()
    termos_busca = {'Folga': 'FOLGA', 'Atestado Médico': 'ATESTADO MÉDICO', 'Falta': 'FALTA'}
    for chave, termo in termos_busca.items():
        dados[chave] = texto_maiusculo.count(termo)
    if re.search(r'ABONAR AUSÊNCIA NO PERÍODO', texto_pagina.upper()):
        dados['Abonar ausência'] = 1
    
    return dados


def extrair_texto_com_ocr(pagina):
    if not TESSERACT_INSTALADO: return ""
    try:
        zoom_x, zoom_y = 2.0, 2.0
        matriz = fitz.Matrix(zoom_x, zoom_y)
        pix = pagina.get_pixmap(matrix=matriz, alpha=False)
        img_data = pix.tobytes("ppm")
        img = Image.open(BytesIO(img_data))
        texto_ocr = pytesseract.image_to_string(img, lang='por')
        return texto_ocr
    except Exception as e:
        print(f"ERRO CRÍTICO no OCR: {e}")
        return ""


@st.cache_data(show_spinner=False)
def extract_employee_data_polly(pdf_bytes):
    dados_finais = []
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(doc.page_count):
            pagina = doc.load_page(i)
            texto_nativo = pagina.get_text("text")
            
            if len(texto_nativo.strip()) > 50:
                dados = extrair_dados_tabela(texto_nativo, 'PDF Nativo')
            else:
                texto_ocr = extrair_texto_com_ocr(pagina)
                if len(texto_ocr.strip()) > 50:
                    dados = extrair_dados_tabela(texto_ocr, 'Processado por OCR')
                else:
                    dados = {'Nome': f'Página {i+1} - Falha no Processamento', 'Matrícula': '-', 'Status': 'FALHA OCR/VAZIO'}
            dados_finais.append(dados)
        doc.close()
    except Exception as e:
        st.error(f"Erro na função principal de extração: {e}")
        return []

    if not dados_finais: return []

    df_consolidado = pd.DataFrame(dados_finais)
    df_final = df_consolidado[df_consolidado['Nome'].str.contains('Página') == False]
    df_final = df_final[df_final['Nome'] != 'Não encontrado'].drop_duplicates(subset=['Matrícula'])

    if df_final.empty: return []

    for col in ['Dias Trabalhados', 'Folga', 'Atestado Médico', 'Falta', 'Abonar ausência']:
        try:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)
        except: pass

    df_final['Total de Faltas e Atestados'] = df_final['Atestado Médico'] + df_final['Falta']
    df_final['Detalhe das Justificativas'] = (
        'Folga: ' + df_final['Folga'].astype(str) + ', AM: ' + df_final['Atestado Médico'].astype(str) + 
        ', Falta: ' + df_final['Falta'].astype(str) + ', Abono: ' + df_final['Abonar ausência'].astype(str)
    )
    
    df_final = df_final.rename(columns={
        'Nome': 'Nome do Funcionário',
        'Dias Trabalhados': 'Dias Trabalhados (Registrados)',
        'Extras Total': 'Horas Extras Total',
    })
    
    df_final['Período de Apuração'] = 'N/A'
    df_final['Horas Extras 50%'] = 'N/A' 

    return df_final.to_dict('records')


def convert_df_to_excel_polly(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: 
        df.to_excel(writer, index=False, sheet_name='Relatorio Polly')
    processed_data = output.getvalue()
    return processed_data

# -------------------------
# Aba Blitz
# -------------------------
with st.container():
    with st.empty():
        pass

# O bloco da Aba Blitz foi reposicionado para o nível da UI (fora de funções)
with st.tabs(["dummy"]):
    pass

# Implementação da Aba Blitz (mantendo sua lógica original e indentação padronizada)
# Observação: o conteúdo original da Aba Blitz foi mantido; aqui reorganizamos para
# que o código execute no escopo correto do Streamlit após a criação das abas.

with st.session_state.get('iniciado', False) and st.container():
    # Se as abas foram criadas, o bloco abaixo será executado no contexto correto.
    try:
        tab1, tab2, tab3 = st.tabs(["📂 Blitz", "🎙️ Polly", "🔍 D0"])
    except Exception:
        # Se as abas já existem em outro escopo, ignoramos essa recriação.
        tab1 = tab2 = tab3 = None

if tab1 is not None:
    with tab1:
        st.header("📂 Upload do PDF de Apontamentos")
        uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"], key="blitz_uploader")

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
                entradas_saidas = [limpa_valor(row.get("ent_1")), limpa_valor(row.get("sai_1")),
                                   limpa_valor(row.get("ent_2")), limpa_valor(row.get("sai_2"))]
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
                mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet"
            )

# -------------------------
# Aba Polly
# -------------------------
if tab2 is not None:
    with tab2:
        st.header("🎙️ Processamento de Cartão de Ponto (Polly)")
        st.markdown("---")

if not TESSERACT_INSTALADO:
    st.warning("⚠️ **ATENÇÃO:** O Tesseract OCR não está configurado. PDFs escaneados não serão processados corretamente.")

# O uploader precisa ser redefinido se você já o tem no seu código
# Se você já tem 'uploaded_file_polly', APAGUE as próximas 5 linhas
# e use sua variável existente. Se não, use este:
uploaded_file_polly = st.file_uploader(
    "1. Anexe o arquivo de Cartão de Ponto (Formato PDF)",
    type=["pdf"],
    key="polly_uploader", # Chave única
    help="Processa PDFs com até 120 páginas, extraindo dados consolidados."
)
# ----------------------------------------------------------------------

if uploaded_file_polly is not None:
    pdf_bytes = uploaded_file_polly.read()
    
    # Botão de processamento para controlar a execução
    if st.button("2. Processar PDF e Gerar Relatório"):
    
        # 2. Executar a função de extração
        # st.spinner é crucial para a experiência em arquivos grandes
        with st.spinner("Processando PDF e extraindo dados... Este processo pode levar tempo para arquivos grandes."):
            data_records = extract_employee_data_polly(pdf_bytes)

        if data_records:
            # 3. Criação do DataFrame e Exibição do Relatório
            df_report = pd.DataFrame(data_records)

            # Colunas de exibição conforme seu pedido
            column_order = [
                "Nome do Funcionário",
                "Matrícula",
                "Período de Apuração",
                "Dias Trabalhados (Registrados)",
                "Horas Extras Total",
                "Horas Extras 50%",
                "Total de Faltas e Atestados",
                "Detalhe das Justificativas"
            ]

            # Garante a ordem e apenas colunas existentes
            column_order_existing = [c for c in column_order if c in df_report.columns]
            df_final = df_report[column_order_existing] if column_order_existing else df_report

            st.success(f"✅ Extração de dados consolidada com sucesso! {len(df_final)} registros únicos de funcionários encontrados.")

            # Exibição da tabela final
            st.markdown("### Relatório de Ponto Consolidado")
            st.dataframe(df_final, use_container_width=True)

            # 4. Opção de Download em XLSX
            excel_data = convert_df_to_excel_polly(df_final)

            st.download_button(
                label="3. Baixar Relatório Polly em XLSX",
                data=excel_data,
                file_name='relatorio_ponto_polly_consolidado.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

        else:
            st.warning("Nenhum Cartão de Ponto da Polly com o formato esperado foi encontrado no arquivo, ou houve um erro no processamento.")
            st.info("Verifique se o PDF contém as frases 'NOME DO FUNCIONARIO' e 'TOTAIS' em um formato de texto detectável.")


    # -------------------------
    # Aba D0
    # -------------------------
    with tab3:
        st.header("🔍 Aba D0")
        st.write("Em construção – espaço reservado para funcionalidades relacionadas ao D0.")
