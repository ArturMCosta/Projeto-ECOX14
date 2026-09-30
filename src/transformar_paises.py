import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/banco_mundial")
PRATA = Path("dados/prata")
PADRAO = "paises_*.csv"

COLUNAS = ["id", "name", "capitalCity", "longitude", "latitude",
           "region.value", "incomeLevel.value"]

ORDEM_RENDA = ["Low income", "Lower middle income",
               "Upper middle income", "High income"]


def carregar():
    arquivos = sorted(BRONZE.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {BRONZE}")
    caminho = arquivos[-1]
    df = pd.read_csv(caminho)
    print("lido:", caminho.name, df.shape)
    return df, caminho


def separar_agregados(df):
    e_pais = df["region.value"] != "Aggregates"
    print("paises   :", e_pais.sum())
    print("agregados:", (~e_pais).sum())
    return df[e_pais].copy()


def conferir_chave(df, chave="id"):
    repetidas = df[chave].duplicated().sum()
    print("chaves repetidas:", repetidas)
    if repetidas:
        print(df[df[chave].duplicated(keep=False)])
    return df.drop_duplicates(subset=chave)


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "paises.parquet"
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
    main()