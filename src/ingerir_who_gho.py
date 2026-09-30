import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

URL = "https://ghoapi.azureedge.net/api"
BRONZE = Path("dados/bronze/who_gho")

ANO_INICIAL = 2000
ANO_FINAL = 2018
POR_PAGINA = 1000

INDICADORES = [
    "WHOSIS_000001",
    "GHED_CHEGDP_SHA2011",
    "GHED_CHE_pc_US_SHA2011",
]


def buscar(codigo, skip):
    filtro = f"TimeDim ge {ANO_INICIAL} and TimeDim le {ANO_FINAL}"
    r = requests.get(
        f"{URL}/{codigo}?$filter={filtro}"
        f"&$top={POR_PAGINA}&$skip={skip}&$count=true",
        timeout=60)
    r.raise_for_status()
    return r.json()


def conferir(dados):
    total = dados["@odata.count"]
    print("registros:", total)
    if total > POR_PAGINA:
        print("ATENCAO: a resposta vem paginada")
    return total


def percorrer(codigo):
    total = conferir(buscar(codigo, 0))
    registros = []
    skip = 0
    while skip < total:
        pagina = buscar(codigo, skip)["value"]
        if not pagina:
            break
        registros = registros + pagina
        skip = skip + len(pagina)
    print("recebidos:", len(registros))
    if len(registros) != total:
        raise ValueError("a serie veio incompleta")
    return registros


def juntar(series):
    """Os tres indicadores sao a mesma tabela da API.

    IndicatorCode ja diz qual e qual, entao nao ha nem o que separar:
    basta concatenar. As colunas vazias saem antes, porque uma delas so
    existe em parte dos indicadores.
    """
    partes = [pd.DataFrame(s).dropna(axis=1, how="all") for s in series]
    df = pd.concat(partes, ignore_index=True)
    print("total:", df.shape)
    print(df["IndicatorCode"].value_counts().to_string())
    return df


def salvar(df):
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"indicadores_{hoje}.csv"
    df.to_csv(destino, index=False)
    return destino


def registrar(destino, linhas, extra=None):
    info = {
        "fonte": URL,
        "indicadores": INDICADORES,
        "arquivo_bronze": destino.name,
        "registros": linhas,
        "periodo": f"{ANO_INICIAL}-{ANO_FINAL}",
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        info.update(extra)
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    series = []
    for codigo in INDICADORES:
        print("\n", codigo)
        series.append(percorrer(codigo))

    destino = salvar(juntar(series))
    registrar(destino, sum(len(s) for s in series))
    print("gravado em:", destino)


if __name__ == "__main__":
    main()