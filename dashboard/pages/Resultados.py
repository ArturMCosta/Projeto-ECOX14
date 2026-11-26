

import sys
from pathlib import Path

import streamlit as st



RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

import analise  


def br(valor, casas=0):
    
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
    "Mínimos quadrados sobre a view da Ouro, com `sexo = 'total'`. Usei R² "
    "porque a pergunta é quanto cada fator explica: ele mede a parte da "
    "variação da expectativa que o modelo acompanha. O PIB entra em log "
    "porque a renda vai de ~US$ 100 a ~US$ 100 mil; cada marcação do eixo "
    "multiplica por 10. O erro-padrão é agrupado por país e, no painel, há "
    "efeito fixo de ano. O modelo é leitura, não etapa do pipeline."
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


c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Renda · 182 países",
    br(corte.loc["Renda", "r2"], 3),
    help="Amostra máxima: quem tem expectativa de vida e PIB em 2018.",
)
c2.metric(
    "Renda · 86 países",
    br(corte.loc["Renda, so os casos completos", "r2"], 3),
    help="Mesmos países usados nos modelos com escolaridade e gasto.",
)
c3.metric(
    "+ escolaridade",
    br(corte.loc["Renda + escolaridade", "r2"], 3),
    delta=f"+{br(r['ganho_escolaridade']['corte'] * 100, 1)} p.p.",
    help="Ganho sobre a renda nos mesmos 86 países.",
)
c4.metric(
    "+ gasto",
    br(corte.loc["Renda + escolaridade + gasto (% do PIB)", "r2"], 3),
    help="Praticamente não muda o R².",
)

st.caption(
    f"2018: {br(a['paises_2018'])} países com expectativa e PIB; "
    f"{br(a['escolaridade_2018'])} têm escolaridade e "
    f"{br(a['completos_2018'])} têm tudo. "
    f"Painel: {br(a['pares_painel'])} pares país-ano de "
    f"{br(a['paises_painel'])} países; {br(a['serie_completa'])} têm os 19 anos."
)

st.divider()


st.subheader("Entre países, em 2018")
st.caption(
    "A renda sozinha usa até 182 países; os modelos com escolaridade e gasto "
    "ficam com 86, que são os países com todos os dados."
)
tabela_r2(r["corte"], com_paises=True)

st.subheader("No painel, 2000 a 2018")
st.caption("Efeito fixo de ano: compara países no mesmo ano.")
tabela_r2(r["painel"])

st.subheader("Dentro do país")
st.caption(
    "Efeito fixo de país e de ano: em vez de comparar países diferentes, "
    "compara o mesmo país em anos diferentes."
)
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
    "- **Quem vive mais, em média, são os países com maior renda.** Com todos "
    "os países de 2018, a renda sozinha acompanha 69,0% da diferença; nos 86 "
    "países com todos os dados, 76,7%. Com os controles, dez vezes mais renda "
    "vale 6,2 anos entre países e 2,3 dentro do país.\n"
    "- **A escolaridade ajuda um pouco.** Nos mesmos 86 países, o R² sai de "
    "0,767 para 0,784 em 2018. Um ano a mais de escolaridade aparece com 0,4 "
    "a 0,85 ano a mais de expectativa.\n"
    "- **O gasto em saúde não muda esse resultado.** Sozinho ele até se "
    "parece com a expectativa, mas quando renda e escolaridade entram o "
    "coeficiente vai a zero. Gasto per capita dá o mesmo e é quase colinear "
    "com o PIB (r ≈ 0,9).\n"
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
