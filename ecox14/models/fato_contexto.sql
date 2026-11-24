-- Uma linha por pais e ano.
--
-- FULL OUTER JOIN, e nao LEFT: 446 pares pais-ano so tem PIB e escolaridade,
-- e 7 so tem gasto. Com LEFT por qualquer um dos lados, um dos dois grupos
-- desapareceria sem aviso.

with gasto as (
    select pais_id, ano, gasto_saude_pct_pib, gasto_saude_per_capita_usd
    from {{ source('prata', 'gasto_saude') }}
    where pais_id in (select pais_id from {{ ref('dim_pais') }})
),

determinantes as (
    select
        pais_id,
        ano,
        pib_per_capita_usd,
        escolaridade_anos,
        cast(escolaridade_anos_faixa as varchar) as escolaridade_anos_faixa
    from {{ source('prata', 'determinantes_socioeconomicos') }}
    where pais_id in (select pais_id from {{ ref('dim_pais') }})
)

select
    coalesce(gasto.pais_id, determinantes.pais_id) as pais_id,
    coalesce(gasto.ano, determinantes.ano)         as ano,
    gasto.gasto_saude_pct_pib,
    gasto.gasto_saude_per_capita_usd,
    determinantes.pib_per_capita_usd,
    determinantes.escolaridade_anos,
    determinantes.escolaridade_anos_faixa
from gasto
full outer join determinantes
    on gasto.pais_id = determinantes.pais_id
   and gasto.ano = determinantes.ano
