-- Uma linha por pais.
--
-- A regiao da OMS nao esta em prata.paises: ela vem da serie da OMS, e e
-- 1:1 com o pais (nenhum pais aparece em duas regioes). Por isso o group by
-- basta e nao duplica a dimensao.

select
    p.pais_id,
    p.pais_nome                      as nome,
    r.regiao_oms,
    p.regiao,
    cast(p.nivel_renda as varchar)   as nivel_renda,
    p.capital,
    p.longitude,
    p.latitude
from {{ source('prata', 'paises') }} p
left join (
    select pais_id, max(regiao_oms) as regiao_oms
    from {{ source('prata', 'expectativa_vida') }}
    group by pais_id
) r on p.pais_id = r.pais_id
