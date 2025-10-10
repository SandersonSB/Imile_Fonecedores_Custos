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

# ==========================================================
# FUNÇÃO BLITZ COMPLETA (INCLUÍDA AQUI)
# ==========================================================
def processar_pdf_blitz(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        funcionarios = []
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue

            linhas = texto.splitlines()
            funcionario = {
                "nome": "",
                "cpf": "",
                "matricula": "",
                "cargo": "",
                "centro_custo": "",
                "total_trabalhado": "00:00",
                "total_noturno": "00:00",
                "horas_previstas": "00:00",
                "faltas": 0,
                "horas_atraso": "00:00",
                "extra_50": "00:00",
                "desconta_dsr": 0,
            }

            # Inicializa temas
            for tema in TEMAS_POSSIVEIS:
                funcionario[tema] = 0

            processar_texto_blitz(linhas, funcionario)
            tabela = pagina.extract_table()
            if tabela:
                processar_tabela_blitz(tabela, funcionario)

            funcionarios.append(funcionario)

    st.success("✅ PDF processado com sucesso!")
    df = pd.DataFrame(funcionarios)
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="apontamentos_blitz.csv",
        mime="text/csv"
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

# ------------------------------------------------------------------
# ABA 2  –  Extração de Texto e Tabelas + OCR por coordenadas (Polly)
# ------------------------------------------------------------------
    with tab2:
        st.header("📄 Extração de Texto e Tabelas - Polly")
        uploaded_polly = st.file_uploader(
            "Selecione o arquivo PDF (Polly)", type=["pdf"], key="uploaded_polly"
        )
    
        if uploaded_polly:
            import pdfplumber, PyPDF2, shutil, pytesseract, tempfile, os, re, io
            from pdf2image import convert_from_path
            from io import BytesIO
            import pandas as pd
    
            def erro(msg):
                st.error(msg)
                st.stop()
    
            # ---------- valida ----------
            try:
                uploaded_polly.seek(0)
                reader = PyPDF2.PdfReader(uploaded_polly)
                num_pages = len(reader.pages)
            except Exception:
                erro("PDF inválido ou corrompido.")
    
            # ---------- tem texto? ----------
            with pdfplumber.open(uploaded_polly) as pdf_temp:
                tem_texto = any(p.extract_text() and p.extract_text().strip() for p in pdf_temp.pages)
    
            if tem_texto:
                st.success(f"Arquivo {uploaded_polly.name} carregado com texto selecionável!")
                textos, tabelas = [], []
                with pdfplumber.open(uploaded_polly) as pdf:
                    st.write(f"📚 Total de páginas: **{len(pdf.pages)}**")
                    for i, p in enumerate(pdf.pages):
                        texto = p.extract_text() or ""
                        textos.append(f"### Página {i+1}\n\n{texto}\n\n")
                        tbl = p.extract_table()
                        if tbl:
                            tabelas.append((i+1, pd.DataFrame(tbl[1:], columns=tbl[0])))
    
                st.subheader("📜 Texto extraído")
                for bloco in textos:
                    st.markdown(bloco)
    
                st.subheader("📊 Tabelas detectadas")
                if tabelas:
                    for i, df in tabelas:
                        st.markdown(f"**Página {i}**")
                        st.dataframe(df)
                else:
                    st.info("Nenhuma tabela detectada.")
    
                txt = "\n\n".join(textos)
                buf = BytesIO()
                buf.write(txt.encode("utf-8"))
                buf.seek(0)
                st.download_button(
                    "⬇️ Texto completo (D0)", buf, "texto_extraido_D0.txt", "text/plain"
                )
    
            else:
                if shutil.which("tesseract") is None:
                    erro("Tesseract não está no PATH do servidor.")
    
                st.info("🔍 PDF escaneado – OCR por coordenadas (todas as páginas).")
                if st.button("Rodar OCR completo"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_polly.getbuffer())
                        tmp_path = tmp.name
    
                    # ---------- funções auxiliares ----------
                    def ocr_page(image):
                        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DATAFRAME, lang="por")
                        return data[data.conf > 0].copy()
    
                    def slice_table(df_words, y0, y1, x0, x1):
                        return df_words[
                            (df_words.top >= y0) & (df_words.top + df_words.height <= y1) &
                            (df_words.left >= x0) & (df_words.left + df_words.width <= x1)
                        ]
    
                    def group_rows(df_crop, tol=6):
                        df_crop = df_crop.sort_values(["top", "left"])
                        rows = {}
                        for _, w in df_crop.iterrows():
                            key = int(round(w.top / tol) * tol)
                            rows.setdefault(key, []).append(w)
                        return rows
    
                    def split_cols(row_words, cuts):
                        cols = [""] * (len(cuts) - 1)
                        for w in row_words:
                            cx = w.left + w.width // 2
                            for i in range(len(cuts) - 1):
                                if cuts[i] <= cx < cuts[i + 1]:
                                    cols[i] += " " + w.text
                                    break
                        return [c.strip() for c in cols]
    
                    # ---------- regex leves só para capturar cabeçalho ----------
                    re_cab = re.compile(
                        r"nome\s*do\s*funcion[áa]rio\s*:?\s*(.*?)\s*n[úu]mero\s*de\s*matr[íi]cula\s*:?\s*(\d+)",
                        flags=re.I | re.S,
                    )
                    re_cpf = re.compile(r"cpf\s*do\s*funcion[áa]rio\s*:?\s*(\d+)", flags=re.I)
                    re_adm = re.compile(
                        r"data\s*de\s*admiss[ãa]o\s*do\s*funcion[áa]rio\s*:?\s*(\d{2}[/\-.]\d{2}[/\-.]\d{4})",
                        flags=re.I,
                    )
    
                    # ---------- colunas finais ----------
                    COLS = [
                        "pagina", "nome", "cpf", "matricula", "data_admissao",
                        "dia", "dia_semana", "ent_1", "sai_1", "ent_2", "sai_2",
                        "ent_3", "sai_3", "situacao", "extras"
                    ]
    
                    detalhes = []
                    bar = st.progress(0)
    
                    for pg in range(1, num_pages + 1):
                        imgs = convert_from_path(
                            tmp_path,
                            dpi=200,
                            first_page=pg,
                            last_page=pg,
                            grayscale=True,
                            thread_count=1,
                            use_pdftocairo=True,
                        )
                        img = imgs[0]
                        df_words = ocr_page(img)
    
                        # ---------- cabeçalho ----------
                        txt_full = " ".join(df_words.text.astype(str).tolist())
                        nome = mat = cpf = adm = ""
                        m = re_cab.search(txt_full)
                        if m:
                            nome = m.group(1).replace("\n", " ").strip()
                            mat = m.group(2).strip()
                        m = re_cpf.search(txt_full)
                        if m:
                            cpf = m.group(1).strip()
                        m = re_adm.search(txt_full)
                        if m:
                            adm = m.group(1).strip()
    
                        # ---------- área da tabela (ajuste seus valores aqui) ----------
                        h, w = img.size[1], img.size[0]
                        y0 = int(h * 0.32)  # começo
                        y1 = int(h * 0.90)  # fim
                        x0 = int(w * 0.05)
                        x1 = int(w * 0.95)
                        cuts = [int(w * p) for p in [0.05, 0.18, 0.30, 0.42, 0.54, 0.64, 0.74, 0.84, 0.92, 1.0]]
    
                        df_crop = slice_table(df_words, y0, y1, x0, x1)
                        rows = group_rows(df_crop, tol=8)
    
                        for y in sorted(rows):
                            cols = split_cols(rows[y], cuts)
                            # ---------- garante 10 colunas ----------
                            while len(cols) < 10:
                                cols.append("")
    
                            dia_str = cols[0]
                            dia_sem = cols[1].upper()
                            horas = [h for h in cols[2:8] if h]
                            ent1, sai1, ent2, sai2, ent3, sai3 = (horas + [""] * 6)[:6]
                            situacao = cols[8] if cols[8] else "Dia normal"
                            extras = cols[9] if cols[9] else "00:00"
    
                            detalhes.append(
                                {
                                    "pagina": pg,
                                    "nome": nome,
                                    "cpf": cpf,
                                    "matricula": mat,
                                    "data_admissao": adm,
                                    "dia": dia_str,
                                    "dia_semana": dia_sem,
                                    "ent_1": ent1,
                                    "sai_1": sai1,
                                    "ent_2": ent2,
                                    "sai_2": sai2,
                                    "ent_3": ent3,
                                    "sai_3": sai3,
                                    "situacao": situacao,
                                    "extras": extras,
                                }
                            )
    
                        bar.progress(pg / num_pages)
    
                    os.unlink(tmp_path)
    
                    # ---------- monta DataFrames ----------
                    df_det = pd.DataFrame(detalhes, columns=COLS)
                    if not df_det.empty:
                        resumo = (
                            df_det.groupby(["nome", "cpf", "matricula", "data_admissao"], dropna=False)
                            .agg(
                                dias_trabalhados=("situacao", lambda x: (x == "Dia normal").sum()),
                                dias_nao_trabalhados=("situacao", lambda x: (x != "Dia normal").sum()),
                                atestados=("situacao", lambda x: (x == "Atestado").sum()),
                                faltas=("situacao", lambda x: (x == "Falta").sum()),
                                folgas=("situacao", lambda x: (x == "Folga").sum()),
                                abonados=("situacao", lambda x: (x == "Abonado").sum()),
                                horas_extras=("extras", lambda x: pd.to_timedelta(x.add(":00")).sum()),
                            )
                            .reset_index()
                        )
                        resumo["horas_extras"] = resumo["horas_extras"].dt.components.apply(
                            lambda c: f"{c.hours:02d}:{c.minutes:02d}", axis=1
                        )
    
                        buf1 = BytesIO()
                        df_det.to_excel(buf1, index=False)
                        buf1.seek(0)
                        st.download_button("⬇️ detalhe_funcionario.xlsx", buf1, "detalhe_funcionario.xlsx")
    
                        buf2 = BytesIO()
                        resumo.to_excel(buf2, index=False)
                        buf2.seek(0)
                        st.download_button("⬇️ resumo_funcionario.xlsx", buf2, "resumo_funcionario.xlsx")
    
                        st.success("Downloads prontos – nada mudou no restante do app!")
                    else:
                        st.warning("Nenhum dia/horário foi capturado via OCR.")
    with tab3:
        st.header("🧱 D0 - Em manutenção")
        st.info("Esta aba está em manutenção e será liberada em breve.")

    footer_imile()

# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":
    main()
