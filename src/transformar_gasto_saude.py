import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/who_gho")
PRATA = Path("dados/prata")
PADRAO = "indicadores_*.csv"
INDICADOR = "GHED_CHEGDP_SHA2011"
INDICADOR_PER_CAPITA = "GHED_CHE_pc_US_SHA2011"

COLUNAS = ["pais_id", "pais_nome", "regiao", "ano",
           "gasto_saude_pct_pib", "gasto_saude_per_capita_usd"]


def carregar():
    arquivos = sorted(BRONZE.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {BRONZE}")
    caminho = arquivos[-1]
    df = pd.read_csv(caminho)
    df = df[df["IndicatorCode"] == INDICADOR].copy()
    print("lido:", caminho.name, df.shape)
    return df, caminho


def tipar_ano(df):
    df["ano"] = pd.to_numeric(df["TimeDim"], errors="coerce").astype("Int64")
    return df


def separar_agregados(df):
    e_pais = df["SpatialDimType"] == "COUNTRY"
    print("paises   :", e_pais.sum())
    print("agregados:", (~e_pais).sum())
    return df[e_pais].copy()


def conferir_chave(df, chave=["pais_id", "ano"]):
    repetidas = df.duplicated(subset=chave).sum()
    print("chaves repetidas:", repetidas)
    return df.drop_duplicates(subset=chave)


def juntar_per_capita(df):
    """Os dois indicadores vem do mesmo arquivo da mesma fonte."""
    outro = pd.read_csv(sorted(BRONZE.glob(PADRAO))[-1])
    outro = outro[outro["IndicatorCode"] == INDICADOR_PER_CAPITA].copy()
    outro = outro.rename(columns={
        "SpatialDim": "pais_id",
        "TimeDim": "ano",
        "NumericValue": "gasto_saude_per_capita_usd",
    })
    df = df.merge(outro[["pais_id", "ano", "gasto_saude_per_capita_usd"]],
                  on=["pais_id", "ano"], how="left")
    print("sem per capita:", df["gasto_saude_per_capita_usd"].isna().sum())
    return df


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "gasto_saude.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def registrar(origem, destino, antes, depois, decisoes):
    info = {
        "origem": origem.name,
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": depois,
        "decisoes": decisoes,
        "transformado_em": datetime.now().isoformat(timespec="seconds"),
    }
    PRATA.mkdir(parents=True, exist_ok=True)
    with (PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    df, origem = carregar()
    antes = len(df)
    df = tipar_ano(df)
    df = limpeza.tipar_numero(df, ["NumericValue"])
    df = df.rename(columns={
        "SpatialDim": "pais_id",
        "NumericValue": "gasto_saude_pct_pib",
    })
    df = separar_agregados(df)
    df = conferir_chave(df)
    df = juntar_per_capita(df)
    df = limpeza.cruzar_com_paises(df, PRATA, ["pais_nome", "regiao"])
    df = limpeza.marcar_extremos_iqr(df, "gasto_saude_pct_pib")

    destino = salvar(df[COLUNAS])
    registrar(origem, destino, antes, len(df), [
        "ano convertido para inteiro, nao para data",
        "valor lido de NumericValue, nao de Value que vem como texto",
        "agregados separados pela declaracao SpatialDimType",
        "gasto por habitante juntado do mesmo arquivo da bronze",
        "extremos de gasto marcados, nao removidos",
    ])


if __name__ == "__main__":
    main()