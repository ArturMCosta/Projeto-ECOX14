-- Passa quando devolve ZERO linhas.
--
-- A dimensao pega a regiao da OMS com max(regiao_oms) por pais. Se um pais
-- aparecesse em duas regioes, esse max escolheria uma das duas sem avisar, e
-- o erro so apareceria numa analise por regiao. A prova que estava no
-- carga.conferir() virou teste da origem: e a prata que precisa garantir
-- isso, nao a Ouro.

select
    pais_id,
    count(distinct regiao_oms) as regioes
from {{ source('prata', 'expectativa_vida') }}
group by pais_id
having count(distinct regiao_oms) > 1
