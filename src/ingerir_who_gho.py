import json
import logging
from datetime import date, datetime

import requests

import config

log = logging.getLogger(__name__)


def montar_url(codigo, skip, contar=False):
    filtro = (f"TimeDim ge {config.ANO_INICIAL} "
              f"and TimeDim le {config.ANO_FINAL}")
    url = (f"{config.URL_WHO}/{codigo}?$filter={filtro}"
           f"&$top={config.POR_PAGINA_WHO}&$skip={skip}"
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
    log.info("a fonte informa: %s registros", esperado)

    registros = []
    skip = 0
    while skip < esperado:
        pagina = baixar_pagina(codigo, skip)
        if not pagina:
            break
        registros = registros + pagina
        skip = skip + len(pagina)

    log.info("recebidos: %s", len(registros))
    if len(registros) != esperado:
        log.error("a serie veio incompleta: %s de %s", len(registros), esperado)
        raise ValueError("a serie veio incompleta")
    return registros


def salvar(registros, prefixo):
    """Grava um arquivo por indicador, no formato que veio do servidor.

    Converter formato e transformacao, e isso pertence a camada seguinte.
    """
    config.BRONZE_WHO.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = config.BRONZE_WHO / f"{prefixo}_{hoje}.json"
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def registrar(codigo, destino, registros):
    """Acrescenta uma linha. Nunca sobrescreve a extracao anterior."""
    info = {
        "fonte": config.URL_WHO,
        "indicador": codigo,
        "arquivo_bronze": destino.name,
        "formato": "JSON",
        "registros": len(registros),
        "periodo": f"{config.ANO_INICIAL}-{config.ANO_FINAL}",
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
    }
    caminho = config.BRONZE_WHO / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    for codigo, prefixo in config.INDICADORES_WHO.items():
        log.info("who/gho: %s (%s)", prefixo, codigo)
        registros = percorrer(codigo)
        destino = salvar(registros, prefixo)
        registrar(codigo, destino, registros)
        log.info("gravado em: %s", destino.name)


if __name__ == "__main__":
    config.configurar_log()
    main()
