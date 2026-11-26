import json
import logging
from datetime import datetime

import pandas as pd

import config
import juncao
import limpeza

log = logging.getLogger(__name__)

PADRAO = "gasto_saude_pct_pib_*.json"
PADRAO_PER_CAPITA = "gasto_saude_per_capita_*.json"

COLUNAS = ["pais_id", "pais_nome", "regiao", "ano",
           "gasto_saude_pct_pib", "gasto_saude_per_capita_usd"]


def carregar():
    arquivos = sorted(config.BRONZE_WHO.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {config.BRONZE_WHO}")
    caminho = arquivos[-1]
    with caminho.open(encoding="utf-8") as f:
        df = pd.DataFrame(json.load(f))
    log.info("lido: %s, %s registros", caminho.name, len(df))
    return df, caminho


def tipar_ano(df):
    df["ano"] = pd.to_numeric(df["TimeDim"], errors="coerce").astype("Int64")
    return df


def separar_agregados(df):
    e_pais = df["SpatialDimType"] == "COUNTRY"
    log.info("paises: %s | agregados: %s",
             int(e_pais.sum()), int((~e_pais).sum()))
    return df[e_pais].copy()


def conferir_chave(df, chave=["pais_id", "ano"]):
    repetidas = int(df.duplicated(subset=chave).sum())
    if repetidas:
        log.warning("chaves repetidas: %s", repetidas)
    else:
        log.debug("chaves repetidas: 0")
    return df.drop_duplicates(subset=chave)


def juntar_per_capita(df):
    
    arquivos = sorted(config.BRONZE_WHO.glob(PADRAO_PER_CAPITA))
    if not arquivos:
        raise FileNotFoundError(f"nada com o padrao {PADRAO_PER_CAPITA}")
    with arquivos[-1].open(encoding="utf-8") as f:
        outro = pd.DataFrame(json.load(f))
    log.info("lido: %s, %s registros", arquivos[-1].name, len(outro))

    outro = outro.rename(columns={
        "SpatialDim": "pais_id",
        "TimeDim": "ano",
        "NumericValue": "gasto_saude_per_capita_usd",
    })
    outro = outro[outro["SpatialDimType"] == "COUNTRY"].copy()
    log.info("paises no pacote por habitante: %s", len(outro))

    juncao.conferir_chaves(df, outro, "pais_id", "pais_id")
    resultado = juncao.juntar(
        df,
        outro[["pais_id", "ano", "gasto_saude_per_capita_usd"]],
        ["pais_id", "ano"], ["pais_id", "ano"],
        relacao="one_to_one",
    )
    juncao.validar(df, resultado, "gasto_saude_per_capita_usd")
    return resultado


def salvar(df):
    config.PRATA.mkdir(parents=True, exist_ok=True)
    destino = config.PRATA / "gasto_saude.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s, %s", destino.name, df.shape)
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
    config.PRATA.mkdir(parents=True, exist_ok=True)
    with (config.PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
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
    df = limpeza.cruzar_com_paises(df, ["pais_nome", "regiao"])
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
    config.configurar_log()
    main()
