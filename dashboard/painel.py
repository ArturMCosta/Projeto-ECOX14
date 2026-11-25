"""
Como executar, a partir da raiz do projeto:
    streamlit run dashboard/painel.py
"""

import streamlit as st

import consultas

st.set_page_config(
    page_title="Expectativa de vida por país",
    page_icon="📊",
    layout="wide",
)


def br(valor, casas=1):
    """Numero no padrao brasileiro, com virgula decimal.

    Formatacao e assunto de apresentacao, por isso mora aqui e nao no modulo
    de consultas.
    """
    if valor is None or valor != valor:  # None ou NaN
        return "sem dado"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def pct(valor, casas=2):
    """Percentual, ou 'sem dado' quando a media nao existe."""
    if valor is None or valor != valor:
        return "sem dado"
    return br(valor, casas) + "%"


# ------------------------------------------------------------ abertura
st.title("Expectativa de vida por país")
st.caption(
    "Camada Ouro do projeto: OMS e Banco Mundial, "
    "tratados e modelados pelo pipeline."
)

if not consultas.banco_existe():
    st.error(
        "Banco não encontrado.\n\n"
        "Rode o pipeline antes:  python src/pipeline.py"
    )
    st.stop()

# ------------------------------------------------------------- filtros
with st.sidebar:
    st.header("Filtros")
    regiao = st.selectbox("Região", consultas.regioes()["regiao"])
    ano = int(st.selectbox("Ano", consultas.anos()["ano"]))
    sexo = st.selectbox(
        "Sexo",
        consultas.sexos()["sexo"],
        help=(
            "A série tem três recortes por país e ano: total, feminino e "
            "masculino. Escolha um só para não contar o mesmo país três vezes."
        ),
    )
    st.divider()
    st.caption(
        "Os filtros viram parâmetro na consulta, e não texto concatenado."
    )

dados = consultas.indicador_por_regiao(regiao, ano, sexo)

if dados.empty:
    st.warning("Nenhum registro para esse filtro.")
    st.stop()

# -------------------------------------------------------- cartoes
resumo = consultas.resumo_da_regiao(regiao, ano, sexo).iloc[0]

c1, c2, c3 = st.columns(3)
c1.metric("Países na região", br(resumo["paises"], 0))
c2.metric("Expectativa média", br(resumo["media"], 1) + " anos")
c3.metric(
    "Variação média",
    pct(resumo["variacao_media"]),
    help="Média da variação em relação ao ano anterior, no mesmo sexo.",
)

st.divider()

# -------------------------------------------------------- graficos
esq, dir_ = st.columns([3, 2])

with esq:
    st.subheader(f"Dez maiores em {regiao}, {ano}")
    st.bar_chart(
        dados.head(10),
        x="pais_nome",
        y="expectativa_vida",
        color="#1B3A5F",
        height=320,
    )

with dir_:
    pais = st.selectbox("Ver a evolução de:", dados["pais_nome"])
    serie = consultas.evolucao_do_pais(pais, sexo)
    st.subheader(f"{pais}, ano a ano")
    st.line_chart(
        serie,
        x="ano",
        y="expectativa_vida",
        color="#D96F2C",
        height=250,
    )

st.divider()

# ---------------------------------------------------------- tabela
st.subheader(f"Detalhe de {regiao} em {ano}")
st.dataframe(
    dados,
    hide_index=True,
    width="stretch",
    column_config={
        "pais_nome": st.column_config.TextColumn("País"),
        "expectativa_vida": st.column_config.NumberColumn(
            "Expectativa (anos)", format="%.1f"
        ),
        "variacao_pct": st.column_config.NumberColumn(
            "Variação",
            format="%+.2f%%",
            help="Em relação ao ano anterior do mesmo país e sexo.",
        ),
        "gasto_saude_pct_pib": st.column_config.NumberColumn(
            "Gasto saúde (% PIB)", format="%.1f%%"
        ),
        "pib_per_capita_usd": st.column_config.NumberColumn(
            "PIB per capita (US$)", format="%.0f"
        ),
        "escolaridade_anos": st.column_config.NumberColumn(
            "Escolaridade (anos)", format="%.1f"
        ),
        "dif_mediana_regiao": st.column_config.NumberColumn(
            "Dif. da mediana (anos)",
            format="%+.1f",
            help=(
                "Quanto o país está acima ou abaixo da mediana da sua "
                "região do Banco Mundial, no mesmo ano e sexo."
            ),
        ),
    },
)

# Todo numero apresentado a alguem deveria dizer de onde veio.
st.caption(
    f"Fonte: OMS (expectativa de vida e gasto em saúde) e Banco Mundial "
    f"(PIB, escolaridade e cadastro de países). "
    f"{len(dados)} registros nesta seleção."
)
