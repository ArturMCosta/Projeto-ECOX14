

import logging
import sys
from pathlib import Path




RAIZ = Path(__file__).resolve().parent.parent

DADOS = RAIZ / "dados"
BRONZE = DADOS / "bronze"
PRATA = DADOS / "prata"
OURO = DADOS / "ouro"
RELATORIOS = RAIZ / "relatorios"


BRONZE_WHO = BRONZE / "who_gho"
BRONZE_BANCO = BRONZE / "banco_mundial"


URL_WHO = "https://ghoapi.azureedge.net/api"
URL_BANCO = "https://api.worldbank.org/v2"

ANO_INICIAL = 2000
ANO_FINAL = 2018

POR_PAGINA_WHO = 1000
POR_PAGINA_BANCO = 300
PAUSA_BANCO = 0.5


INDICADORES_WHO = {
    "WHOSIS_000001": "expectativa_vida",
    "GHED_CHEGDP_SHA2011": "gasto_saude_pct_pib",
    "GHED_CHE_pc_US_SHA2011": "gasto_saude_per_capita",
}

SERIES_BANCO = {
    "NY.GDP.PCAP.CD": "pib_per_capita",
    "SE.SCH.LIFE": "escolaridade",
}


ARQUIVO_LOG = RAIZ / "pipeline.log"


def configurar_log(nivel=logging.INFO):
    
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def criar_pastas():
    for pasta in (BRONZE_WHO, BRONZE_BANCO, PRATA, OURO, RELATORIOS):
        pasta.mkdir(parents=True, exist_ok=True)
