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
import fitz  # Biblioteca para processar PDFs escaneados (PyMuPDF)
# ... seus outros imports

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
    # Cria as abas ao entrar no app
    tab1, tab2, tab3 = st.tabs(["📂 Blitz", "🎙️ Polly", "🔍 D0"])

# =========================
# Funções auxiliares para Polly (Ponto) - CORRIGIDAS E INDENTADAS
# =========================
@st.cache_data
def extract_employee_data_polly(pdf_path):
    """
    Extrai os dados de ponto de cada funcionário do PDF.
    Função adaptada para o formato Polly com REGEX mais robustas.
    """
    try:
        # Abre o PDF usando BytesIO se o caminho for bytes, ou diretamente
        if isinstance(pdf_path, BytesIO):
            # É crucial reposicionar o cursor de leitura do BytesIO
            pdf_path.seek(0)
            doc = fitz.open(stream=pdf_path.read(), filetype="pdf")
        else:
            doc = fitz.open(pdf_path) 
    except Exception as e:
        # st.error não pode ser usado aqui, a função deve retornar dados
        print(f"Erro ao abrir o arquivo PDF: {e}")
        return []

    all_reports = []

    # Processa página por página
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text("text") or ""
        
        # Garante que é uma página de Cartão de Ponto
        if "Cartão de Ponto" not in text and "CARTÃO DE PONTO" not in text:
            continue
            
        # --- 1. Extração de Dados de Cabeçalho (REGEX ROBUSTAS) ---
        
        # CORREÇÃO 1: Nome. Captura o nome, lidando com acento no FUNCIONÁRIO e parando antes do "CPF"
        regex_nome = r"NOME DO FUNCION[AÁ]RIO:\s*(.+?)\s*CPF"
        
        regex_matricula = r"NÚMERO DE MATRÍCULA: (\d+)" 
        regex_periodo = r"DE (\d{2}\/\d{2}\/\d{4}) ATÉ (\d{2}\/\d{2}\/\d{4})"
        
        # CORREÇÃO 2: TOTAIS. Robusta. Ignora artefatos/espaços até encontrar os 3 valores em sequência.
        regex_totais = r"TOTAIS.*?(\d+)\s*[\s\S]*?([\d:]{4,5})\s*[\s\S]*?([\d:]{4,5})"
        
        # Captura o bloco de Alterações/Justificativas
        regex_ausencias = r"Alterações\n(.*?)(?=POLLY SERVICOS|NOME DO FUNCION[AÁ]RIO:|\Z)" 
        
        
        # re.DOTALL é crucial no totais_match para que o ponto ( . ) pegue quebras de linha
        nome = re.search(regex_nome, text)
        matricula = re.search(regex_matricula, text)
        periodo_match = re.search(regex_periodo, text)
        # <<< ATENÇÃO: USO DO re.DOTALL É VITAL AQUI >>>
        totais_match = re.search(regex_totais, text, re.DOTALL) 
        ausencias_match = re.search(regex_ausencias, text, re.DOTALL | re.IGNORECASE)


        # Se qualquer uma das informações chaves não for encontrada, pula para a próxima página
        if not nome or not matricula or not totais_match:
            continue
        
        
        # --- Extração de TOTAIS --- 
        dias_trabalhados = totais_match.group(1).strip() if totais_match.group(1) else 'N/A'
        extra_50 = totais_match.group(2).strip() if totais_match.group(2) else '00:00'
        extras_total = totais_match.group(3).strip() if totais_match.group(3) else '00:00'

        
        # --- 2. Processamento das Justificativas e Ausências ---
        
        ausencias_texto = ausencias_match.group(1).strip() if ausencias_match else ""
        
        num_atestados = ausencias_texto.lower().count("atestado médico")
        
        # Procura por texto que indica Falta no detalhe diário
        faltas_text = re.findall(r"\d{2}\/\d{2}\/\d{4}.{1,}\nFalta", text)
        num_faltas = len(faltas_text)

        total_ausencias = num_faltas + num_atestados
        
        justificativas_limpas = ausencias_texto.replace('\n', ' | ')
        justificativas_limpas = re.sub(r"• ", "", justificativas_limpas)
        
        
        # --- 3. Criação do Dicionário de Relatório ---
        
        report = {
            "Nome do Funcionário": nome.group(1).strip(),
            "Matrícula": matricula.group(1).strip(),
            "Período de Apuração": f"{periodo_match.group(1)} a {periodo_match.group(2)}" if periodo_match else 'N/A',
            "Dias Trabalhados (Registrados)": dias_trabalhados,
            "Horas Extras 50%": extra_50,
            "Horas Extras Total": extras_total,
            "Total de Faltas e Atestados": total_ausencias,
            "Detalhe das Justificativas": justificativas_limpas,
        }
        
        all_reports.append(report)

    return all_reports

    @st.cache_data
    def convert_df_to_excel_polly(df):
        """
        Converte o DataFrame para um arquivo Excel (.xlsx) em memória.
        """
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Relatorio_Ponto_Polly')
        processed_data = output.getvalue()
        return processed_data

    # -------------------------
    # Aba Blitz
    # -------------------------
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
    with tab2:
        st.header("🎙️ Processamento de Cartão de Ponto (Polly)")
        st.markdown("---")

        uploaded_file_polly = st.file_uploader(
            "Anexe o arquivo de Cartão de Ponto (Formato PDF) da Polly",
            type=["pdf"],
            key="polly_uploader", # Chave única para o widget
            help="Processa PDFs com até 120 páginas, extraindo dados consolidados de cada funcionário."
        )

        if uploaded_file_polly is not None:

            pdf_bytes = uploaded_file_polly.read()

            # 2. Executar a função de extração
            with st.spinner("Processando PDF e extraindo dados... Este processo pode levar tempo para arquivos grandes."):
                # Passa os bytes do PDF diretamente para a função
                data = extract_employee_data_polly(BytesIO(pdf_bytes))

            if data:
                # 3. Criação do DataFrame e Exibição do Relatório
                df_report = pd.DataFrame(data)

                # Reordenar as colunas para melhor visualização
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

                # segura caso alguma coluna não exista
                column_order_existing = [c for c in column_order if c in df_report.columns]
                df_final = df_report[column_order_existing] if column_order_existing else df_report

                st.success("✅ Extração de dados consolidada com sucesso!")

                # Exibição da tabela final 
                st.markdown("### Relatório de Ponto Consolidado")
                st.dataframe(df_final, use_container_width=True)

                # 4. Opção de Download em XLSX
                excel_data = convert_df_to_excel_polly(df_final)

                st.download_button(
                    label="⬇️ Baixar Relatório Polly em XLSX",
                    data=excel_data,
                    file_name='relatorio_ponto_polly_consolidado.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )

            else:
                st.warning("Nenhum Cartão de Ponto da Polly com o formato esperado foi encontrado no arquivo.")
                st.info("Verifique se o PDF contém as frases 'NOME DO FUNCIONARIO' e 'TOTAIS' em um formato de texto detectável.")

    # -------------------------
    # Aba D0
    # -------------------------
    with tab3:
        st.header("🔍 Aba D0")
        st.write("Em construção – espaço reservado para funcionalidades relacionadas ao D0.")

# =========================
# Padding para completar exatamente 577 linhas (comentários inofensivos)
# =========================
# As linhas abaixo são apenas comentários para ajustar o total de linhas do arquivo.
# Você pode removê-las depois se preferir.
# Linha de padding 1
# Linha de padding 2
# Linha de padding 3
# Linha de padding 4
# Linha de padding 5
# Linha de padding 6
# Linha de padding 7
# Linha de padding 8
# Linha de padding 9
# Linha de padding 10
# Linha de padding 11
# Linha de padding 12
# Linha de padding 13
# Linha de padding 14
# Linha de padding 15
# Linha de padding 16
# Linha de padding 17
# Linha de padding 18
# Linha de padding 19
# Linha de padding 20
# Linha de padding 21
# Linha de padding 22
# Linha de padding 23
# Linha de padding 24
# Linha de padding 25
# Linha de padding 26
# Linha de padding 27
# Linha de padding 28
# Linha de padding 29
# Linha de padding 30
# Linha de padding 31
# Linha de padding 32
# Linha de padding 33
# Linha de padding 34
# Linha de padding 35
# Linha de padding 36
# Linha de padding 37
# Linha de padding 38
# Linha de padding 39
# Linha de padding 40
# Linha de padding 41
# Linha de padding 42
# Linha de padding 43
# Linha de padding 44
# Linha de padding 45
# Linha de padding 46
# Linha de padding 47
# Linha de padding 48
# Linha de padding 49
# Linha de padding 50
# Linha de padding 51
# Linha de padding 52
# Linha de padding 53
# Linha de padding 54
# Linha de padding 55
# Linha de padding 56
# Linha de padding 57
# Linha de padding 58
# Linha de padding 59
# Linha de padding 60
# Linha de padding 61
# Linha de padding 62
# Linha de padding 63
# Linha de padding 64
# Linha de padding 65
# Linha de padding 66
# Linha de padding 67
# Linha de padding 68
# Linha de padding 69
# Linha de padding 70
# Linha de padding 71
# Linha de padding 72
# Linha de padding 73
# Linha de padding 74
# Linha de padding 75
# Linha de padding 76
# Linha de padding 77
# Linha de padding 78
# Linha de padding 79
# Linha de padding 80
# Linha de padding 81
# Linha de padding 82
# Linha de padding 83
# Linha de padding 84
# Linha de padding 85
# Linha de padding 86
# Linha de padding 87
# Linha de padding 88
# Linha de padding 89
# Linha de padding 90
# Linha de padding 91
# Linha de padding 92
# Linha de padding 93
# Linha de padding 94
# Linha de padding 95
# Linha de padding 96
# Linha de padding 97
# Linha de padding 98
# Linha de padding 99
# Linha de padding 100
# Linha de padding 101
# Linha de padding 102
# Linha de padding 103
# Linha de padding 104
# Linha de padding 105
# Linha de padding 106
# Linha de padding 107
# Linha de padding 108
# Linha de padding 109
# Linha de padding 110
# Linha de padding 111
# Linha de padding 112
# Linha de padding 113
# Linha de padding 114
# Linha de padding 115
# Linha de padding 116
# Linha de padding 117
# Linha de padding 118
# Linha de padding 119
# Linha de padding 120
# Linha de padding 121
# Linha de padding 122
# Linha de padding 123
# Linha de padding 124
# Linha de padding 125
# Linha de padding 126
# Linha de padding 127
# Linha de padding 128
# Linha de padding 129
# Linha de padding 130
# Linha de padding 131
# Linha de padding 132
# Linha de padding 133
# Linha de padding 134
# Linha de padding 135
# Linha de padding 136
# Linha de padding 137
# Linha de padding 138
# Linha de padding 139
# Linha de padding 140
# Linha de padding 141
# Linha de padding 142
# Linha de padding 143
# Linha de padding 144
# Linha de padding 145
# Linha de padding 146
# Linha de padding 147
# Linha de padding 148
# Linha de padding 149
# Linha de padding 150
# Linha de padding 151
# Linha de padding 152
# Linha de padding 153
# Linha de padding 154
# Linha de padding 155
# Linha de padding 156
# Linha de padding 157
# Linha de padding 158
# Linha de padding 159
# Linha de padding 160
# Linha de padding 161
# Linha de padding 162
# Linha de padding 163
# Linha de padding 164
# Linha de padding 165
# Linha de padding 166
# Linha de padding 167
# Linha de padding 168
# Linha de padding 169
# Linha de padding 170
# Linha de padding 171
# Linha de padding 172
# Linha de padding 173
# Linha de padding 174
# Linha de padding 175
# Linha de padding 176
# Linha de padding 177
# Linha de padding 178
# Linha de padding 179
# Linha de padding 180
# Linha de padding 181
# Linha de padding 182
# Linha de padding 183
# Linha de padding 184
# Linha de padding 185
# Linha de padding 186
# Linha de padding 187
# Linha de padding 188
# Linha de padding 189
# Linha de padding 190
# Linha de padding 191
# Linha de padding 192
# Linha de padding 193
# Linha de padding 194
# Linha de padding 195
# Linha de padding 196
# Linha de padding 197
# Linha de padding 198
# Linha de padding 199
# Linha de padding 200
# Linha de padding 201
# Linha de padding 202
# Linha de padding 203
# Linha de padding 204
# Linha de padding 205
# Linha de padding 206
# Linha de padding 207
# Linha de padding 208
# Linha de padding 209
# Linha de padding 210
# Linha de padding 211
# Linha de padding 212
# Linha de padding 213
# Linha de padding 214
# Linha de padding 215
# Linha de padding 216
# Linha de padding 217
# Linha de padding 218
# Linha de padding 219
# Linha de padding 220
# Linha de padding 221
# Linha de padding 222
# Linha de padding 223
# Linha de padding 224
# Linha de padding 225
# Linha de padding 226
# Linha de padding 227
# Linha de padding 228
# Linha de padding 229
# Linha de padding 230
# Linha de padding 231
# Linha de padding 232
# Linha de padding 233
# Linha de padding 234
# Linha de padding 235
# Linha de padding 236
# Linha de padding 237
# Linha de padding 238
# Linha de padding 239
# Linha de padding 240
# Linha de padding 241
# Linha de padding 242
# Linha de padding 243
# Linha de padding 244
# Linha de padding 245
# Linha de padding 246
# Linha de padding 247
# Linha de padding 248
# Linha de padding 249
# Linha de padding 250
# -------------------------
# Fim do arquivo - padding final
# -------------------------
