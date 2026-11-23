"""Configuracao central do projeto.

O QUE ENTRA AQUI
================
    caminhos de pasta e arquivo
    parametros que voce ajusta e reexecuta (indicador, periodo)
    a ordem das camadas

O QUE NAO ENTRA
===============
    logica de transformacao
    qualquer coisa que mude a cada execucao
    segredo: senha, token, chave de API

Segredo nunca vem para ca, porque este arquivo vai para o GitHub.
Token e senha ficam em variavel de ambiente ou em arquivo ignorado,
como o kaggle.json.

O TESTE
=======
Se alguem for rodar o projeto em outra maquina, ou com outro
indicador, quais linhas essa pessoa precisa editar? Essas linhas
pertencem a este arquivo.
"""

import logging
import sys
from pathlib import Path

# RAIZ calculada a partir do proprio arquivo: o caminho deixa de
# depender de onde voce esta quando roda. Rodar de dentro de src
# ou da raiz da no mesmo lugar.
RAIZ = Path(__file__).resolve().parent.parent

DADOS = RAIZ / "dados"
BRONZE = DADOS / "bronze"
PRATA = DADOS / "prata"
OURO = DADOS / "ouro"
RELATORIOS = RAIZ / "relatorios"

# A bronze tem dois niveis: a origem, depois o pacote de dados.
BRONZE_WHO = BRONZE / "who_gho"
BRONZE_BANCO = BRONZE / "banco_mundial"

# ---------------------------------------------------------- parametros
URL_WHO = "https://ghoapi.azureedge.net/api"
URL_BANCO = "https://api.worldbank.org/v2"

ANO_INICIAL = 2000
ANO_FINAL = 2018

POR_PAGINA_WHO = 1000
POR_PAGINA_BANCO = 300
PAUSA_BANCO = 0.5

# codigo do indicador na fonte -> prefixo do arquivo na bronze
INDICADORES_WHO = {
    "WHOSIS_000001": "expectativa_vida",
    "GHED_CHEGDP_SHA2011": "gasto_saude_pct_pib",
    "GHED_CHE_pc_US_SHA2011": "gasto_saude_per_capita",
}

SERIES_BANCO = {
    "NY.GDP.PCAP.CD": "pib_per_capita",
    "SE.SCH.LIFE": "escolaridade",
}

# ------------------------------------------------------------- logging
ARQUIVO_LOG = RAIZ / "pipeline.log"


def configurar_log(nivel=logging.INFO):
    """Manda a mesma mensagem para a tela e para o arquivo.

    Os dois handlers fazem a saida ser dupla. O arquivo entra no
    .gitignore: e registro de execucao, nao codigo.

    O console escreve em stdout, e nao no stderr padrao: no
    PowerShell, stderr de programa externo aparece como erro.
    """
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
