import logging

import pandas as pd

import config
import juncao

log = logging.getLogger(__name__)


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
    fora = df[coluna].isna().sum() - antes
    if fora:
        log.warning("%s: %s valores fora da escala", coluna, fora)
    else:
        log.debug("%s: nenhum valor fora da escala", coluna)
    return df


def tipar_numero(df, colunas):
    for coluna in colunas:
        antes = df[coluna].isna().sum()
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        viraram = df[coluna].isna().sum() - antes
        if viraram:
            log.warning("%s: %s viraram ausentes", coluna, viraram)
        else:
            log.debug("%s: nenhum virou ausente", coluna)
    return df


def remover_vazias(df, colunas):
    
    vazia = df[colunas].isna().all(axis=1)
    log.info("linhas sem nenhum dos dados: %s (%s paises)",
             int(vazia.sum()), df.loc[vazia, "pais_nome"].nunique())
    return df[~vazia].copy()


def variacao_anual(df, chave, tempo, valor):
    
    df = df.sort_values(chave + [tempo])
    df["variacao_pct"] = (df.groupby(chave, sort=False, observed=True)[valor]
                          .pct_change() * 100)
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
    log.info("%s: %s extremos marcados, nenhum removido",
             coluna, int(fora.sum()))
    return df


def cruzar_com_paises(df, colunas):
    
    paises = pd.read_parquet(config.PRATA / "paises.parquet")

    juncao.conferir_chaves(df, paises, "pais_id", "pais_id")
    resultado = juncao.juntar(
        df, paises[["pais_id"] + colunas], "pais_id", "pais_id",
        relacao="many_to_one",
    )
    sem_par = juncao.validar(df, resultado, "pais_nome")
    return resultado
