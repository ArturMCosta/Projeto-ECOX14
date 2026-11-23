"""Enriquece a serie de expectativa de vida com o que falta nela.

O QUE ESTE SCRIPT RESOLVE
=========================
A expectativa de vida e a tabela que responde a pergunta e a mais fina das
quatro: uma linha por pais, ano e sexo. Mas ela nao tem PIB, nao tem
escolaridade, nao tem gasto em saude -- e a regiao que carrega e a da OMS
(regiao_oms), nao a do Banco Mundial.

Enriquecer e trazer para perto o que estava separado. Nenhum valor nasce
aqui: o que era de outra tabela muda de endereco. A unica coluna calculada
e dif_mediana_regiao, e ela so existe porque a regiao do Banco Mundial
chegou pela juncao.

A ORDEM DAS JUNCOES
===================
A serie fica a esquerda em todas, porque e ela que responde a pergunta e
porque e o grao mais fino. Gasto e determinantes tem uma linha por pais e
ano, entao a relacao esperada e many_to_one.

O GRAO DO RESULTADO E pais + ano + sexo
=======================================
As colunas de dinheiro se repetem nas tres linhas de sexo do mesmo pais e
ano. Somar gasto ou PIB nesta tabela conta o mesmo pais tres vezes. Para
dinheiro, use gasto_saude.parquet ou determinantes_socioeconomicos.parquet.

Como executar:
    python src/pipeline.py enriquecimento
    python src/enriquecer.py
"""

import json
import logging
from datetime import datetime

import pandas as pd

import config
import juncao

log = logging.getLogger(__name__)

SERIE = config.PRATA / "expectativa_vida.parquet"
GASTO = config.PRATA / "gasto_saude.parquet"
DETERMINANTES = config.PRATA / "determinantes_socioeconomicos.parquet"
CADASTRO = config.PRATA / "paises.parquet"

DESTINO = config.PRATA / "indicadores_enriquecidos.parquet"

CHAVE = ["pais_id", "ano"]


def carregar():
    serie = pd.read_parquet(SERIE)
    gasto = pd.read_parquet(GASTO)
    determinantes = pd.read_parquet(DETERMINANTES)
    cadastro = pd.read_parquet(CADASTRO)

    log.info("serie: %s", serie.shape)
    log.info("gasto: %s", gasto.shape)
    log.info("determinantes: %s", determinantes.shape)
    log.info("cadastro: %s", cadastro.shape)
    return serie, gasto, determinantes, cadastro


def enriquecer(serie, gasto, determinantes, cadastro):
    """Junta as tres fontes na serie, uma de cada vez, conferindo cada passo."""
    antes = len(serie)

    log.info("serie x gasto em saude")
    juncao.conferir_chaves(serie, gasto, "pais_id", "pais_id")
    com_gasto = juncao.juntar(
        serie,
        gasto[CHAVE + ["gasto_saude_pct_pib", "gasto_saude_per_capita_usd"]],
        CHAVE, CHAVE, relacao="many_to_one",
    )
    juncao.validar(serie, com_gasto, "gasto_saude_pct_pib")

    log.info("serie x determinantes socioeconomicos")
    juncao.conferir_chaves(com_gasto, determinantes, "pais_id", "pais_id")
    com_determinantes = juncao.juntar(
        com_gasto,
        determinantes[CHAVE + ["pib_per_capita_usd", "escolaridade_anos"]],
        CHAVE, CHAVE, relacao="many_to_one",
    )
    juncao.validar(com_gasto, com_determinantes, "pib_per_capita_usd")

    log.info("serie x cadastro (regiao e nivel de renda do Banco Mundial)")
    juncao.conferir_chaves(com_determinantes, cadastro, "pais_id", "pais_id")
    com_cadastro = juncao.juntar(
        com_determinantes,
        cadastro[["pais_id", "regiao", "nivel_renda"]],
        "pais_id", "pais_id", relacao="many_to_one",
    )
    sem_par = juncao.validar(com_determinantes, com_cadastro, "regiao")

    if len(com_cadastro) != antes:
        log.warning("a serie tinha %s linhas e ficou com %s",
                    antes, len(com_cadastro))

    return com_cadastro, sem_par


def diferenca_mediana_regiao(df):
    """Atributo que so existe depois da juncao.

    Quanto o pais esta acima ou abaixo da mediana da sua regiao do Banco
    Mundial, no mesmo ano e no mesmo sexo. Antes do enriquecimento esta
    conta era impossivel: a serie traz a regiao da OMS, nao a do Banco.

    O sexo entra no agrupamento. Sem ele, a expectativa masculina seria
    comparada com a mediana dos tres sexos, e a diferenca mediria a
    distincao entre sexos em vez da distincao entre paises.

    A mediana, e nao a media: dentro de uma regiao ha paises muito
    distantes entre si, e a media se desloca com um extremo.
    """
    mediana = df.groupby(["regiao", "ano", "sexo"], observed=True)[
        "expectativa_vida"
    ].transform("median")
    df["dif_mediana_regiao"] = (df["expectativa_vida"] - mediana).round(1)

    log.info("linhas com o atributo: %s",
             int(df["dif_mediana_regiao"].notna().sum()))
    return df


def registrar(resultado, sem_par, decisoes):
    info = {
        "origem_esquerda": [SERIE.name, GASTO.name, DETERMINANTES.name],
        "origem_direita": CADASTRO.name,
        "arquivo_prata": DESTINO.name,
        "chave": "pais_id + ano (cadastro: pais_id)",
        "tipo_de_juncao": "left",
        "validacao": "many_to_one",
        "linhas_resultado": len(resultado),
        "linhas_sem_par": len(sem_par),
        "atributos_derivados": ["dif_mediana_regiao"],
        "decisoes": decisoes,
        "transformado_em": datetime.now().isoformat(timespec="seconds"),
    }
    with (config.PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    serie, gasto, determinantes, cadastro = carregar()

    resultado, sem_par = enriquecer(serie, gasto, determinantes, cadastro)

    resultado = diferenca_mediana_regiao(resultado)

    resultado.to_parquet(DESTINO, index=False)
    log.info("salvo em: %s, %s", DESTINO.name, resultado.shape)

    registrar(resultado, sem_par, [
        "serie a esquerda: e o grao mais fino e o que responde a pergunta",
        "gasto e determinantes entram como many_to_one, com validate",
        "cadastro entra pela regiao e nivel de renda do Banco Mundial: "
        "a serie so tem a regiao da OMS",
        "derivado dif_mediana_regiao: pais contra a mediana da regiao, "
        "no mesmo ano e sexo",
        "colunas de dinheiro repetem nas tres linhas de sexo: nao somar aqui",
    ])


if __name__ == "__main__":
    config.configurar_log()
    main()
