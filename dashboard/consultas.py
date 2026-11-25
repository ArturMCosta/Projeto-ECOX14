"""
Onde o SQL do painel fica.

POR QUE ESTE ARQUIVO EXISTE
===========================
Na aula de dbt dissemos que SQL dentro de string de Python e ruim. Aquilo
valia para o SQL de TRANSFORMACAO, o que cria tabela: esse foi para o dbt,
versionado e testado.

Sobra o SQL de CONSULTA, que so le para mostrar. Ele precisa existir em
algum lugar, e o lugar nao e o arquivo da tela.

A pergunta que separa os dois: se alguem pedir esse mesmo numero por e-mail,
sem abrir o painel, a consulta existe em algum lugar reaproveitavel? Se nao
existe, ela esta no lugar errado.

Com este modulo, o painel.py fica so com tela, e cada pergunta que o painel
faz vira uma funcao com nome.
"""
from pathlib import Path

import duckdb
import streamlit as st

# Mesma ideia do config.py: o caminho vem deste arquivo, e nao da pasta de
# onde voce rodou o comando.
#   __file__        dashboard/consultas.py
#   .parent         dashboard/
#   .parent.parent  a raiz do projeto
RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "dados" / "ouro" / "projeto.duckdb"


def banco_existe():
    """Para o painel avisar em vez de estourar erro de conexao."""
    return BANCO.exists()


# O cache evita refazer a consulta a cada clique na tela.
@st.cache_data
def _consultar(sql, parametros=None):
    """Roda uma consulta e devolve um DataFrame.

    read_only=True porque o painel so le: sem isso ele trava o banco e o
    pipeline (ou o dbt) nao consegue rodar enquanto a tela estiver aberta.
    """
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        return con.execute(sql, parametros or []).df()
    finally:
        con.close()


# ----------------------------------------------------------- filtros

def regioes():
    """Regioes do Banco Mundial disponiveis, para o filtro da tela."""
    return _consultar("""
        select distinct regiao
        from ouro.dim_pais
        where regiao is not null
        order by 1
    """)


def anos():
    """Anos disponiveis, do mais recente para o mais antigo."""
    return _consultar("""
        select distinct ano
        from ouro.fato_expectativa
        order by ano desc
    """)


def sexos():
    """Os tres recortes da serie, com o total primeiro."""
    return _consultar("""
        select distinct sexo
        from ouro.fato_expectativa
        order by case sexo
                   when 'total' then 0
                   when 'feminino' then 1
                   else 2
                 end
    """)


# ---------------------------------------------------------- perguntas

def indicador_por_regiao(regiao, ano, sexo):
    """Expectativa de vida dos paises de uma regiao, num ano e sexo.

    O sexo entra no filtro porque a serie tem tres recortes por pais e ano:
    sem ele, o mesmo pais seria contado tres vezes.

    O nome da funcao e a pergunta que ela responde. Se o nome ficar dificil
    de escrever, a consulta provavelmente esta fazendo coisa demais.
    """
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
    """Numeros de cabecalho da regiao, para os cartoes do topo.

    A media e calculada pelo banco, e nao no Python: a conta e uma pergunta
    sobre o dado, entao mora aqui.
    """
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
    """Serie completa de um pais, ano a ano, no mesmo recorte de sexo."""
    return _consultar(
        """
        select ano, expectativa_vida, dif_mediana_regiao
        from ouro.vw_indicador_completo
        where pais_nome = ? and sexo = ?
        order by ano
        """,
        [nome_pais, sexo],
    )
