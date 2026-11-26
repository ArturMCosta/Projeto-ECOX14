

import logging

import duckdb

import config

log = logging.getLogger(__name__)

BANCO = config.OURO / "projeto.duckdb"


TABELAS_PRATA = {
    "paises": "paises.parquet",
    "expectativa_vida": "expectativa_vida.parquet",
    "gasto_saude": "gasto_saude.parquet",
    "determinantes_socioeconomicos": "determinantes_socioeconomicos.parquet",
    "indicadores_enriquecidos": "indicadores_enriquecidos.parquet",
}


def um_valor(con, sql):
    
    return con.execute(sql).fetchone()[0]


def conectar():
    
    config.OURO.mkdir(parents=True, exist_ok=True)
    log.info("banco: %s", BANCO)
    return duckdb.connect(str(BANCO))


def criar_esquemas(con):
    
    for esquema in ("prata", "ouro"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
    log.info("esquemas prata e ouro prontos")


def carregar_prata(con):
    
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
    
    for tabela in ("dim_pais", "fato_expectativa", "fato_contexto",
                   "vw_indicador_completo"):
        log.info("ouro.%s: %s linhas", tabela,
                 um_valor(con, f"SELECT COUNT(*) FROM ouro.{tabela}"))

    
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
        
    finally:
        con.close()
    log.info("carga concluida")


if __name__ == "__main__":
    config.configurar_log()
    main()
