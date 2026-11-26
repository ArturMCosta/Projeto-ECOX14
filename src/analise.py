

import duckdb
import numpy as np
import pandas as pd

import config

BANCO = config.OURO / "projeto.duckdb"




SEXO = "total"
MODELOS = {
    "corte": [
        ("renda", "Renda"),
        ("renda_completo", "Renda, so os casos completos"),
        ("renda_escolaridade", "Renda + escolaridade"),
        ("completo", "Renda + escolaridade + gasto (% do PIB)"),
    ],
    "painel": [
        ("renda", "Renda"),
        ("renda_escolaridade", "Renda + escolaridade"),
        ("completo", "Renda + escolaridade + gasto (% do PIB)"),
    ],
    "dentro": [
        ("renda", "Renda"),
        ("renda_escolaridade", "Renda + escolaridade"),
        ("completo", "Renda + escolaridade + gasto (% do PIB)"),
    ],
}

COEFICIENTES = [
    ("log_pib", "PIB per capita, por 10x", 1),
    ("escolaridade_anos", "Escolaridade, por ano", 2),
    ("gasto_saude_pct_pib", "Gasto saude, por ponto do PIB", 2),
]

COMPLETAS = [
    "expectativa_vida",
    "pib_per_capita_usd",
    "escolaridade_anos",
    "gasto_saude_pct_pib",
]
XS_RENDA = ["log_pib"]
XS_RENDA_ESCOLARIDADE = ["log_pib", "escolaridade_anos"]
XS_COMPLETO = ["log_pib", "escolaridade_anos", "gasto_saude_pct_pib"]


def banco_existe():
    
    return BANCO.exists()


def ler_dados():
    
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        return con.execute(
            """
            select
                ano,
                pais_id,
                expectativa_vida,
                pib_per_capita_usd,
                escolaridade_anos,
                gasto_saude_pct_pib
            from ouro.vw_indicador_completo
            where sexo = ?
            order by pais_id, ano
            """,
            [SEXO],
        ).df()
    finally:
        con.close()


def anos_disponiveis():
    
    dados = ler_dados()
    return sorted(int(ano) for ano in dados["ano"].dropna().unique())


def _erro_agrupado(X, residuo, grupos, k):
    
    inv = np.linalg.inv(X.T @ X)
    carne = np.zeros((k, k))
    for indices in grupos.groupby(grupos).indices.values():
        soma = X[indices].T @ residuo[indices]
        carne += np.outer(soma, soma)

    g = grupos.nunique()
    n = len(residuo)
    cov = inv @ carne @ inv * (g / (g - 1)) * ((n - 1) / (n - k))
    return np.sqrt(np.diag(cov))


def _ajustar(base, xs, ano_fe=False, pais_fe=False):
    
    s = base.dropna(subset=["expectativa_vida", "pib_per_capita_usd"] + xs).copy()
    y = s["expectativa_vida"]
    colunas = s[xs].copy()

    if pais_fe:
        grupo = s.groupby("pais_id")
        y = y - grupo["expectativa_vida"].transform("mean")
        colunas = colunas - grupo[colunas.columns].transform("mean")

    if ano_fe:
        dummies = pd.get_dummies(s["ano"], drop_first=True, dtype=float)
        if pais_fe:
            
            auxiliar = dummies.copy()
            auxiliar["_pais"] = s["pais_id"].values
            dummies = (
                auxiliar[dummies.columns]
                - auxiliar.groupby("_pais")[dummies.columns].transform("mean")
            )
        colunas = pd.concat([colunas, dummies], axis=1)

    X = colunas.values
    if not pais_fe:
        X = np.column_stack([np.ones(len(s)), X])

    beta, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    residuo = y.values - X @ beta
    ssr = (residuo**2).sum()
    sst = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ssr / sst

    erro = _erro_agrupado(X, residuo, s["pais_id"], X.shape[1])
    inicio = 0 if pais_fe else 1
    coeficientes = {}
    for i, nome in enumerate(xs):
        b = beta[inicio + i]
        ep = erro[inicio + i]
        coeficientes[nome] = {"b": b, "ep": ep, "t": b / ep}

    return {
        "n": len(s),
        "paises": int(s["pais_id"].nunique()),
        "r2": float(r2),
        "coef": coeficientes,
    }


def _tabela(resultados, chaves):
    linhas = []
    for chave, rotulo in chaves:
        linhas.append(
            {
                "modelo": rotulo,
                "paises": resultados[chave]["n"],
                "r2": round(resultados[chave]["r2"], 3),
            }
        )
    return pd.DataFrame(linhas)


def _br(valor, casas=0):
    
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _coeficiente(valor, t, casas):
    
    if abs(valor) < 0.5 * 10**-casas:
        texto = "0," + "0" * casas
    else:
        texto = f"{valor:+.{casas}f}".replace(".", ",")
    if abs(t) < 1.96:
        texto += " (n.s.)"
    return texto


def analisar():
    
    dados = ler_dados()
    dados["log_pib"] = np.log10(dados["pib_per_capita_usd"])

    
    
    completas = COMPLETAS
    corte_2018 = dados[dados["ano"] == 2018]
    completo_2018 = corte_2018.dropna(subset=completas)
    painel = dados.dropna(subset=completas)

    xs_renda = XS_RENDA
    xs_renda_escolaridade = XS_RENDA_ESCOLARIDADE
    xs_completo = XS_COMPLETO

    corte = {
        "renda": _ajustar(corte_2018, xs_renda),
        "renda_completo": _ajustar(completo_2018, xs_renda),
        "renda_escolaridade": _ajustar(completo_2018, xs_renda_escolaridade),
        "completo": _ajustar(completo_2018, xs_completo),
    }
    no_painel = {
        "renda": _ajustar(painel, xs_renda, ano_fe=True),
        "renda_escolaridade": _ajustar(
            painel, xs_renda_escolaridade, ano_fe=True
        ),
        "completo": _ajustar(painel, xs_completo, ano_fe=True),
    }
    dentro = {
        "renda": _ajustar(painel, xs_renda, ano_fe=True, pais_fe=True),
        "renda_escolaridade": _ajustar(
            painel, xs_renda_escolaridade, ano_fe=True, pais_fe=True
        ),
        "completo": _ajustar(
            painel, xs_completo, ano_fe=True, pais_fe=True
        ),
    }

    linhas = []
    for chave, rotulo, casas in COEFICIENTES:
        linhas.append(
            {
                "variavel": rotulo,
                "corte": _coeficiente(
                    corte["completo"]["coef"][chave]["b"],
                    corte["completo"]["coef"][chave]["t"],
                    casas,
                ),
                "painel": _coeficiente(
                    no_painel["completo"]["coef"][chave]["b"],
                    no_painel["completo"]["coef"][chave]["t"],
                    casas,
                ),
                "dentro": _coeficiente(
                    dentro["completo"]["coef"][chave]["b"],
                    dentro["completo"]["coef"][chave]["t"],
                    casas,
                ),
            }
        )

    anos_por_pais = painel.groupby("pais_id")["ano"].nunique()
    return {
        "amostra": {
            "paises_2018": int(corte_2018["pais_id"].nunique()),
            "paises_2018_pib": int(corte["renda"]["n"]),
            "escolaridade_2018": int(
                corte_2018["escolaridade_anos"].notna().sum()
            ),
            "completos_2018": int(len(completo_2018)),
            "pares_painel": int(len(painel)),
            "paises_painel": int(painel["pais_id"].nunique()),
            "serie_completa": int((anos_por_pais == 19).sum()),
        },
        "corte": _tabela(corte, MODELOS["corte"]),
        "painel": _tabela(no_painel, MODELOS["painel"]),
        "dentro": _tabela(dentro, MODELOS["dentro"]),
        "coeficientes": pd.DataFrame(linhas),
        "ganho_escolaridade": {
            "corte": corte["renda_escolaridade"]["r2"]
            - corte["renda_completo"]["r2"],
            "painel": no_painel["renda_escolaridade"]["r2"]
            - no_painel["renda"]["r2"],
            "dentro": dentro["renda_escolaridade"]["r2"]
            - dentro["renda"]["r2"],
        },
    }


def analisar_corte(ano):
    
    ano = int(ano)
    dados = ler_dados()
    dados["log_pib"] = np.log10(dados["pib_per_capita_usd"])
    corte = dados[dados["ano"] == ano]
    completo = corte.dropna(subset=COMPLETAS)
    resultados = {
        "renda": _ajustar(corte, XS_RENDA),
        "renda_completo": _ajustar(completo, XS_RENDA),
        "renda_escolaridade": _ajustar(completo, XS_RENDA_ESCOLARIDADE),
        "completo": _ajustar(completo, XS_COMPLETO),
    }
    return {
        "ano": ano,
        "amostra": {
            "paises": int(corte["pais_id"].nunique()),
            "paises_pib": int(resultados["renda"]["n"]),
            "escolaridade": int(corte["escolaridade_anos"].notna().sum()),
            "completos": int(len(completo)),
        },
        "corte": _tabela(resultados, MODELOS["corte"]),
        "ganho_escolaridade": resultados["renda_escolaridade"]["r2"]
        - resultados["renda_completo"]["r2"],
    }


def imprimir(resultado):
    
    amostra = resultado["amostra"]
    print("A pergunta norteadora: renda, escolaridade e gasto")
    print("Fonte: ouro.vw_indicador_completo, sexo = 'total'")
    print("Leitura da Ouro; nao e etapa do pipeline.")
    print()
    print("== Amostra ==")
    print(
        f"  2018: {_br(amostra['paises_2018'])} paises, "
        f"{_br(amostra['paises_2018_pib'])} com expectativa e PIB, "
        f"{_br(amostra['escolaridade_2018'])} com escolaridade, "
        f"{_br(amostra['completos_2018'])} com todos os dados"
    )
    print(
        f"  Painel 2000-2018: {_br(amostra['pares_painel'])} pares pais-ano, "
        f"{_br(amostra['paises_painel'])} paises, "
        f"{_br(amostra['serie_completa'])} com os 19 anos"
    )
    print()

    print("== Entre paises, 2018 ==")
    for _, linha in resultado["corte"].iterrows():
        print(
            f"  {linha['modelo']:<44} {_br(linha['paises']):>5} "
            f"{_br(linha['r2'], 3):>6}"
        )
    print()

    print("== Painel 2000-2018, efeito de ano ==")
    for _, linha in resultado["painel"].iterrows():
        print(f"  {linha['modelo']:<44} {_br(linha['r2'], 3):>6}")
    print()

    print("== Dentro do pais, efeito de pais e de ano ==")
    for _, linha in resultado["dentro"].iterrows():
        print(f"  {linha['modelo']:<44} {_br(linha['r2'], 3):>6}")
    print()

    print("== Coeficientes do modelo completo ==")
    print(
        f"  {'Variavel':<32} {'Entre 2018':>11} {'Painel':>9} {'Dentro':>8}"
    )
    for _, linha in resultado["coeficientes"].iterrows():
        print(
            f"  {linha['variavel']:<32} {linha['corte']:>11} "
            f"{linha['painel']:>9} {linha['dentro']:>8}"
        )
    print("  n.s. = nao significativo a 5%; erro-padrao agrupado por pais.")
    print()

    ganho = resultado["ganho_escolaridade"]
    print("Ganho de R2 com a escolaridade:")
    print(
        f"  2018 {_br(ganho['corte'] * 100, 1)} p.p.; "
        f"painel {_br(ganho['painel'] * 100, 1)} p.p.; "
        f"dentro {_br(ganho['dentro'] * 100, 1)} p.p."
    )


if __name__ == "__main__":
    imprimir(analisar())
