import json
import logging
import time
from datetime import date, datetime

import requests

import config

log = logging.getLogger(__name__)


def montar_url_indicador(codigo, pagina):
    return (f"{config.URL_BANCO}/country/all/indicator/{codigo}"
            f"?format=json&date={config.ANO_INICIAL}:{config.ANO_FINAL}"
            f"&per_page={config.POR_PAGINA_BANCO}&page={pagina}")


def montar_url_paises():
    return (f"{config.URL_BANCO}/country"
            f"?format=json&per_page={config.POR_PAGINA_BANCO}")


def pedir(url, tentativas=3):
    for tentativa in range(tentativas):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException:
            log.warning("conexao caiu (%s/%s), tentando de novo",
                        tentativa + 1, tentativas)
            time.sleep(3)
    log.error("fonte inacessivel depois de %s tentativas", tentativas)
    raise SystemExit("fonte inacessivel depois de varias tentativas")


def buscar_paises():
    """Metadados: nome, regiao, nivel de renda e coordenadas.

    E aqui que a serie da WHO ganha o nome do pais. A WHO devolve so o
    codigo ISO3, como 'BRA'. Quem traduz e esta tabela.
    """
    corpo = pedir(montar_url_paises()).json()
    log.info("a fonte informa: %s registros", corpo[0]["total"])
    return corpo


def conferir(meta, recebidos):
    if recebidos != meta["total"]:
        log.error("recebidos %s, a fonte informou %s",
                  recebidos, meta["total"])
        raise ValueError(
            f"recebidos {recebidos}, a fonte informou {meta['total']}")
    log.info("conferido: %s", recebidos)


def percorrer(codigo):
    """Toda API pagina. Sem percorrer, voce leva a primeira pagina e
    acha que tem a serie inteira. Nada avisa."""
    registros = []
    pagina = 1
    meta = {}
    while True:
        corpo = pedir(montar_url_indicador(codigo, pagina)).json()
        meta = corpo[0]
        registros = registros + (corpo[1] or [])
        log.info("pagina %s de %s -> %s registros",
                 pagina, meta["pages"], len(registros))
        if pagina >= meta["pages"]:
            break
        pagina = pagina + 1
        time.sleep(config.PAUSA_BANCO)

    conferir(meta, len(registros))
    return registros, meta


def salvar(registros, prefixo):
    """Grava um arquivo por pacote de dados, no formato que veio do servidor.

    A API responde um array com os metadados na posicao 0 e os registros na
    posicao 1. Guarda-se so a lista de registros: o que o arquivo contem e o
    dado, e os metadados ficam na proveniencia, que e onde pertencem.
    """
    config.BRONZE_BANCO.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = config.BRONZE_BANCO / f"{prefixo}_{hoje}.json"
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def registrar(prefixo, destino, linhas, extra=None):
    """Acrescenta uma linha. Nunca sobrescreve a extracao anterior."""
    info = {
        "fonte": config.URL_BANCO,
        "pacote": prefixo,
        "arquivo_bronze": destino.name,
        "formato": "JSON",
        "registros": linhas,
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        info.update(extra)

    caminho = config.BRONZE_BANCO / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    log.info("banco_mundial: paises")
    paises = buscar_paises()
    destino = salvar(paises[1], "paises")
    registrar("paises", destino, len(paises[1]),
              extra={"lastupdated": paises[0].get("lastupdated")})
    log.info("gravado em: %s", destino.name)

    for codigo, prefixo in config.SERIES_BANCO.items():
        log.info("banco_mundial: %s (%s)", prefixo, codigo)
        registros, meta = percorrer(codigo)
        destino = salvar(registros, prefixo)
        registrar(prefixo, destino, len(registros), extra={
            "indicador": codigo,
            "lastupdated": meta["lastupdated"],
            "periodo": f"{config.ANO_INICIAL}-{config.ANO_FINAL}",
        })
        log.info("gravado em: %s", destino.name)


if __name__ == "__main__":
    config.configurar_log()
    main()
