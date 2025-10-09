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

# ==========================================================
# CONFIGURAÇÕES GLOBAIS
# ==========================================================

CORES_IMILE = {
    "azul": "#0052CC",
    "amarelo": "#FFC400",
    "cinza": "#2C3E50",
    "fundo": "#F4F7FC",
    "branco": "#FFFFFF"
}

TEMAS_POSSIVEIS = [
    "FALTA SEM JUSTIFICATIVA",
    "ABONO DE HORAS",
    "DECLARAÇÃO DE HORAS",
    "AJUSTE DE HORAS",
    "ATESTADO MÉDICO",
    "FOLGA HABILITADA",
    "SAÍDA ANTECIPADA"
]

# ==========================================================
# ESTILO VISUAL IMILE
# ==========================================================

def aplicar_estilo_imile():
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
    </style>
    """, unsafe_allow_html=True)

def header_imile():
    st.markdown("""
    <div class="header">
        <h1>IMILE</h1>
        <p>Assistente de Custos - Controle de Apontamentos</p>
    </div>
    """, unsafe_allow_html=True)

def card_boas_vindas():
    st.markdown("""
    <div class="card">
        <p>Bem-vindo ao <strong>Assistente de Custos da Imile</strong>! 
        Analise apontamentos de funcionários, valide horários e gere relatórios de forma clara e elegante.</p>
    </div>
    """, unsafe_allow_html=True)

def footer_imile():
    st.markdown("""
    <div class="footer">
        <p>© 2025 IMILE - Assistente de Custos | Todos os direitos reservados</p>
    </div>
    """, unsafe_allow_html=True)

# ==========================================================
# FUNÇÕES UTILITÁRIAS
# ==========================================================

def limpar_texto(texto: str) -> str:
    texto = texto.upper()
    texto = re.sub(r'[^A-Z0-9 ]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def normalizar_nome_coluna(nome: str) -> str:
    if not nome:
        return None
    nome = nome.upper()
    mapeamento = {
        "TRAB": "total_trabalhado",
        "NOTURNO": "total_noturno",
        "PREVIST": "horas_previstas",
        "FALTA": "faltas",
        "ATRASO": "horas_atraso",
        "EXTRA": "extra_50",
        "DSR": "desconta_dsr",
    }
    for chave, valor in mapeamento.items():
        if chave in nome:
            return valor
    return None

def padronizar_tempo(valor: str) -> str:
    if not valor:
        return "00:00"
    valor = valor.strip()
    if re.match(r"^\d{1,3}:\d{2}$", valor):
        return valor
    return "00:00"

def hora_para_minutos(hora: str) -> int:
    try:
        h, m = map(int, hora.split(":"))
        return h * 60 + m
    except:
        return 0

def limpa_valor(v):
    return str(v or "").strip()

def eh_horario(valor: str) -> bool:
    if not isinstance(valor, str) or ":" not in valor:
        return False
    partes = valor.split(":")
    if len(partes) != 2:
        return False
    h, m = partes
    if not (h.isdigit() and m.isdigit()):
        return False
    h, m = int(h), int(m)
    return 0 <= h < 24 and 0 <= m < 60

def pdf_possui_texto(pdf_file) -> bool:
    with pdfplumber.open(pdf_file) as pdf:
        return any(p.extract_text() and p.extract_text().strip() for p in pdf.pages)

# ==========================================================
# COMPONENTES VISUAIS
# ==========================================================

def alerta_pdf_imagem(mensagem: str):
    st.markdown(f"""
    <div style="
        padding: 20px;
        border: 2px solid {CORES_IMILE['amarelo']};
        background-color: {CORES_IMILE['fundo']};
        border-radius: 10px;
        margin-bottom: 10px;
    ">
        <strong>⚠️ Atenção:</strong> {mensagem}
    </div>
    """, unsafe_allow_html=True)

# ==========================================================
# TELA INICIAL
# ==========================================================

def tela_inicial():
    aplicar_estilo_imile()
    header_imile()
    card_boas_vindas()

    col1, col2, col3 = st.columns([3, 2, 2])
    with col2:
        if st.button("Iniciar 🚀"):
            st.session_state.iniciado = True

# ==========================================================
# PROCESSAMENTO DE PDFs
# ==========================================================

def achar_tema_mais_proximo(linha: str, lista_temas, limiar=0.6):
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

def processar_tabela_blitz(tabela, funcionario):
    if not tabela:
        return
    cabecalho = tabela[0]
    for linha_tabela in tabela:
        if linha_tabela[0] and "TOTAIS" in str(linha_tabela[0]).upper():
            for titulo, valor in zip(cabecalho, linha_tabela):
                chave = normalizar_nome_coluna(titulo)
                if chave:
                    if chave in ["faltas", "desconta_dsr"]:
                        funcionario[chave] = int(valor) if valor and str(valor).isdigit() else 0
                    else:
                        funcionario[chave] = padronizar_tempo(valor)
            if funcionario["extra_50"] == funcionario["horas_previstas"]:
                funcionario["extra_50"] = "00:00"

def processar_texto_blitz(linhas, funcionario):
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
        tema_encontrado = achar_tema_mais_proximo(linha_final, TEMAS_POSSIVEIS)
        if tema_encontrado:
            funcionario[tema_encontrado] += 1

def processar_pdf_blitz(uploaded_file):
    # 🚨 Rejeita PDF escaneado sem perguntar
    with pdfplumber.open(uploaded_file) as pdf_temp:
        tem_texto = any(p.extract_text() and p.extract_text().strip() for p in pdf_temp.pages)

    if not tem_texto:
        alerta_pdf_imagem("Arquivo rejeitado: PDF escaneado (imagem) não é suportado.")
        st.warning("⚠️ Por favor, anexe um PDF com texto selecionável.")
        # Limpa o arquivo e reinicia
        st.session_state["uploaded_blitz"] = None
        st.rerun()
        return

    st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")

    dados_funcionarios = []
    detalhes = []

    with pdfplumber.open(uploaded_file) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text() or ""
            tabela = pagina.extract_table()
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
            for tema in TEMAS_POSSIVEIS:
                funcionario[tema] = 0

            processar_texto_blitz(linhas, funcionario)
            processar_tabela_blitz(tabela, funcionario)

            if funcionario["faltas"] > 0 or funcionario["desconta_dsr"] > 0:
                funcionario["status"] = "NOK"
            else:
                funcionario["status"] = "OK"

            dados_funcionarios.append(funcionario)

            if tabela:
                for linha_detalhe in tabela[1:]:
                    linha_detalhe = [celula for celula in linha_detalhe if celula not in [None, '']]
                    if not linha_detalhe or str(linha_detalhe[0]).upper() == "TOTAIS":
                        continue
                    data_split = str(linha_detalhe[0]).split(" - ")
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

    df = pd.DataFrame(dados_funcionarios).fillna(0)
    df_detalhe = pd.DataFrame(detalhes)

    # Validação de horas
    df_detalhe["Validação da hora trabalhada"] = df_detalhe.apply(
        lambda row: "Carga Horaria Completa - Fez Hora Extra" if (
            hora_para_minutos(limpa_valor(row.get("total_trabalhado"))) >
            hora_para_minutos(limpa_valor(row.get("horas_previstas")))
        ) else "Carga Horaria Completa" if (
            hora_para_minutos(limpa_valor(row.get("total_trabalhado"))) ==
            hora_para_minutos(limpa_valor(row.get("horas_previstas")))
        ) else "Carga Horaria Incompleta", axis=1
    )

    # Situação do dia
    def validar_dia(row):
        valores = [limpa_valor(row["ent_1"]), limpa_valor(row["sai_1"]),
                   limpa_valor(row["ent_2"]), limpa_valor(row["sai_2"])]
        textos = [v for v in valores if v and not eh_horario(v)]
        if textos:
            return textos[0].upper()
        horarios_validos = [eh_horario(v) for v in valores]
        if all(horarios_validos):
            return "Dia normal de trabalho"
        elif any(horarios_validos):
            return "Presença parcial"
        else:
            return "Dia incompleto"

    df_detalhe["Situação"] = df_detalhe.apply(validar_dia, axis=1)

    # Contagem por situação
    for sit in df_detalhe["Situação"].unique():
        nome_col = f"Qtd - {sit}"
        df_detalhe[nome_col] = df_detalhe.groupby("cpf")["Situação"].transform(lambda x: (x == sit).sum())

    # Preparar Excel
    output_consolidado = BytesIO()
    df_consolidado = df.drop(columns=TEMAS_POSSIVEIS)
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

def processar_pdf_pollynesse(uploaded_file):
    # 🚨 Rejeita PDF escaneado sem perguntar
    with pdfplumber.open(uploaded_file) as pdf_temp:
        tem_texto = any(p.extract_text() and p.extract_text().strip() for p in pdf_temp.pages)

    if not tem_texto:
        alerta_pdf_imagem("Arquivo rejeitado: PDF escaneado (imagem) não é suportado.")
        st.warning("⚠️ Por favor, anexe um PDF com texto selecionável.")
        # Limpa o arquivo e reinicia
        st.session_state["uploaded_polly"] = None
        st.rerun()
        return

    st.success(f"Arquivo {uploaded_file.name} carregado com sucesso!")

    textos_paginas = []
    tabelas_encontradas = []

    with pdfplumber.open(uploaded_file) as pdf:
        st.write(f"📚 Total de páginas detectadas: **{len(pdf.pages)}**")
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text() or ""
            if texto.strip():
                textos_paginas.append(f"### Página {i+1}\n\n{texto}\n\n")
            else:
                textos_paginas.append(f"### Página {i+1}\n> ⚠️ Nenhum texto detectado (imagem escaneada)")
            tabela = pagina.extract_table()
            if tabela:
                df_tabela = pd.DataFrame(tabela[1:], columns=tabela[0])
                tabelas_encontradas.append((i+1, df_tabela))

    st.subheader("📜 Texto extraído")
    for bloco in textos_paginas:
        st.markdown(bloco)

    st.subheader("📊 Tabelas detectadas")
    if tabelas_encontradas:
        for i, tabela_df in tabelas_encontradas:
            st.markdown(f"**Tabela detectada na página {i}:**")
            st.dataframe(tabela_df)
    else:
        st.info("Nenhuma tabela detectada em nenhuma página.")

    texto_completo = "\n\n".join(textos_paginas)
    buffer = BytesIO()
    buffer.write(texto_completo.encode("utf-8"))
    buffer.seek(0)

    st.download_button(
        label="⬇️ Baixar texto extraído (D0)",
        data=buffer,
        file_name="texto_extraido_D0.txt",
        mime="text/plain"
    )

# ==========================================================
# INTERFACE PRINCIPAL
# ==========================================================

def main():
    st.set_page_config(page_title="Imile - Assistente de Custos", layout="wide", page_icon="📊")

    if "iniciado" not in st.session_state:
        st.session_state.iniciado = False

    if not st.session_state.iniciado:
        tela_inicial()
        footer_imile()
        return

    aplicar_estilo_imile()
    header_imile()

    tab1, tab2, tab3 = st.tabs(["📂 Blitz", "📂 Pollynesse", "🧱 D0 - Em manutenção"])

    with tab1:
        st.header("📂 Upload do PDF de Apontamentos")
        uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"], key="uploaded_blitz")
        if uploaded_file:
            processar_pdf_blitz(uploaded_file)

    with tab2:
        st.header("📄 Extração de Texto e Tabelas - Polly")
        uploaded_polly = st.file_uploader("Selecione o arquivo PDF (Polly)", type=["pdf"], key="uploaded_polly")
        if uploaded_polly:
            # 1. Verifica se é PDF escaneado
            with pdfplumber.open(uploaded_polly) as pdf_temp:
                tem_texto = any(p.extract_text() and p.extract_text().strip() for p in pdf_temp.pages)

            if not tem_texto:
                alerta_pdf_imagem("PDF escaneado detectado. Será realizada leitura via OCR (Tesseract).")
                st.info("🔍 Iniciando OCR... isso pode levar alguns segundos.")

                # --- OCR + DataFrame (código já validado) ---
                import pytesseract
                from pdf2image import convert_from_path
                from io import BytesIO
                import re
                import os

                # Salva o arquivo em disco temporário para pdf2image
                with open("temp_polly.pdf", "wb") as f:
                    f.write(uploaded_polly.read())

                # Regexes flexíveis
                re_nome        = re.compile(r"NOME DO FUNCIONÁRIO[:\s]*(.+?)(?:\n|\r)", re.IGNORECASE | re.UNICODE)
                re_matricula   = re.compile(r"N[ÚU]MERO DE MATR[ÍI]CULA[:\s]*(\d+)", re.IGNORECASE | re.UNICODE)
                re_cpf         = re.compile(r"CPF DO FUNCIONÁRIO[:\s]*(\d+)", re.IGNORECASE | re.UNICODE)
                re_admissao    = re.compile(r"DATA DE ADMISS[ÃA]O DO FUNCIONÁRIO[:\s]*(\d{2}/\d{2}/\d{4})", re.IGNORECASE | re.UNICODE)
                re_dia_linha   = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(SEG|TER|QUA|QUI|SEX|SAB|DOM)\s*(.+)", re.IGNORECASE | re.UNICODE)

                images = convert_from_path("temp_polly.pdf", dpi=300)
                rows = []

                for idx, img in enumerate(images):
                    texto = pytesseract.image_to_string(img, lang='por')
                    nome      = re_nome.search(texto)
                    matricula = re_matricula.search(texto)
                    cpf       = re_cpf.search(texto)
                    admissao  = re_admissao.search(texto)

                    nome      = nome.group(1).strip() if nome else None
                    matricula = matricula.group(1).strip() if matricula else None
                    cpf       = cpf.group(1).strip() if cpf else None
                    admissao  = admissao.group(1).strip() if admissao else None

                    for match in re_dia_linha.finditer(texto):
                        dia_str, dia_semana, resto = match.groups()
                        dia = int(dia_str[:2])
                        resto = resto.strip()

                        trabalhou = True
                        motivo = ""
                        observacoes = ""

                        if "Folga" in resto:
                            trabalhou = False
                            motivo = "Folga"
                        elif "Falta" in resto:
                            trabalhou = False
                            motivo = "Falta"
                        elif "Atestado" in resto:
                            trabalhou = False
                            motivo = "Atestado"
                            cid_match = re.search(r"CID\s+([A-Z0-9\.]+)", resto)
                            if cid_match:
                                observacoes = f"Atestado Médico (CID {cid_match.group(1)})"
                        elif "Abonar ausencia" in resto:
                            trabalhou = False
                            motivo = "Abonado"

                        horarios = re.findall(r"(\d{2}:\d{2})", resto)
                        entrou_1 = horarios[0] if len(horarios) >= 1 else None
                        saiu_1   = horarios[1] if len(horarios) >= 2 else None
                        entrou_2 = horarios[2] if len(horarios) >= 3 else None
                        saiu_2   = horarios[3] if len(horarios) >= 4 else None

                        extras = re.findall(r"(\d{2}:\d{2})\s+(\d{2}:\d{2})", resto)
                        horas_extras = extras[0][0] if extras else None

                        rows.append({
                            "nome": nome,
                            "matricula": matricula,
                            "cpf": cpf,
                            "data_admissao": admissao,
                            "dia": dia,
                            "dia_semana": dia_semana,
                            "entrou_1": entrou_1,
                            "saiu_1": saiu_1,
                            "entrou_2": entrou_2,
                            "saiu_2": saiu_2,
                            "trabalhou": trabalhou,
                            "motivo": motivo,
                            "horas_extras": horas_extras,
                            "observacoes": observacoes
                        })

                df_diario = pd.DataFrame(rows)
                df_resumo = df_diario.groupby(['nome', 'matricula']).agg(
                    dias_trabalhados=('trabalhou', 'sum'),
                    dias_nao_trabalhados=('trabalhou', lambda x: (x == False).sum()),
                    atestados=('motivo', lambda x: (x == 'Atestado').sum()),
                    faltas=('motivo', lambda x: (x == 'Falta').sum()),
                    folgas=('motivo', lambda x: (x == 'Folga').sum()),
                    abonados=('motivo', lambda x: (x == 'Abonado').sum()),
                    horas_extras=('horas_extras', lambda x: pd.to_timedelta(x + ':00', errors='coerce').sum() if x.notna().any() else pd.Timedelta(0))
                ).reset_index()

                # Download
                output_diario = BytesIO()
                df_diario.to_excel(output_diario, index=False)
                output_diario.seek(0)

                output_resumo = BytesIO()
                df_resumo.to_excel(output_resumo, index=False)
                output_resumo.seek(0)

                st.download_button("⬇️ Baixar relatório diário (OCR)", output_diario, "relatorio_diario_polly.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.download_button("⬇️ Baixar resumo por funcionário (OCR)", output_resumo, "resumo_por_funcionario_polly.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                # Limpa arquivo temporário
                if os.path.exists("temp_polly.pdf"):
                    os.remove("temp_polly.pdf")

            else:
                # PDF com texto selecionável - comportamento original
                st.success(f"Arquivo {uploaded_polly.name} carregado com sucesso!")
                textos_paginas = []
                tabelas_encontradas = []

                with pdfplumber.open(uploaded_polly) as pdf:
                    st.write(f"📚 Total de páginas detectadas: **{len(pdf.pages)}**")
                    for i, pagina in enumerate(pdf.pages):
                        texto = pagina.extract_text() or ""
                        if texto.strip():
                            textos_paginas.append(f"### Página {i+1}\n\n{texto}\n\n")
                        else:
                            textos_paginas.append(f"### Página {i+1}\n> ⚠️ Nenhum texto detectado (imagem escaneada)")
                        tabela = pagina.extract_table()
                        if tabela:
                            df_tabela = pd.DataFrame(tabela[1:], columns=tabela[0])
                            tabelas_encontradas.append((i+1, df_tabela))

                st.subheader("📜 Texto extraído")
                for bloco in textos_paginas:
                    st.markdown(bloco)

                st.subheader("📊 Tabelas detectadas")
                if tabelas_encontradas:
                    for i, tabela_df in tabelas_encontradas:
                        st.markdown(f"**Tabela detectada na página {i}:**")
                        st.dataframe(tabela_df)
                else:
                    st.info("Nenhuma tabela detectada em nenhuma página.")

                texto_completo = "\n\n".join(textos_paginas)
                buffer = BytesIO()
                buffer.write(texto_completo.encode("utf-8"))
                buffer.seek(0)

                st.download_button(
                    label="⬇️ Baixar texto extraído (D0)",
                    data=buffer,
                    file_name="texto_extraido_D0.txt",
                    mime="text/plain"
                )

    with tab3:
        st.header("🧱 D0 - Em manutenção")
        st.info("Esta aba está em manutenção e será liberada em breve.")

    footer_imile()

# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":
    main()
