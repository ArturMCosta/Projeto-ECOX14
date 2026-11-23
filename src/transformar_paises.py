import json
import logging
from datetime import datetime

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

PADRAO = "paises_*.json"

COLUNAS = ["id", "name", "capitalCity", "longitude", "latitude",
           "region.value", "incomeLevel.value"]

ORDEM_RENDA = ["Low income", "Lower middle income",
               "Upper middle income", "High income"]


def carregar():
    arquivos = sorted(config.BRONZE_BANCO.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {config.BRONZE_BANCO}")
    caminho = arquivos[-1]
    with caminho.open(encoding="utf-8") as f:
        df = pd.json_normalize(json.load(f))
    log.info("lido: %s, %s registros", caminho.name, len(df))
    log.debug("forma: %s", df.shape)
    return df, caminho


def separar_agregados(df):
    e_pais = df["region.value"] != "Aggregates"
    log.info("paises: %s | agregados: %s",
             int(e_pais.sum()), int((~e_pais).sum()))
    return df[e_pais].copy()


def conferir_chave(df, chave="id"):
    repetidas = int(df[chave].duplicated().sum())
    if repetidas:
        log.warning("chaves repetidas: %s", repetidas)
        log.debug("%s", df[df[chave].duplicated(keep=False)])
    else:
        log.debug("chaves repetidas: 0")
    return df.drop_duplicates(subset=chave)


def salvar(df):
    config.PRATA.mkdir(parents=True, exist_ok=True)
    destino = config.PRATA / "paises.parquet"
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
    df = limpeza.tirar_espacos(df)
    df = separar_agregados(df)
    df = conferir_chave(df)
    df = limpeza.tipar_numero(df, ["longitude", "latitude"])
    df = limpeza.tipar_categoria(df, "incomeLevel.value", ORDEM_RENDA)
    df = df[COLUNAS].rename(columns={
        "id": "pais_id",
        "name": "pais_nome",
        "capitalCity": "capital",
        "region.value": "regiao",
        "incomeLevel.value": "nivel_renda",
    })
    destino = salvar(df)
    registrar(origem, destino, antes, len(df), [
        "espacos removidos de nome de coluna e de texto",
        "agregados regionais separados",
        "longitude e latitude convertidas para numero",
        "nivel de renda tipado como categoria com ordem",
    ])


if __name__ == "__main__":
    config.configurar_log()
    main()
