"""Ponto de entrada do pipeline.

ISTO NAO E ORQUESTRACAO
=======================
Orquestrador de verdade (Airflow, Prefect, Dagster) agenda sozinho,
entende dependencia em grafo, tenta de novo quando falha, avisa
alguem, roda etapas em paralelo e reprocessa periodo passado.

Este arquivo nao faz nada disso. Ele e um ponto de entrada: roda as
etapas na ordem certa, registra o que aconteceu e para quando quebra.

Saber exatamente o que falta aqui e o que permite decidir, mais
tarde, se vale a pena adotar um orquestrador.

COMO EXECUTAR
=============
    python src/pipeline.py                  roda tudo
    python src/pipeline.py enriquecimento   retoma do meio

A retomada existe por um motivo pratico: reexecutar a ingestao bate
na API de novo e demora. Quando o erro esta na ultima etapa, voce
nao quer refazer a primeira.
"""

import logging
import sys
import time

import config

log = logging.getLogger(__name__)


def etapa_ingestao():
    import ingerir_banco_mundial
    import ingerir_who_gho

    ingerir_who_gho.main()
    ingerir_banco_mundial.main()


def etapa_transformacao():
    import transformar_determinantes
    import transformar_expectativa_vida
    import transformar_gasto_saude
    import transformar_paises

    # paises primeiro: os outros tres cruzam com a prata de paises.
    transformar_paises.main()
    transformar_expectativa_vida.main()
    transformar_gasto_saude.main()
    transformar_determinantes.main()


def etapa_enriquecimento():
    import enriquecer

    enriquecer.main()


ETAPAS = [
    ("ingestao", etapa_ingestao),
    ("transformacao", etapa_transformacao),
    ("enriquecimento", etapa_enriquecimento),
    ("carga", None),        # proxima aula
    ("modelagem", None),    # proxima aula
]


def executar(nome, funcao):
    log.info("etapa %s: inicio", nome)
    comeco = time.perf_counter()
    try:
        funcao()
    except Exception:
        log.exception("etapa %s falhou", nome)
        raise
    log.info("etapa %s: fim em %.0fs", nome, time.perf_counter() - comeco)


def main(a_partir_de=None):
    config.configurar_log()
    config.criar_pastas()

    nomes = [nome for nome, _ in ETAPAS]
    if a_partir_de and a_partir_de not in nomes:
        log.error("etapa desconhecida: %s", a_partir_de)
        log.error("etapas validas: %s", ", ".join(nomes))
        return 1

    comecou = a_partir_de is None
    for nome, funcao in ETAPAS:
        if nome == a_partir_de:
            comecou = True
        if not comecou:
            log.info("etapa %s: pulada", nome)
            continue
        if funcao is None:
            log.warning("etapa %s: ainda nao implementada", nome)
            continue
        executar(nome, funcao)

    log.info("pipeline concluido")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
