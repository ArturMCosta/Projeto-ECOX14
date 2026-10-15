import json
import time
from datetime import date, datetime
from pathlib import Path

import requests

URL = "https://api.worldbank.org/v2"
BRONZE = Path("dados/bronze/banco_mundial")

ANO_INICIAL = 2000
ANO_FINAL = 2018
POR_PAGINA = 300
PAUSA = 0.5

SERIES = {
    "NY.GDP.PCAP.CD": "pib_per_capita",
    "SE.SCH.LIFE": "escolaridade",
}


def montar_url_indicador(codigo, pagina):
    return (f"{URL}/country/all/indicator/{codigo}"
            f"?format=json&date={ANO_INICIAL}:{ANO_FINAL}"
            f"&per_page={POR_PAGINA}&page={pagina}")


def montar_url_paises():
    return f"{URL}/country?format=json&per_page={POR_PAGINA}"


def pedir(url, tentativas=3):
    for tentativa in range(tentativas):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException:
            print(f"conexao caiu ({tentativa + 1}/{tentativas}), tentando de novo")
            time.sleep(3)
    raise SystemExit("fonte inacessivel depois de varias tentativas")


def buscar_paises():
    """Metadados: nome, regiao, nivel de renda e coordenadas.

    E aqui que a serie da WHO ganha o nome do pais. A WHO devolve so o
    codigo ISO3, como 'BRA'. Quem traduz e esta tabela.
    """
    corpo = pedir(montar_url_paises()).json()
    print("a fonte informa:", corpo[0]["total"])
    return corpo


def conferir(meta, recebidos):
    if recebidos != meta["total"]:
        raise ValueError(
            f"recebidos {recebidos}, a fonte informou {meta['total']}")
    print("conferido:", recebidos)


def percorrer(codigo):
    """Toda API pagina. Sem percorrer, voce leva a primeira pagina e
    acha que tem a serie inteira. Nada avisa."""
    registros = []
    pagina = 1
    while True:
        corpo = pedir(montar_url_indicador(codigo, pagina)).json()
        meta = corpo[0]
        registros = registros + (corpo[1] or [])
        print(f"pagina {pagina} de {meta['pages']} -> {len(registros)}")
        if pagina >= meta["pages"]:
            break
        pagina = pagina + 1
        time.sleep(PAUSA)

    conferir(meta, len(registros))
    return registros, meta


def salvar(registros, prefixo):
    """Grava um arquivo por pacote de dados, no formato que veio do servidor.

    A API responde um array com os metadados na posicao 0 e os registros na
    posicao 1. Guarda-se so a lista de registros: o que o arquivo contem e o
    dado, e os metadados ficam na proveniencia, que e onde pertencem.
    """
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"{prefixo}_{hoje}.json"
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def registrar(prefixo, destino, linhas, extra=None):
    """Acrescenta uma linha. Nunca sobrescreve a extracao anterior."""
    info = {
        "fonte": URL,
        "pacote": prefixo,
        "arquivo_bronze": destino.name,
        "formato": "JSON",
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
    registrar("paises", destino, len(paises[1]),
              extra={"lastupdated": paises[0].get("lastupdated")})
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