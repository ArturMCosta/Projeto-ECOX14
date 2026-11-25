-- Passa quando devolve ZERO linhas.
--
-- O grao da fato e pais + ano + sexo. Nenhum teste pronto cobre chave
-- composta: `unique` olha uma coluna so. Entao a consulta de conferencia da
-- aula de modelagem, que antes era um print no carga.py, vira regra que o
-- pipeline cobra sozinho.

select
    pais_id,
    ano,
    sexo,
    count(*) as linhas
from {{ ref('fato_expectativa') }}
group by pais_id, ano, sexo
having count(*) > 1
