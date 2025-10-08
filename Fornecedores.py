# ==========================================================
# Fornecedores.py - Sistema de Processamento de Fornecedores
# Empresa: Imile (Cores: Azul e Amarelo)
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

def estilo_pagina():
    st.markdown(f"""
        <style>
        .splash-container {{
            display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; min-height: 80vh;
        }}
        .desc-text {{
            color: {CORES_IMILE['cinza']}; font-size: 18px; max-width: 700px; margin: 10px auto 30px auto;
        }}
        div.stButton {{ display: flex; justify-content: center; }}
        div.stButton > button {{
            height: 60px; width: 250px; font-size: 22px; background-color: {CORES_IMILE['azul']}; color: white;
        }}
        div.stButton > button:hover {{
            background-color: {CORES_IMILE['amarelo']}; transform: scale(1.05); transition: all 0.3s ease;
        }}
        </style>
    """, unsafe_allow_html=True)

# ==========================================================
# TELA INICIAL
# ==========================================================

def tela_inicial():
    estilo_pagina()
    st.markdown(f"""
        <div class="splash-container">
            <h1 style="color: {CORES_IMILE['azul']};">📊 Sistema de Processamento de Dados de Fornecedores</h1>
            <p class="desc-text">
                Este aplicativo processa apontamentos de funcionários em PDF, aplica regras de validação de horários e situações, e gera relatórios finais prontos para análise.
            </p>
            <img src="https://github.com/SandersonSB/Imile_Fonecedores_Custos/blob/main/Gemini_Generated_Image_wjo0iiwjo0iiwjo0.png?raw=true" width="600">
        </div>
    """, unsafe_allow_html=True)

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

    # ---------- restante do processamento ----------
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
    st.set_page_config(page_title="Imile - Processamento de Fornecedores", layout="wide", page_icon="📊")

    if "iniciado" not in st.session_state:
        st.session_state.iniciado = False

    if not st.session_state.iniciado:
        tela_inicial()
        return

    tab1, tab2, tab3 = st.tabs(["📂 Blitz", "📄 Pollynesse (D0)", "🧱 D0 - Em manutenção"])

    with tab1:
        st.header("📂 Upload do PDF de Apontamentos")
        uploaded_file = st.file_uploader("Escolha o arquivo PDF", type=["pdf"], key="uploaded_blitz")
        if uploaded_file:
            processar_pdf_blitz(uploaded_file)

    with tab2:
        st.header("📄 Extração de Texto e Tabelas - Polly")
        uploaded_polly = st.file_uploader("Selecione o arquivo PDF (Polly)", type=["pdf"], key="uploaded_polly")
        if uploaded_polly:
            processar_pdf_pollynesse(uploaded_polly)

    with tab3:
        st.header("🧱 D0 - Em manutenção")
        st.info("Esta aba está em manutenção e será liberada em breve.")

# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":
    main()
