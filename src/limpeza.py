from pathlib import Path

import pandas as pd


def tirar_espacos(df):
    df.columns = df.columns.str.strip()
    for coluna in df.select_dtypes(include="object"):
        df[coluna] = df[coluna].str.strip()
    return df


def chave_texto(serie):
    s = serie.str.strip().str.lower()
    s = s.str.normalize("NFKD")
    s = s.str.encode("ascii", errors="ignore")
    return s.str.decode("utf-8")


def aplicar_mapa(serie, mapa):
    return serie.replace(mapa)


def tipar_categoria(df, coluna, ordem):
    antes = df[coluna].isna().sum()
    df[coluna] = pd.Categorical(df[coluna], categories=ordem, ordered=True)
    print(f"{coluna} fora da escala:", df[coluna].isna().sum() - antes)
    return df


def tipar_numero(df, colunas):
    for coluna in colunas:
        antes = df[coluna].isna().sum()
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        print(f"{coluna}: {df[coluna].isna().sum() - antes} viraram ausentes")
    return df


def remover_vazias(df, colunas):
    """Remove a linha que nao tem valor em nenhuma das colunas.

    Uma linha sem nenhum dos seus dados nao responde a pergunta, e nao
    existe valor defensavel para preencher: o territorio nao tem economia
    registrada na fonte.
    """
    vazia = df[colunas].isna().all(axis=1)
    print("linhas sem nenhum dos dados:", vazia.sum())
    print("paises envolvidos:", df.loc[vazia, "pais_nome"].nunique())
    return df[~vazia].copy()


def variacao_anual(df, chave, tempo, valor):
    """Variacao em relacao ao registro anterior da mesma chave.

    A chave precisa ser uma lista quando a tabela tem mais de uma dimensao:
    com uma linha por pais, ano e sexo, agrupar so por pais comara um ano
    com outro sexo do mesmo ano.
    """
    df = df.sort_values(chave + [tempo])
    df["variacao_pct"] = df.groupby(chave, sort=False)[valor].pct_change() * 100
    return df


def faixa_por_quartil(df, coluna, rotulos):
    df[coluna + "_faixa"] = pd.qcut(df[coluna], q=4, labels=rotulos)
    return df


def marcar_extremos_iqr(df, coluna):
    q1 = df[coluna].quantile(0.25)
    q3 = df[coluna].quantile(0.75)
    iqr = q3 - q1
    fora = (df[coluna] < q1 - 1.5 * iqr) | (df[coluna] > q3 + 1.5 * iqr)
    df[coluna + "_extremo"] = fora
    print(f"{coluna} extremos:", fora.sum())
    return df


def cruzar_com_paises(df, prata, colunas):
    paises = pd.read_parquet(Path(prata) / "paises.parquet")
    antes = len(df)
    df = df.merge(paises[["pais_id"] + colunas], on="pais_id", how="left")
    print("sem nome de pais:", df["pais_nome"].isna().sum())
    print("linhas antes:", antes, "depois:", len(df))
    return df