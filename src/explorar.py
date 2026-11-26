import json
import logging
import sys

import pandas as pd
from data_profiling import ProfileReport

import config

log = logging.getLogger(__name__)


def mais_recente(bronze, padrao):
    arquivos = sorted(bronze.glob(padrao))
    if not arquivos:
        raise FileNotFoundError(f"nada com o padrao {padrao} em {bronze}")
    return arquivos[-1]


def carregar(caminho):
    
    with caminho.open(encoding="utf-8") as f:
        return pd.json_normalize(json.load(f))


def gerar(df, caminho):
    log.info("perfilando: %s, %s", caminho.name, df.shape)
    log.debug("colunas: %s", df.columns.tolist())
    log.debug("ausentes por coluna:\n%s", df.isna().sum())

    config.RELATORIOS.mkdir(parents=True, exist_ok=True)
    saida = config.RELATORIOS / f"{caminho.stem}.html"
    ProfileReport(df, title=caminho.name).to_file(saida)
    log.info("relatorio em: %s", saida)
    return saida


def main():
    fonte = sys.argv[1] if len(sys.argv) > 1 else "banco_mundial"
    padrao = sys.argv[2] if len(sys.argv) > 2 else "paises_*.json"
    caminho = mais_recente(config.BRONZE / fonte, padrao)
    gerar(carregar(caminho), caminho)


if __name__ == "__main__":
    config.configurar_log()
    main()
