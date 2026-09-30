import json
import sys
from pathlib import Path

import pandas as pd
from data_profiling import ProfileReport

BRONZE = Path("dados/bronze")
RELATORIOS = Path("relatorios")


def mais_recente(bronze, padrao):
    arquivos = sorted(bronze.glob(padrao))
    if not arquivos:
        raise FileNotFoundError(f"nada com o padrao {padrao} em {bronze}")
    return arquivos[-1]


def carregar(caminho):
    if caminho.suffix == ".json":
        with caminho.open(encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    return pd.read_csv(caminho)


def gerar(df, caminho):
    print("perfilando:", caminho.name, df.shape)
    print(df.columns.tolist())
    print(df.isna().sum())

    RELATORIOS.mkdir(exist_ok=True)
    saida = RELATORIOS / f"{caminho.stem}.html"
    ProfileReport(df, title=caminho.name).to_file(saida)
    print("relatorio em:", saida)
    return saida


def main():
    fonte = sys.argv[1] if len(sys.argv) > 1 else "banco_mundial"
    padrao = sys.argv[2] if len(sys.argv) > 2 else "paises_*.csv"
    caminho = mais_recente(BRONZE / fonte, padrao)
    gerar(carregar(caminho), caminho)


if __name__ == "__main__":
    main()