"""Carrega a Prata num banco DuckDB e confere o modelo construido pelo dbt.

O QUE ESTE SCRIPT FAZ
=====================
abre o banco, cria os esquemas prata e ouro, e copia os Parquet da prata
para dentro dele com read_parquet. Nada mais.

A Ouro NAO NASCE AQUI
=====================
Ela nasceu aqui ate a Aula 09, com CREATE TABLE dentro de strings do Python.
Na Aula 10 o SQL virou um arquivo por tabela em ecox14/models/, e quem
executa e o dbt. O construir_ouro() fica abaixo, comentado, para comparar
as duas formas.

O QUE SOBRA PARA ESTE MODULO
============================
conferir(): as mesmas provas da aula passada. Ela e chamada depois do dbt,
pela etapa modelagem, porque num banco novo a Ouro ainda nao existe quando
a carga termina.
"""

import logging

import duckdb

import config

log = logging.getLogger(__name__)

BANCO = config.OURO / "projeto.duckdb"

# Tabelas da prata que entram no banco como estao.
TABELAS_PRATA = {
    "paises": "paises.parquet",
    "expectativa_vida": "expectativa_vida.parquet",
    "gasto_saude": "gasto_saude.parquet",
    "determinantes_socioeconomicos": "determinantes_socioeconomicos.parquet",
    "indicadores_enriquecidos": "indicadores_enriquecidos.parquet",
}


def um_valor(con, sql):
    """Le um numero de dentro do banco.

    con.execute, e nao con.sql: o objeto devolvido por con.sql nem sempre
    tem fetchone.
    """
    return con.execute(sql).fetchone()[0]


def conectar():
    """Abre o banco. O arquivo e o banco inteiro; apagar recomeca do zero."""
    config.OURO.mkdir(parents=True, exist_ok=True)
    log.info("banco: %s", BANCO)
    return duckdb.connect(str(BANCO))


def criar_esquemas(con):
    """Camada deixa de ser pasta e passa a ser esquema."""
    for esquema in ("prata", "ouro"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
    log.info("esquemas prata e ouro prontos")


def carregar_prata(con):
    """Copia a prata para dentro do banco, sem importacao e sem declarar tipo.

    O Parquet ja traz o tipo de cada coluna. Se a prata fosse CSV, seria
    preciso redescrever as colunas aqui e torcer.
    """
    for tabela, arquivo in TABELAS_PRATA.items():
        caminho = config.PRATA / arquivo
        if not caminho.exists():
            raise FileNotFoundError(f"falta {caminho}")
        con.execute(f"""
            CREATE OR REPLACE TABLE prata.{tabela} AS
            SELECT * FROM read_parquet('{caminho.as_posix()}')
        """)
        linhas = um_valor(con, f"SELECT COUNT(*) FROM prata.{tabela}")
        log.info("prata.%s: %s linhas", tabela, linhas)


def construir_ouro(con):
    """Aposentada na Aula 10: quem constroi a Ouro agora e o dbt.

    O codigo fica aqui para comparar as duas formas -- e para mostrar o que
    o dbt faz por baixo: exatamente estes CREATE TABLE, com a ordem que
    antes so existia na cabeca de quem escreveu.
    """
    con.execute("""
        CREATE OR REPLACE TABLE ouro.dim_pais AS
        SELECT
            p.pais_id,
            p.pais_nome             AS nome,
            r.regiao_oms,
            p.regiao,
            CAST(p.nivel_renda AS VARCHAR) AS nivel_renda,
            p.capital,
            p.longitude,
            p.latitude
        FROM prata.paises p
        LEFT JOIN (
            SELECT pais_id, MAX(regiao_oms) AS regiao_oms
            FROM prata.expectativa_vida
            GROUP BY pais_id
        ) r ON p.pais_id = r.pais_id
    """)
    log.info("ouro.dim_pais: %s linhas",
             um_valor(con, "SELECT COUNT(*) FROM ouro.dim_pais"))

    # A entrada da fato e o arquivo enriquecido, como na aula. Mas so entra
    # o que e do grao dele: as colunas de dinheiro se repetem nas tres linhas
    # de sexo e vao para fato_contexto.
    con.execute("""
        CREATE OR REPLACE TABLE ouro.fato_expectativa AS
        SELECT
            pais_id,
            ano,
            CAST(sexo AS VARCHAR) AS sexo,
            expectativa_vida,
            ic_baixo,
            ic_alto,
            variacao_pct,
            CAST(expectativa_vida_faixa AS VARCHAR) AS expectativa_vida_faixa,
            dif_mediana_regiao
        FROM prata.indicadores_enriquecidos
        WHERE pais_id IN (SELECT pais_id FROM ouro.dim_pais)
    """)
    log.info("ouro.fato_expectativa: %s linhas",
             um_valor(con, "SELECT COUNT(*) FROM ouro.fato_expectativa"))

    # O contexto vem das duas tabelas que tem grão pais-ano. FULL OUTER, e nao
    # LEFT: 446 pares pais-ano so tem PIB e escolaridade, e sete so tem gasto.
    con.execute("""
        CREATE OR REPLACE TABLE ouro.fato_contexto AS
        WITH g AS (
            SELECT pais_id, ano, gasto_saude_pct_pib, gasto_saude_per_capita_usd
            FROM prata.gasto_saude
            WHERE pais_id IN (SELECT pais_id FROM ouro.dim_pais)
        ), d AS (
            SELECT pais_id, ano, pib_per_capita_usd, escolaridade_anos,
                   CAST(escolaridade_anos_faixa AS VARCHAR) AS escolaridade_anos_faixa
            FROM prata.determinantes_socioeconomicos
            WHERE pais_id IN (SELECT pais_id FROM ouro.dim_pais)
        )
        SELECT
            COALESCE(g.pais_id, d.pais_id) AS pais_id,
            COALESCE(g.ano, d.ano)         AS ano,
            g.gasto_saude_pct_pib,
            g.gasto_saude_per_capita_usd,
            d.pib_per_capita_usd,
            d.escolaridade_anos,
            d.escolaridade_anos_faixa
        FROM g
        FULL OUTER JOIN d ON g.pais_id = d.pais_id AND g.ano = d.ano
    """)
    log.info("ouro.fato_contexto: %s linhas",
             um_valor(con, "SELECT COUNT(*) FROM ouro.fato_contexto"))

    # O filtro de integridade tem preco, e o preco vai para o log.
    for tabela in ("gasto_saude", "determinantes_socioeconomicos"):
        fora = um_valor(con, f"""
            SELECT COUNT(*) FROM prata.{tabela} t
            LEFT JOIN ouro.dim_pais d USING (pais_id)
            WHERE d.pais_id IS NULL
        """)
        if fora:
            log.warning("%s: %s linhas ficaram fora da fato, sem pais na dimensao",
                        tabela, fora)

    con.execute("""
        CREATE OR REPLACE VIEW ouro.vw_indicador_completo AS
        SELECT
            f.pais_id,
            d.nome          AS pais_nome,
            f.ano,
            f.sexo,
            d.regiao_oms,
            f.expectativa_vida,
            f.ic_baixo,
            f.ic_alto,
            f.variacao_pct,
            f.expectativa_vida_faixa,
            c.gasto_saude_pct_pib,
            c.gasto_saude_per_capita_usd,
            c.pib_per_capita_usd,
            c.escolaridade_anos,
            d.regiao,
            d.nivel_renda,
            f.dif_mediana_regiao
        FROM ouro.fato_expectativa f
        JOIN ouro.dim_pais d USING (pais_id)
        LEFT JOIN ouro.fato_contexto c
               ON f.pais_id = c.pais_id AND f.ano = c.ano
    """)
    log.info("ouro.vw_indicador_completo: criada")


def conferir(con):
    """Confere o que o dbt nao cobre.

    Grao, integridade e regiao da OMS unica sairam daqui: viraram testes
    declarados em ecox14/models/schema.yml e ecox14/tests/, que a etapa de
    modelagem roda com `dbt test`. Ficam as contagens -- que sao numero, nao
    regra -- e a prova que compara com o Parquet, que o dbt nao faz.
    """
    for tabela in ("dim_pais", "fato_expectativa", "fato_contexto",
                   "vw_indicador_completo"):
        log.info("ouro.%s: %s linhas", tabela,
                 um_valor(con, f"SELECT COUNT(*) FROM ouro.{tabela}"))

    # A prova final: a view remonta a tabela achatada, linha por linha.
    caminho = (config.PRATA / "indicadores_enriquecidos.parquet").as_posix()
    diferencas = um_valor(con, f"""
        SELECT COUNT(*) FROM (
            (SELECT * FROM ouro.vw_indicador_completo
             EXCEPT ALL
             SELECT * FROM read_parquet('{caminho}'))
            UNION ALL
            (SELECT * FROM read_parquet('{caminho}')
             EXCEPT ALL
             SELECT * FROM ouro.vw_indicador_completo)
        )
    """)
    log.info("view x tabela achatada: %s linhas de diferenca (esperado 0)",
             diferencas)
    if diferencas:
        raise ValueError(f"a view nao remonta o parquet: {diferencas} linhas")


def verificar_banco():
    """Confere o modelo depois que o dbt criou a Ouro.

    A conferencia saiu do main porque, num banco novo, a Ouro ainda nao
    existe quando a carga termina: quem cria e a etapa seguinte.
    """
    con = conectar()
    try:
        conferir(con)
    finally:
        con.close()


def main():
    con = conectar()
    try:
        criar_esquemas(con)
        carregar_prata(con)
        # construir_ouro(con)   <- agora e o dbt
    finally:
        con.close()
    log.info("carga concluida")


if __name__ == "__main__":
    config.configurar_log()
    main()
