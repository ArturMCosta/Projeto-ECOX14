-- Passa quando devolve ZERO linhas.
--
-- O grao da fato de contexto e pais + ano. A chave e composta, e por isso
-- `unique` nao serve: o mesmo pais aparece em 19 anos, e o mesmo ano em 217
-- paises. So o group by nas duas colunas responde a pergunta.

select
    pais_id,
    ano,
    count(*) as linhas
from {{ ref('fato_contexto') }}
group by pais_id, ano
having count(*) > 1
