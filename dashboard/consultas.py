
from pathlib import Path

import duckdb
import streamlit as st






RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "dados" / "ouro" / "projeto.duckdb"


def banco_existe():
    
    return BANCO.exists()



@st.cache_data
def _consultar(sql, parametros=None):
    
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        return con.execute(sql, parametros or []).df()
    finally:
        con.close()




def regioes():
    
    return _consultar("""
        select distinct regiao
        from ouro.dim_pais
        where regiao is not null
        order by 1
    """)


def anos():
    
    return _consultar("""
        select distinct ano
        from ouro.fato_expectativa
        order by ano desc
    """)


def sexos():
    
    return _consultar("""
        select distinct sexo
        from ouro.fato_expectativa
        order by case sexo
                   when 'total' then 0
                   when 'feminino' then 1
                   else 2
                 end
    """)




def indicador_por_regiao(regiao, ano, sexo):
    
    return _consultar(
        """
        select
            pais_nome,
            expectativa_vida,
            variacao_pct,
            gasto_saude_pct_pib,
            pib_per_capita_usd,
            escolaridade_anos,
            dif_mediana_regiao
        from ouro.vw_indicador_completo
        where regiao = ? and ano = ? and sexo = ?
        order by expectativa_vida desc nulls last, pais_nome
        """,
        [regiao, ano, sexo],
    )


def resumo_da_regiao(regiao, ano, sexo):
    
    return _consultar(
        """
        select
            count(*)          as paises,
            avg(expectativa_vida) as media,
            avg(variacao_pct) as variacao_media
        from ouro.vw_indicador_completo
        where regiao = ? and ano = ? and sexo = ?
        """,
        [regiao, ano, sexo],
    )


def evolucao_do_pais(nome_pais, sexo):
    
    return _consultar(
        """
        select ano, expectativa_vida, dif_mediana_regiao
        from ouro.vw_indicador_completo
        where pais_nome = ? and sexo = ?
        order by ano
        """,
        [nome_pais, sexo],
    )
