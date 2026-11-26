import logging
import shutil
import sys
import time
from pathlib import Path

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

    
    transformar_paises.main()
    transformar_expectativa_vida.main()
    transformar_gasto_saude.main()
    transformar_determinantes.main()


def etapa_enriquecimento():
    import enriquecer

    enriquecer.main()


def etapa_carga():
    import carga

    carga.main()


def comando_dbt():
    caminho = shutil.which("dbt")
    if caminho:
        return caminho
    candidato = Path(sys.executable).parent / "dbt.exe"
    if candidato.exists():
        return str(candidato)
    raise FileNotFoundError(
        "dbt nao encontrado. Instale com: pip install dbt-core dbt-duckdb")


def etapa_modelagem():
    import subprocess

    import carga
    subprocess.run([comando_dbt(), "run"],
                   cwd=config.RAIZ / "ecox14", check=True)
    subprocess.run([comando_dbt(), "test"],
                   cwd=config.RAIZ / "ecox14", check=True)
    carga.verificar_banco()


ETAPAS = [
    ("ingestao", etapa_ingestao),
    ("transformacao", etapa_transformacao),
    ("enriquecimento", etapa_enriquecimento),
    ("carga", etapa_carga),
    ("modelagem", etapa_modelagem),
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
