-- A tabela achatada, agora como consulta com nome.
--
-- Nao guarda dado: toda vez que alguem consulta, o banco executa o join na
-- hora. As mesmas 17 colunas e as mesmas 10.545 linhas de
-- indicadores_enriquecidos.parquet, sem arquivo para manter e sem risco de
-- ficar desatualizada.
{{ config(materialized='view') }}

select
    f.pais_id,
    d.nome          as pais_nome,
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
from {{ ref('fato_expectativa') }} f
join {{ ref('dim_pais') }} d using (pais_id)
left join {{ ref('fato_contexto') }} c
       on f.pais_id = c.pais_id
      and f.ano = c.ano
