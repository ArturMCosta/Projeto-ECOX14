import json
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

URL = "https://api.worldbank.org/v2"
BRONZE = Path("dados/bronze/banco_mundial")

ANO_INICIAL = 2000
ANO_FINAL = 2018
POR_PAGINA = 300

SERIES = {
    "NY.GDP.PCAP.CD": "pib_per_capita",
    "SE.SCH.LIFE": "escolaridade",
}


def pedir(url):
    for tentativa in range(3):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException:
            print("conexao caiu, tentando de novo")
            time.sleep(3)
    raise SystemExit("fonte inacessivel")


def buscar_paises():
    return pedir(f"{URL}/country?format=json&per_page={POR_PAGINA}").json()


def buscar_indicador(codigo, pagina):
    url = (f"{URL}/country/all/indicator/{codigo}"
           f"?format=json&date={ANO_INICIAL}:{ANO_FINAL}"
           f"&per_page={POR_PAGINA}&page={pagina}")
    return pedir(url).json()


def conferir(dados):
    meta = dados[0]
    print("registros:", meta["total"])
    print("paginas  :", meta["pages"])
    if meta["pages"] > 1:
        print("ATENCAO: a resposta vem paginada")
    return meta


def percorrer(codigo):
    meta = conferir(buscar_indicador(codigo, 1))
    registros = []
    for pagina in range(1, meta["pages"] + 1):
        registros = registros + (buscar_indicador(codigo, pagina)[1] or [])
        time.sleep(0.5)
        print(f"pagina {pagina} de {meta['pages']} -> {len(registros)}")
    if len(registros) != meta["total"]:
        raise ValueError("a serie veio incompleta")
    return registros, meta


def salvar(registros, prefixo):
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"{prefixo}_{hoje}.csv"
    pd.json_normalize(registros).to_csv(destino, index=False)
    return destino


def registrar(prefixo, destino, linhas, extra=None):
    info = {
        "fonte": URL,
        "serie": prefixo,
        "arquivo_bronze": destino.name,
        "registros": linhas,
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        info.update(extra)
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    paises = buscar_paises()
    destino = salvar(paises[1], "paises")
    registrar("paises", destino, len(paises[1]))
    print("gravado em:", destino)

    for codigo, prefixo in SERIES.items():
        print("\n", prefixo, codigo)
        registros, meta = percorrer(codigo)
        destino = salvar(registros, prefixo)
        registrar(prefixo, destino, len(registros), extra={
            "indicador": codigo,
            "lastupdated": meta["lastupdated"],
            "periodo": f"{ANO_INICIAL}-{ANO_FINAL}",
        })
        print("gravado em:", destino)


if __name__ == "__main__":
    main()