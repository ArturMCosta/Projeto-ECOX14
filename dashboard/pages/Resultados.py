"""
Pagina de analise da pergunta norteadora.

COMO RODAR
==========
Esta pagina faz parte do app multipagina do Streamlit. Rode o app inteiro:

    streamlit run dashboard/painel.py

A navegacao fica na barra lateral, com a pagina principal ("painel") e esta
("Resultados"). Nao rode este arquivo sozinho: o caminho relativo dos
modulos e as configuracoes do app sao as do ponto de entrada principal.
"""

import sys
from pathlib import Path

import streamlit as st

# A pagina esta em dashboard/pages/, entao a raiz do projeto e dois niveis
# acima. Os modulos de leitura e analise ficam fora da pasta do painel.
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

import analise  # noqa: E402


def br(valor, casas=0):
    """Numero no padrao brasileiro, com virgula decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


MODELOS = {
    "Renda": "Renda",
    "Renda, so os casos completos": "Renda, só os casos completos",
    "Renda + escolaridade": "Renda + escolaridade",
    "Renda + escolaridade + gasto (% do PIB)": "Renda + escolaridade + gasto (% do PIB)",
}

VARIAVEIS = {
    "PIB per capita, por 10x": "PIB per capita, por 10×",
    "Escolaridade, por ano": "Escolaridade, por ano",
    "Gasto saude, por ponto do PIB": "Gasto saúde, por ponto do PIB",
}

COLUNAS_COEFICIENTES = {
    "variavel": "Variável",
    "corte": "Entre países (2018)",
    "painel": "Painel com ano",
    "dentro": "Dentro do país",
}


def tabela_r2(tabela, com_paises=False):
    """Mostra uma tabela de modelos e R2, com rotulos em portugues."""
    exibir = tabela.copy()
    exibir["modelo"] = exibir["modelo"].replace(MODELOS)
    exibir["r2"] = exibir["r2"].map(lambda v: br(v, 3))
    if com_paises:
        exibir["paises"] = exibir["paises"].map(lambda v: br(v, 0))
        exibir = exibir.rename(columns={"modelo": "Modelo", "paises": "Países", "r2": "R²"})
        exibir = exibir[["Modelo", "Países", "R²"]]
    else:
        exibir = exibir.rename(columns={"modelo": "Modelo", "r2": "R²"})
        exibir = exibir[["Modelo", "R²"]]
    st.dataframe(exibir, hide_index=True, width="stretch")


st.set_page_config(
    page_title="Quanto cada fator explica",
    page_icon="📐",
    layout="wide",
)

st.title("Quanto cada fator explica")
st.caption(
    "A segunda metade da pergunta norteadora: além de descrever o gradiente, "
    "medir quanto renda, escolaridade e gasto em saúde acompanham a "
    "expectativa de vida."
)

st.markdown(
    "Mínimos quadrados sobre a view da Ouro, com `sexo = 'total'`, PIB per "
    "capita em escala log (cada 10× de renda é uma unidade), erro-padrão "
    "agrupado por país e, no painel, efeito fixo de ano. O modelo é leitura, "
    "não etapa do pipeline."
)

if not analise.banco_existe():
    st.error(
        "Banco não encontrado.\n\n"
        "Rode o pipeline antes:  python src/pipeline.py"
    )
    st.stop()


@st.cache_data(show_spinner="Ajustando os modelos...")
def carregar():
    return analise.analisar()


try:
    r = carregar()
except Exception as erro:
    st.error(
        f"Não foi possível ler o banco: {erro}\n\n"
        "Feche a interface do DuckDB e tente de novo."
    )
    st.stop()

corte = r["corte"].set_index("modelo")
a = r["amostra"]

# -------------------------------------------------------- cartoes
c1, c2, c3 = st.columns(3)
c1.metric(
    "Renda sozinha, 2018",
    br(corte.loc["Renda", "r2"], 3),
    help=f"{br(a['paises_2018'])} países na amostra.",
)
c2.metric(
    "Com escolaridade",
    br(corte.loc["Renda + escolaridade", "r2"], 3),
    delta=f"+{br(r['ganho_escolaridade']['corte'] * 100, 1)} p.p.",
    help="Comparado ao mesmo modelo sem escolaridade, nos 86 países com os três dados.",
)
c3.metric(
    "Gasto em saúde",
    "sem efeito",
    help="Coeficiente não significativo a 5%, com renda e escolaridade no modelo.",
)

st.caption(
    f"2018: {br(a['paises_2018'])} países; {br(a['escolaridade_2018'])} com "
    f"escolaridade; {br(a['completos_2018'])} com os três dados. "
    f"Painel: {br(a['pares_painel'])} pares país-ano de "
    f"{br(a['paises_painel'])} países; {br(a['serie_completa'])} têm os 19 anos."
)

st.divider()

# -------------------------------------------------------- tabelas
st.subheader("Entre países, em 2018")
st.caption(
    "Amostra máxima de 182 países na renda; os casos completos caem para 86 "
    "porque a escolaridade é o gargalo."
)
tabela_r2(r["corte"], com_paises=True)

st.subheader("No painel, 2000 a 2018")
st.caption("Efeito fixo de ano: compara países no mesmo ano.")
tabela_r2(r["painel"])

st.subheader("Dentro do país")
st.caption("Efeito fixo de país e de ano: usa só a variação de cada país contra ele mesmo.")
tabela_r2(r["dentro"])

st.subheader("Coeficientes do modelo completo")
coef = r["coeficientes"].copy()
coef["variavel"] = coef["variavel"].replace(VARIAVEIS)
coef = coef.rename(columns=COLUNAS_COEFICIENTES)
coef = coef[["Variável", "Entre países (2018)", "Painel com ano", "Dentro do país"]]
st.dataframe(coef, hide_index=True, width="stretch")
st.caption("n.s. = não significativo a 5%; erro-padrão agrupado por país.")

st.divider()

st.subheader("O que os números dizem")
st.markdown(
    "- **A renda explica a maior parte.** Sozinha, 69,0% da diferença entre "
    "países em 2018, 70,4% no painel e 60,8% da variação dentro do país ao "
    "longo do tempo. Com os controles, dez vezes mais renda vale 6,2 anos "
    "entre países e 2,3 dentro do país.\n"
    "- **A escolaridade acrescenta pouco, mas acrescenta.** Leva o R² de "
    "0,767 para 0,784 em 2018, de 0,704 para 0,736 no painel e de 0,608 "
    "para 0,629 dentro do país. O coeficiente fica entre 0,4 e 0,85 ano por "
    "ano de escolaridade.\n"
    "- **O gasto em saúde não acrescenta nada depois dos outros dois.** A "
    "correlação bruta com a expectativa de vida é 0,40, mas o coeficiente "
    "vai a zero quando renda e escolaridade entram. Gasto per capita dá o "
    "mesmo resultado e é quase colinear com o PIB (r ≈ 0,9): este dado não "
    "separa os dois.\n"
    "- **Entre e dentro são respostas diferentes.** Um país dez vezes mais "
    "rico tem 6,2 anos a mais que outro; um país que ficou dez vezes mais "
    "rico no período ganha 2,3. O resto da vantagem dos ricos não é renda: "
    "é o que o efeito fixo de país captura — história, sistema de saúde, "
    "ambiente — e este dado não abre essa caixa."
)

st.subheader("O que o dado não permite dizer")
st.markdown(
    "- **Associação, não causalidade.** Renda, escolaridade e gasto andam "
    "juntos; o modelo mede o quanto a variação de um acompanha a do outro.\n"
    "- **Médias de país, não pessoas.** Nada aqui diz sobre um indivíduo.\n"
    "- **O painel é desbalanceado.** São 1.922 dos 3.515 pares possíveis; só "
    "33 dos 169 países têm os 19 anos. Quem entra é quem tem escolaridade "
    "medida, e isso não é aleatório.\n"
    "- **A escolaridade acaba em 2019 e cai no fim do recorte:** 107 países "
    "em 2002, 92 em 2018 na prata e 87 entre os 185 com expectativa de vida."
)

st.caption(
    "Fonte: OMS e Banco Mundial, camada Ouro do projeto. O mesmo resultado "
    "sai de `python src/analise.py`."
)
