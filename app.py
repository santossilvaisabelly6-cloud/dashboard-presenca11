import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("📊 Dashboard - Controle de Presença | Board Program")

# ==========================================
# CONFIG
# ==========================================

URL_SHEETS = "https://docs.google.com/spreadsheets/d/1ev-amJE2ggWvyj-Vm-6GW4oqmNu7ZRSf_vrXLRP_lZA/export?format=csv"

# ==========================================
# 1. CARREGAR DADOS
# ==========================================

@st.cache_data
def carregar_dados():
    try:
        df = pd.read_csv(URL_SHEETS)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# ==========================================
# 2. DETECTAR HEADER AUTOMATICAMENTE
# ==========================================

def detectar_header(df):
    """
    Procura automaticamente a linha que contém os nomes das colunas
    """
    for i in range(len(df)):
        linha = df.iloc[i].astype(str).str.upper()

        if (
            linha.str.contains("NOME").any()
            and linha.str.contains("TURMA").any()
        ):
            df.columns = df.iloc[i]
            df = df[i + 1:].reset_index(drop=True)
            return df

    st.error("Não foi possível identificar o header automaticamente.")
    return df

# ==========================================
# 3. LIMPEZA E PADRONIZAÇÃO
# ==========================================

def limpar_dados(df):

    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, ~df.columns.duplicated()]

    df.columns = df.columns.astype(str).str.strip().str.upper()

    return df

# ==========================================
# 4. IDENTIFICAR COLUNAS
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
        "status": find_col("STATUS"),
        "email": find_col("MAIL") or find_col("EMAIL")
    }

# ==========================================
# 5. ESTRUTURAR BASE
# ==========================================

def estruturar_base(df, colunas):

    df["nome"] = df[colunas["nome"]] if colunas["nome"] else ""
    df["turma"] = df[colunas["turma"]] if colunas["turma"] else ""
    df["status"] = df[colunas["status"]] if colunas["status"] else ""

    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace("nan", "")
    )

    return df

# ==========================================
# 6. TRATAR TURMA / EDIÇÃO
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
# 7. CLASSIFICAÇÃO DE STATUS
# ==========================================

def classificar_status(df):

    df["reposicao"] = df["status"].str.contains("repos", na=False)
    df["ausente"] = df["status"].str.contains("ausente", na=False)
    df["confirmado"] = df["status"].str.contains("confirmado", na=False)

    return df

# ==========================================
# 8. KPIs
# ==========================================

def calcular_kpis(df):

    total = len(df)
    repos = df["reposicao"].sum()
    ausentes = df["ausente"].sum()
    confirmados = df["confirmado"].sum()

    taxa_repos = (repos / total * 100) if total > 0 else 0

    return total, repos, ausentes, confirmados, taxa_repos

# ==========================================
# 9. DASHBOARD
# ==========================================

def gerar_dashboard(df):

    # KPIs GERAIS
    st.markdown("## 📊 Visão Geral")

    total, repos, ausentes, confirmados, taxa_repos = calcular_kpis(df)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Participantes", total)
    c2.metric("Reposições", repos)
    c3.metric("Ausentes", ausentes)
    c4.metric("Confirmados", confirmados)

    st.metric("Taxa de Reposição", f"{taxa_repos:.1f}%")

    st.divider()

    # GRÁFICOS
    st.markdown("## 📈 Análises")

    st.subheader("Participantes por Turma")
    participantes = df.groupby("turma_nome")["nome"].count().sort_values(ascending=False)
    st.bar_chart(participantes)

    st.subheader("Reposições por Turma")
    reposicoes = df[df["reposicao"]].groupby("turma_nome")["nome"].count().sort_values(ascending=False)
    st.bar_chart(reposicoes)

    st.subheader("Distribuição de Status por Turma")

    df_valid = df[df["status"] != ""]

    status_por_turma = (
        df_valid.groupby(["turma_nome", "status"])
        .size()
        .reset_index(name="quantidade")
    )

    st.bar_chart(
        status_por_turma,
        x="turma_nome",
        y="quantidade",
        color="status"
    )

    st.divider()

    # FILTROS
    st.sidebar.title("Filtros")

    edicao = st.sidebar.selectbox(
        "Edição",
        sorted(df["edicao"].dropna().unique())
    )

    df_filtrado = df[df["edicao"] == edicao]

    turma = st.sidebar.selectbox(
        "Turma",
        sorted(df_filtrado["turma_nome"].dropna().unique())
    )

    df_filtrado = df_filtrado[df_filtrado["turma_nome"] == turma]

    # KPIs FILTRADOS
    st.markdown(f"## 📌 Resumo: {turma}")

    total, repos, ausentes, confirmados, taxa_repos = calcular_kpis(df_filtrado)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Participantes", total)
    c2.metric("Reposições", repos)
    c3.metric("Ausentes", ausentes)
    c4.metric("Confirmados", confirmados)

    st.metric("Taxa de Reposição", f"{taxa_repos:.1f}%")

    st.divider()

    # LISTAS
    st.subheader("Lista de Reposições")

    lista_repos = df_filtrado[df_filtrado["reposicao"]]

    if not lista_repos.empty:
        st.dataframe(
            lista_repos[["nome", "turma_nome", "edicao", "status"]],
            use_container_width=True
        )
    else:
        st.info("Nenhuma reposição encontrada")

    st.subheader("Lista de Ausentes")

    lista_ausentes = df_filtrado[df_filtrado["ausente"]]

    if not lista_ausentes.empty:
        st.dataframe(
            lista_ausentes[["nome", "turma_nome", "edicao", "status"]],
            use_container_width=True
        )
    else:
        st.info("Nenhum ausente")

# ==========================================
# EXECUÇÃO
# ==========================================

df = carregar_dados()

if not df.empty:
    df = detectar_header(df)
    df = limpar_dados(df)
    colunas = mapear_colunas(df)
    df = estruturar_base(df, colunas)
    df = tratar_turma(df)
    df = classificar_status(df)

    gerar_dashboard(df)