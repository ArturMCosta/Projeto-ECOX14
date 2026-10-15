import json
from datetime import date, datetime
from pathlib import Path

import requests

URL = "https://ghoapi.azureedge.net/api"
BRONZE = Path("dados/bronze/who_gho")

ANO_INICIAL = 2000
ANO_FINAL = 2018
POR_PAGINA = 1000

INDICADORES = {
    "WHOSIS_000001": "expectativa_vida",
    "GHED_CHEGDP_SHA2011": "gasto_saude_pct_pib",
    "GHED_CHE_pc_US_SHA2011": "gasto_saude_per_capita",
}


def montar_url(codigo, skip, contar=False):
    filtro = f"TimeDim ge {ANO_INICIAL} and TimeDim le {ANO_FINAL}"
    url = (f"{URL}/{codigo}?$filter={filtro}"
           f"&$top={POR_PAGINA}&$skip={skip}"
           f"&$orderby=SpatialDim,TimeDim,Dim1")
    if contar:
        url = url + "&$count=true"
    return url


def conferir_total(codigo):
    r = requests.get(montar_url(codigo, 0, contar=True), timeout=60)
    r.raise_for_status()
    return r.json()["@odata.count"]


def baixar_pagina(codigo, skip):
    r = requests.get(montar_url(codigo, skip), timeout=60)
    r.raise_for_status()
    return r.json()["value"]


def percorrer(codigo):
    """Baixa todas as paginas e so segue se veio tudo."""
    esperado = conferir_total(codigo)
    print("a fonte informa:", esperado)

    registros = []
    skip = 0
    while skip < esperado:
        pagina = baixar_pagina(codigo, skip)
        if not pagina:
            break
        registros = registros + pagina
        skip = skip + len(pagina)

    print("recebidos:", len(registros))
    if len(registros) != esperado:
        raise ValueError("a serie veio incompleta")
    return registros


def salvar(registros, prefixo):
    """Grava um arquivo por indicador, no formato que veio do servidor.

    Converter formato e transformacao, e isso pertence a camada seguinte.
    """
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"{prefixo}_{hoje}.json"
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def registrar(codigo, destino, registros):
    """Acrescenta uma linha. Nunca sobrescreve a extracao anterior."""
    info = {
        "fonte": URL,
        "indicador": codigo,
        "arquivo_bronze": destino.name,
        "formato": "JSON",
        "registros": len(registros),
        "periodo": f"{ANO_INICIAL}-{ANO_FINAL}",
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
    }
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    for codigo, prefixo in INDICADORES.items():
        print("\n", prefixo, codigo)
        registros = percorrer(codigo)
        destino = salvar(registros, prefixo)
        registrar(codigo, destino, registros)
        print("gravado em:", destino)


if __name__ == "__main__":
    main()