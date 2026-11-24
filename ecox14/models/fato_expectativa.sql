-- Uma linha por pais, ano e sexo.
--
-- So entram as colunas desse grao: as de dinheiro se repetem nas tres linhas
-- de sexo e moram em fato_contexto. O filtro de integridade usa a dimensao,
-- entao o dbt sabe que esta fato depende de dim_pais.

select
    pais_id,
    ano,
    cast(sexo as varchar)                              as sexo,
    expectativa_vida,
    ic_baixo,
    ic_alto,
    variacao_pct,
    cast(expectativa_vida_faixa as varchar)            as expectativa_vida_faixa,
    dif_mediana_regiao
from {{ source('prata', 'indicadores_enriquecidos') }}
where pais_id in (select pais_id from {{ ref('dim_pais') }})
