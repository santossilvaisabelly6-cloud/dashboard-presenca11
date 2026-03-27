import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide", page_title="Board Program | Controle de Presença")

# ==========================================
# CONFIG
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ID da sua planilha (extraído da URL do Google Sheets)
# Exemplo: https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/edit
SPREADSHEET_ID = "1ev-amJE2ggWvyj-Vm-6GW4oqmNu7ZRSf_vrXLRP_lZA"

# Nome da aba da planilha que contém os dados
SHEET_NAME = "BOARD (NOVO)"  # Altere se necessário

# ==========================================
# 1. AUTENTICAÇÃO E CONEXÃO
# ==========================================

@st.cache_resource
def conectar_sheets():
    """
    Conecta ao Google Sheets usando as credenciais do arquivo JSON.
    Coloque o arquivo JSON na mesma pasta do app.py e referencie abaixo.
    """
    try:
        creds = Credentials.from_service_account_file(
            "credentials.json",  # Nome do seu arquivo JSON de credenciais
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except FileNotFoundError:
        st.error("❌ Arquivo 'credentials.json' não encontrado. Coloque-o na mesma pasta do app.py.")
        return None
    except Exception as e:
        st.error(f"❌ Erro ao autenticar: {e}")
        return None

# ==========================================
# 2. CARREGAR DADOS
# ==========================================

@st.cache_data(ttl=60)
def carregar_dados():
    client = conectar_sheets()
    if client is None:
        return pd.DataFrame()
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        dados = sheet.get_all_values()
        if not dados:
            return pd.DataFrame()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return pd.DataFrame()

# ==========================================
# 3. SALVAR DADOS NA PLANILHA
# ==========================================

def salvar_dados(df_editado):
    client = conectar_sheets()
    if client is None:
        return False
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # Pega os dados atuais para preservar linhas de cabeçalho e outras abas
        todos_dados = sheet.get_all_values()
        df_atual = pd.DataFrame(todos_dados)

        # Localiza a linha do header real (que contém NOME e TURMA)
        header_row_idx = None
        for i, row in df_atual.iterrows():
            row_upper = [str(v).upper() for v in row]
            if any("NOME" in v for v in row_upper) and any("TURMA" in v for v in row_upper):
                header_row_idx = i
                break

        if header_row_idx is None:
            st.error("Não foi possível localizar o cabeçalho na planilha.")
            return False

        # Converte df_editado para lista de listas
        linhas_novas = [df_editado.columns.tolist()] + df_editado.values.tolist()

        # Atualiza a partir da linha do header (1-indexed para o gspread)
        start_row = header_row_idx + 1  # gspread usa 1-indexed
        end_row = start_row + len(linhas_novas) - 1
        num_cols = len(df_editado.columns)
        end_col = chr(ord('A') + num_cols - 1)

        range_str = f"A{start_row}:{end_col}{end_row}"
        sheet.update(range_str, linhas_novas)

        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")
        return False

# ==========================================
# 4. DETECTAR HEADER
# ==========================================

def detectar_header(df):
    for i in range(len(df)):
        linha = df.iloc[i].astype(str).str.upper()
        if linha.str.contains("NOME").any() and linha.str.contains("TURMA").any():
            df.columns = df.iloc[i]
            df = df[i + 1:].reset_index(drop=True)
            return df, i
    st.error("Não foi possível identificar o header automaticamente.")
    return df, 0

# ==========================================
# 5. LIMPEZA
# ==========================================

def limpar_dados(df):
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, ~df.columns.duplicated()]
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df

# ==========================================
# 6. MAPEAR COLUNAS
# ==========================================

def mapear_colunas(df):
    def find_col(keyword):
        for col in df.columns:
            if keyword in col:
                return col
        return None
    return {
        "nome": find_col("NOME"),
        "turma": find_col("TURMA"),
        "guid": find_col("GUID"),
        "status_1": find_col("1º ENCONTRO") or find_col("STATUS - 1"),
        "status_2": find_col("2º ENCONTRO") or find_col("STATUS - 2"),
        "status_3": find_col("3º ENCONTRO") or find_col("STATUS - 3"),
    }

# ==========================================
# 7. ESTRUTURAR BASE
# ==========================================

def estruturar_base(df, colunas):
    df["nome"] = df[colunas["nome"]] if colunas["nome"] else ""
    df["turma"] = df[colunas["turma"]] if colunas["turma"] else ""
    df["guid"] = df[colunas["guid"]] if colunas["guid"] else ""
    df["status_1"] = df[colunas["status_1"]].astype(str).str.strip() if colunas["status_1"] else ""
    df["status_2"] = df[colunas["status_2"]].astype(str).str.strip() if colunas["status_2"] else ""
    df["status_3"] = df[colunas["status_3"]].astype(str).str.strip() if colunas["status_3"] else ""
    return df

# ==========================================
# 8. TRATAR TURMA / EDIÇÃO
# ==========================================

def tratar_turma(df):
    df["turma"] = df["turma"].astype(str).str.strip()
    split_cols = df["turma"].str.split(" - ", n=1, expand=True)
    if split_cols.shape[1] == 2:
        df["turma_nome"] = split_cols[0]
        df["edicao"] = split_cols[1]
    else:
        df["turma_nome"] = df["turma"]
        df["edicao"] = "Não identificado"
    return df

# ==========================================
# 9. CLASSIFICAÇÃO DE STATUS
# ==========================================

def classificar_status(df):
    status_all = (df["status_1"] + " " + df["status_2"] + " " + df["status_3"]).str.lower()
    df["reposicao"] = status_all.str.contains("repos", na=False)
    df["ausente"] = status_all.str.contains("ausente", na=False)
    df["confirmado"] = status_all.str.contains("confirmado", na=False)
    df["presente"] = status_all.str.contains("presente", na=False)
    return df

# ==========================================
# 10. KPIs
# ==========================================

def calcular_kpis(df):
    total = len(df)
    repos = int(df["reposicao"].sum())
    ausentes = int(df["ausente"].sum())
    confirmados = int(df["confirmado"].sum())
    presentes = int(df["presente"].sum())
    taxa_repos = (repos / total * 100) if total > 0 else 0
    return total, repos, ausentes, confirmados, presentes, taxa_repos

# ==========================================
# 11. DASHBOARD
# ==========================================

def gerar_dashboard(df, df_raw, header_row_idx):

    # ---- SIDEBAR FILTROS ----
    st.sidebar.title("🔎 Filtros")

    edicoes = ["Todas"] + sorted(df["edicao"].dropna().unique().tolist())
    edicao_sel = st.sidebar.selectbox("Edição", edicoes)

    df_filtrado = df if edicao_sel == "Todas" else df[df["edicao"] == edicao_sel]

    turmas = ["Todas"] + sorted(df_filtrado["turma_nome"].dropna().unique().tolist())
    turma_sel = st.sidebar.selectbox("Turma", turmas)

    df_filtrado = df_filtrado if turma_sel == "Todas" else df_filtrado[df_filtrado["turma_nome"] == turma_sel]

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

    # ---- TABS PRINCIPAIS ----
    tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "✏️ Editar Participantes", "➕ Adicionar Participante"])

    # ==========================
    # TAB 1 - VISÃO GERAL
    # ==========================
    with tab1:

        st.markdown(f"## 📊 Visão Geral{' — ' + turma_sel if turma_sel != 'Todas' else ''}")

        total, repos, ausentes, confirmados, presentes, taxa_repos = calcular_kpis(df_filtrado)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("👥 Participantes", total)
        c2.metric("✅ Presentes", presentes)
        c3.metric("❌ Ausentes", ausentes)
        c4.metric("🔁 Reposições", repos)
        c5.metric("📋 Taxa de Reposição", f"{taxa_repos:.1f}%")

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Participantes por Turma")
            participantes = df_filtrado.groupby("turma_nome")["nome"].count().sort_values(ascending=False)
            st.bar_chart(participantes)

        with col_b:
            st.subheader("Reposições por Turma")
            reposicoes = df_filtrado[df_filtrado["reposicao"]].groupby("turma_nome")["nome"].count().sort_values(ascending=False)
            if not reposicoes.empty:
                st.bar_chart(reposicoes)
            else:
                st.info("Nenhuma reposição encontrada.")

        st.divider()

        st.subheader("Lista de Ausentes")
        lista_ausentes = df_filtrado[df_filtrado["ausente"]][["nome", "guid", "turma_nome", "edicao", "status_1", "status_2", "status_3"]]
        if not lista_ausentes.empty:
            st.dataframe(lista_ausentes, use_container_width=True)
        else:
            st.info("Nenhum ausente encontrado.")

    # ==========================
    # TAB 2 - EDITAR PARTICIPANTES
    # ==========================
    with tab2:

        st.markdown("## ✏️ Editar Participantes")
        st.info("Edite os dados diretamente na tabela abaixo. Quando terminar, clique em **Salvar alterações**.")

        # Colunas editáveis
        colunas_edicao = mapear_colunas(df_raw)
        cols_para_editar = [
            colunas_edicao["nome"],
            colunas_edicao["guid"],
            colunas_edicao["turma"],
        ]
        cols_para_editar = [c for c in cols_para_editar if c is not None]

        df_para_editar = df_raw[cols_para_editar].copy()
        df_para_editar = df_para_editar[df_para_editar[colunas_edicao["guid"]].astype(str).str.strip() != ""]

        df_editado = st.data_editor(
            df_para_editar,
            use_container_width=True,
            num_rows="dynamic",
            key="editor_participantes"
        )

        if st.button("💾 Salvar alterações no Google Sheets", type="primary"):
            with st.spinner("Salvando..."):
                sucesso = salvar_dados(df_editado)
                if sucesso:
                    st.success("✅ Alterações salvas com sucesso!")
                    st.cache_data.clear()
                else:
                    st.error("❌ Erro ao salvar. Verifique as permissões da Service Account.")

    # ==========================
    # TAB 3 - ADICIONAR PARTICIPANTE
    # ==========================
    with tab3:

        st.markdown("## ➕ Adicionar Novo Participante")
        st.info("Preencha os campos abaixo para adicionar um novo participante diretamente na planilha.")

        colunas_edicao = mapear_colunas(df_raw)

        with st.form("form_novo_participante"):
            novo_nome = st.text_input("Nome Completo")
            novo_guid = st.text_input("GUID")

            turmas_disponiveis = sorted(df["turma"].dropna().unique().tolist())
            nova_turma = st.selectbox("Edição x Turma", turmas_disponiveis)

            submitted = st.form_submit_button("➕ Adicionar Participante", type="primary")

            if submitted:
                if not novo_nome or not novo_guid:
                    st.warning("⚠️ Nome e GUID são obrigatórios.")
                else:
                    try:
                        client = conectar_sheets()
                        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
                        todos = sheet.get_all_values()

                        # Acha a última linha com dado
                        ultima_linha = len(todos) + 1

                        # Monta nova linha vazia do mesmo tamanho
                        nova_linha = [""] * len(todos[0]) if todos else [""] * 10

                        # Preenche os campos que conhecemos
                        df_temp = pd.DataFrame(todos)
                        header_series = df_temp.iloc[header_row_idx]

                        for idx, val in enumerate(header_series):
                            val_upper = str(val).upper().strip()
                            if "NOME" in val_upper:
                                nova_linha[idx] = novo_nome
                            elif "GUID" in val_upper:
                                nova_linha[idx] = novo_guid
                            elif "TURMA" in val_upper or "EDIÇÃO" in val_upper:
                                nova_linha[idx] = nova_turma

                        sheet.append_row(nova_linha)
                        st.success(f"✅ Participante **{novo_nome}** adicionado com sucesso!")
                        st.cache_data.clear()

                    except Exception as e:
                        st.error(f"❌ Erro ao adicionar participante: {e}")

# ==========================================
# EXECUÇÃO
# ==========================================

st.title("📊 Dashboard - Controle de Presença | Board Program")

df_raw_inicial = carregar_dados()

if not df_raw_inicial.empty:
    df_raw, header_row_idx = detectar_header(df_raw_inicial.copy())
    df_raw = limpar_dados(df_raw)

    colunas = mapear_colunas(df_raw)
    df = estruturar_base(df_raw.copy(), colunas)
    df = tratar_turma(df)
    df = classificar_status(df)
    df = df[df["guid"].astype(str).str.strip() != ""]

    gerar_dashboard(df, df_raw, header_row_idx)
else:
    st.warning("⚠️ Nenhum dado carregado. Verifique a conexão com o Google Sheets.")
