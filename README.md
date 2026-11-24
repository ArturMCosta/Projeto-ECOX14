# Life Expectancy — bronze, prata e ouro

**Pergunta norteadora:** por que alguns países vivem mais que outros — quanto
o nível de renda, a escolaridade e o gasto em saúde explicam da expectativa
de vida?

## Como rodar

Um comando, de qualquer pasta:

```bash
python src/pipeline.py
```

| Etapa | O que faz |
|---|---|
| `ingestao` | baixa os pacotes: 3 indicadores da OMS e 3 do Banco Mundial |
| `transformacao` | gera as 4 tabelas da prata |
| `enriquecimento` | gera `indicadores_enriquecidos.parquet` |
| `carga` | cria o banco Ouro: dimensão, duas fatos e a view |
| `modelagem` | roda o dbt: os quatro modelos da Ouro, na ordem do grafo |

Retomar de uma etapa, sem refazer as anteriores:

```bash
python src/pipeline.py enriquecimento
```

A retomada existe por um motivo prático: reexecutar a ingestão bate na API de
novo e demora. Bater na API sem necessidade não é só lento — é sobrecarregar
um serviço público e gratuito.

As etapas que faltam aparecem como `None` no `ETAPAS` do `pipeline.py`: o
pipeline **declara o que ainda não tem**, em vez de esconder. Hoje não sobrou
nenhum: as cinco etapas são funções.

**Isto não é um orquestrador.** Não agenda, não repete quando falha, não avisa
ninguém, não roda etapas em paralelo. É um ponto de entrada que roda na ordem
certa, registra o que aconteceu e para quando quebra — e saber exatamente o que
falta aqui é o que permite decidir depois se vale adotar Airflow, Prefect ou
Dagster.

## Configuração e log

Caminhos, URLs, período e códigos de indicador ficam em `src/config.py`. A raiz
do projeto é calculada a partir do próprio arquivo
(`Path(__file__).resolve().parent.parent`), então o caminho deixa de depender
de onde você está quando roda.

Toda mensagem vai para a tela **e** para `pipeline.log`, com hora, nível e
módulo de origem:

```
20:00:15 INFO    transformar_paises: lido: paises_20261015.json, 296 registros
20:00:17 WARNING juncao: sem par: 38
20:00:17 INFO    __main__: etapa transformacao: fim em 2s
```

| Nível | Quando |
|---|---|
| `DEBUG` | detalhe para achar um bug hoje |
| `INFO` | o pipeline andou — é o que você quer saber amanhã |
| `WARNING` | estranho, mas seguiu (38 linhas sem par, 6 coordenadas ausentes) |
| `ERROR` | não deu para continuar |

Se uma etapa falha, o `log.exception` grava o rastro completo com a linha exata
e o `raise` devolve o erro para cima: **o pipeline para**, em vez de seguir para
a etapa seguinte com dado pela metade.

O `pipeline.log` está no `.gitignore` — é registro de execução, não código.

## Fontes

| Fonte | Pacote | Formato | Registros |
|---|---|---|---|
| WHO Global Health Observatory | `WHOSIS_000001` expectativa de vida | JSON | 11.172 |
| WHO Global Health Observatory | `GHED_CHEGDP_SHA2011` gasto em saúde % do PIB | JSON | 3.824 |
| WHO Global Health Observatory | `GHED_CHE_pc_US_SHA2011` gasto em saúde por habitante | JSON | 3.824 |
| Banco Mundial | `/v2/country` lista de países | JSON | 296 |
| Banco Mundial | `NY.GDP.PCAP.CD` PIB per capita | JSON | 5.054 |
| Banco Mundial | `SE.SCH.LIFE` escolaridade esperada | JSON | 5.168 |

A camada bronze guarda um arquivo por pacote de dados, no formato que o servidor
entregou — 29.338 registros no total.

O `/v2/country` não é uma série temporal: é o dicionário com nome, região,
nível de renda e coordenadas. A WHO devolve só o código ISO3 do país, então é
ele que dá nome aos registros das outras séries.

## O que os relatórios alertaram

Alertas da seção **Alerts** de cada relatório, e a correção aplicada.

### Banco Mundial — `paises`

| Alerta | Correção |
|---|---|
| `id`, `name` com valores únicos | chave confirmada: `pais_id` |
| `capitalCity`, `longitude`, `latitude` com 84 ausentes (28,5%) | são os 79 agregados; capital vazia em agrupamento não se aplica |
| `region.*`, `incomeLevel.*`, `lendingType.*` com 78 ausentes (26,4%) | os mesmos agregados, separados na entrada da prata |
| correlações altas | `id`, `iso2code` e `value` se repetem em cada bloco; só o `value` foi mantido |
| nomes de região com espaço no fim | `tirar_espacos()` |
| nível de renda como texto livre | `tipar_categoria()` com a ordem `Low` → `Lower middle` → `Upper middle` → `High` |

### Banco Mundial — `pib_per_capita` e `escolaridade`

| Alerta | Correção |
|---|---|
| `unit` e `obs_status` como texto vazio em todas as linhas | removidas: o teste olha nulo e string vazia |
| `indicator.id`, `indicator.value`, `decimal` constantes | informação repetida nas 5.054 e 5.168 linhas, não guardada |
| `value` com 144 ausentes (2,9%) no PIB | mantidos |
| `value` com **2.214 ausentes (42,8%)** na escolaridade | motivo do recorte ir só até 2018 |
| `countryiso3code` com 95 e 266 ausentes | linhas de agregado sem código de país de verdade, separadas |
| 107 linhas sem PIB e sem escolaridade | territórios sem economia registrada (Gibraltar, Ilhas Cayman…), removidas |

### WHO — `expectativa_vida`, `gasto_saude_*`

| Alerta | Correção |
|---|---|
| `SpatialDimType` desbalanceado | **é o sinal do misto país/agregado**: 627 de 11.172 linhas, separados pela própria coluna que declara o que cada registro é |
| `Value` traz `'54.2 [51.2-57.2]'` | número lido de `NumericValue`; nenhuma conversão perdeu dado |
| `Dim1`, `Low`, `High` vazios | só a expectativa de vida tem sexo e intervalo de confiança |
| `TimeDimType` constante `"YEAR"` | confirma série anual: ano em inteiro, não em data |
| correlações altas | `TimeDim`, `TimeDimensionValue`, `Begin` e `End` dizem a mesma coisa |
| não vem o nome do país | cruzamento com o dicionário do Banco Mundial, sem perder linha |

## O que cada arquivo virou

| Bronze (JSON) | Registros | → Prata (Parquet) | Registros | Chave |
|---|---|---|---|---|
| `expectativa_vida` | 11.172 | `expectativa_vida.parquet` | 10.545 | `pais_id` + `ano` + `sexo` |
| `gasto_saude_pct_pib` + `gasto_saude_per_capita` | 3.824 | `gasto_saude.parquet` | 3.615 | `pais_id` + `ano` |
| `paises` | 296 | `paises.parquet` | 217 | `pais_id` |
| `pib_per_capita` + `escolaridade` | 10.222 | `determinantes_socioeconomicos.parquet` | 4.016 | `pais_id` + `ano` |

Na expectativa de vida, 627 das 11.172 linhas eram grupos de países; no
gasto em saúde, 209 das 3.824. Na lista de países, 79 dos 296 registros eram
agregados.

A quinta tabela não vem de um pacote novo: ela **junta três das anteriores**.
`indicadores_enriquecidos.parquet` tem as 10.545 linhas da expectativa de vida,
o grão mais fino, com o gasto, o PIB, a escolaridade, a região e o nível de
renda ao lado. É o assunto da seção abaixo.

A expectativa de vida **não** é "um país por ano": a WHO publica a mesma
medida para homens, mulheres e total, na mesma tabela.

Um pacote pode virar uma tabela com dois pacotes (junção por país e ano), e um
mesmo pacote pode alimentar mais de uma tabela.

## Enriquecimento: a junção que fecha o grão

Enriquecer é acrescentar a um registro uma informação que já existe em outra
tabela. **Nenhum valor nasce aqui**: o que era de outro arquivo muda de
endereço. É o `merge`, e é por isso que a tabela final tem colunas que nenhuma
fonte sozinha possui.

A série de expectativa de vida fica sempre à esquerda: é ela que responde à
pergunta e é o grão mais fino (país + ano + sexo). Gasto e determinantes têm
uma linha por país e ano, então a relação esperada é `many_to_one` — e é isso
que o `validate` declara em cada junção.

### As chaves, conferidas antes de juntar

| Junção | Só na série | Só na outra | Nas duas |
|---|---:|---:|---:|
| expectativa × `gasto_saude` | 2 (`PRI`, `PRK`) | 12 | 183 |
| expectativa × `determinantes` | 0 | 32 | 185 |
| expectativa × `paises` | 0 | 32 | 185 |

Esses três números são a previsão do que a junção vai fazer. Conferir depois
seria tarde: já não daria para distinguir quem não casou de quem casou trazendo
valor ausente.

### A conta antes e depois

| Junção | Relação | Antes | Depois | Sem par |
|---|---|---:|---:|---:|
| × `gasto_saude` | `many_to_one` | 10.545 | 10.545 | 345 |
| × `determinantes` | `many_to_one` | 10.545 | 10.545 | 111 |
| × `paises` | `many_to_one` | 10.545 | 10.545 | **0** |

Nenhuma linha se perdeu e nenhuma se repetiu. As 345 e as 111 sem par são
lacunas da fonte, não erro de junção: 115 pares de país e ano sem gasto
registrado e 37 sem PIB, multiplicados pelas três linhas de sexo.

As junções que já existiam nos scripts de transformação também passaram a
declarar a relação esperada:

| Junção | Relação | Onde |
|---|---|---|
| série × `paises` | `many_to_one` | `limpeza.cruzar_com_paises()` |
| gasto % do PIB × gasto por habitante | `one_to_one` | `transformar_gasto_saude.py` |
| PIB × escolaridade | `one_to_one` | `transformar_determinantes.py` |

### Quem não casou, e por quê

São três grupos, e não dois:

| Grupo | Linhas na tabela enriquecida | Por quê |
|---|---:|---|
| País | 10.545 | casaram com o cadastro |
| Entidade sem cadastro | 0 | a série só traz país; as 38 linhas sem cadastro (Ilhas Cook e Niue) estão em `gasto_saude.parquet` |
| Agregado | 0 | os 627 regionais já saíram na prata, pela coluna `SpatialDimType` |

E o achado que o `left` deixa visível, na direção contrária: **32 países do
cadastro não têm série de expectativa de vida** — Andorra, Bermudas, Hong Kong,
Mônaco, Liechtenstein, Kosovo e outros pequenos territórios. Se a junção
começasse pelo cadastro, eles apareceriam com valor ausente; começando pela
série, eles simplesmente não entram. O `left` não esconde nenhum dos dois lados,
mas **a escolha do lado é uma decisão** — e está registrada aqui.

### O atributo que só existe depois da junção

**`dif_mediana_regiao`** — quantos anos o país está acima ou abaixo da mediana
da sua região do Banco Mundial, **no mesmo ano e no mesmo sexo**.

Antes da junção essa conta era impossível: a série traz a região da OMS
(`regiao_oms`), que vem na própria fonte. A região do Banco Mundial chega pelo
cadastro, e é ela que permite comparar o país com os vizinhos.

| País e ano | Sexo | Expectativa | Região | Diferença |
|---|---|---:|---|---:|
| Haiti (2010) | total | 39,9 | Latin America & Caribbean | **−34,7** |
| Central African Republic (2009) | total | 25,5 | Sub-Saharan Africa | **−34,2** |
| Brasil (2018) | total | 75,4 | Latin America & Caribbean | **+0,5** |
| Seychelles (2000) | feminino | 76,2 | Sub-Saharan Africa | **+22,0** |

As maiores distâncias negativas são **os mesmos eventos** da seção anterior:
Haiti 2010, República Centro-Africana 2009, Somália 2011. O atributo chegou a
elas por outro caminho, sem olhar a variação — é a confirmação de que o dado
está contando a mesma história por duas contas independentes.

São 5.168 linhas acima da mediana, 5.165 abaixo e 212 empatadas.

### A armadilha do grão

O resultado assume o grão da tabela mais fina: **país + ano + sexo**. As
colunas de dinheiro se repetem nas três linhas de sexo do mesmo país e ano.

| Soma de `gasto_saude_per_capita_usd` em 2018 | Valor |
|---|---:|
| na tabela enriquecida | US$ 595.567 |
| na tabela de gasto | US$ 231.161 |

A segunda está certa. A primeira é **2,58 vezes** maior porque soma cada país
três vezes — e a soma é uma operação perfeitamente válida, então nada avisa.
Para dinheiro, use `gasto_saude.parquet` ou `determinantes_socioeconomicos.parquet`.


## Modelagem e carga: a camada Ouro

A camada deixa de ser pasta e vira esquema dentro de um banco. O banco é o
DuckDB: uma biblioteca, não um servidor — sem senha, sem porta, e o banco
inteiro é um arquivo em `dados/ouro/projeto.duckdb`, ignorado pelo Git. A
Prata entra como está, via `read_parquet`; a Ouro nasce dentro do banco,
escrita em SQL — desde a Aula 10, pelo dbt.

### A frase do grão

> **Uma linha de `fato_expectativa` é um país em um ano e um sexo.**
>
> **Uma linha de `fato_contexto` é um país em um ano.**

A primeira frase decide três coisas: a chave primária é `(pais_id, ano, sexo)`
e não `(pais_id, ano)`; somar entre anos do mesmo país não faz sentido; e
duplicata é o mesmo país, no mesmo ano, no mesmo sexo, duas vezes.

A conferência do material — agrupar a fato por país e ano e esperar zero
repetidos — devolveria **3.515** linhas aqui. Não é erro de dado: é a
conferência perguntando o grão errado. 185 países × 19 anos × 3 sexos =
**10.545**, exatamente as linhas da fato.

### O desenho

| Objeto | Tipo | Uma linha é | Linhas |
|---|---|---|---:|
| `ouro.dim_pais` | dimensão | um país | 217 |
| `ouro.fato_expectativa` | fato | um país, um ano, um sexo | 10.545 |
| `ouro.fato_contexto` | fato | um país, um ano | 4.023 |
| `ouro.vw_indicador_completo` | view | um país, um ano, um sexo | 10.545 |

**`dim_pais`** — `pais_id`, `nome`, `regiao_oms`, `regiao`, `nivel_renda`,
`capital`, `longitude`, `latitude`. A região da OMS não está em
`prata.paises`: entra por `DISTINCT` sobre a série, e é 1:1 com o país, então
uma agregação simples resolve. `nome` é o `pais_nome` da prata; o vocabulário
de origem (`region.value`, `incomeLevel.value`) já tinha ficado para trás na
Aula 05.

**`fato_expectativa`** — `pais_id`, `ano`, `sexo`, `expectativa_vida`,
`ic_baixo`, `ic_alto`, `variacao_pct`, `expectativa_vida_faixa`,
`dif_mediana_regiao`.

**`fato_contexto`** — `pais_id`, `ano`, `gasto_saude_pct_pib`,
`gasto_saude_per_capita_usd`, `pib_per_capita_usd`, `escolaridade_anos`,
`escolaridade_anos_faixa`.

### Por que duas fatos, e não uma

A tabela enriquecida mistura dois grãos. `expectativa_vida`, `ic_baixo`,
`ic_alto`, `variacao_pct`, `dif_mediana_regiao` e `expectativa_vida_faixa`
existem por país, ano e sexo. `gasto_saude_pct_pib`,
`gasto_saude_per_capita_usd`, `pib_per_capita_usd` e `escolaridade_anos`
existem por país e ano — nenhum par país-ano tem mais de um valor de gasto.

Numa fato só, a armadilha do grão deixaria de ser um aviso e viraria
estrutura: todo `SUM()` de dinheiro contaria cada país três vezes. Com duas
fatos, cada medida mora no seu grão, e a view remonta a tabela achatada quando
alguém precisar dela.

`fato_contexto` é um `FULL OUTER JOIN` entre gasto e determinantes, e não
`LEFT`: 446 pares país-ano têm só PIB e escolaridade, e 7 têm só gasto.

### O que a carga descarta

| Tabela | Linhas fora da fato | Por quê |
|---|---:|---|
| `gasto_saude` | 38 | Cook Islands e Niue não têm cadastro de país |
| `determinantes` | 0 | todos os países têm cadastro |

O `WHERE` de integridade é o mesmo do material: fica na fato só o que tem
dimensão. Aqui ele custa 38 linhas, e o log avisa. Por isso a soma de
`gasto_saude_per_capita_usd` na fato não fecha com a prata: em 2018 são
US$ 229.185 contra US$ 231.161, e a diferença de US$ 1.976 são exatamente os
dois países.

### A view é a tabela achatada, sem arquivo para manter

`vw_indicador_completo` junta as duas fatos à dimensão e devolve as mesmas 17
colunas e as mesmas 10.545 linhas da tabela enriquecida. A conferência é um
`EXCEPT` nos dois sentidos entre a view e o Parquet: **zero linhas de
diferença**. Corrigir a região de um país é uma linha em `dim_pais`, e a view
já sai certa para todo mundo.

### As provas

| Prova | Resultado |
|---|---:|
| grão de `fato_expectativa` repetido | 0 |
| grão de `fato_contexto` repetido | 0 |
| fatos órfãos (`fato_expectativa` / `fato_contexto`) | 0 / 0 |
| `dim_pais`: linhas / países distintos | 217 / 217 |
| view contra o Parquet | 0 diferenças |

Qualquer uma diferente de zero levanta erro, e o pipeline para.

### A pergunta, em SQL

```sql
SELECT d.nivel_renda, ROUND(AVG(f.expectativa_vida), 1) AS media
FROM ouro.fato_expectativa f
JOIN ouro.dim_pais d USING (pais_id)
WHERE f.ano = 2018 AND f.sexo = 'total'
GROUP BY 1
ORDER BY media DESC;
```

| Nível de renda | Expectativa média em 2018 | Países |
|---|---:|---:|
| High income | 79,4 | 58 |
| Upper middle income | 73,8 | 55 |
| Lower middle income | 67,9 | 47 |
| Low income | 62,8 | 25 |

O `GROUP BY` muda o grão, como o `pct_change` mudou na prata: a fato tinha uma
linha por país, ano e sexo, e a consulta devolve uma linha por nível de renda.


## Construção da Ouro com dbt

Na Aula 09 a Ouro era construída por `construir_ouro()`, com `CREATE TABLE`
dentro de strings do Python. Na Aula 10 esse SQL saiu de dentro do código e
virou **um arquivo por tabela**, em `ecox14/models/`. Quem executa é o dbt.

| O que doía no SQL dentro do Python | O que o dbt faz |
|---|---|
| nenhum editor conferia a sintaxe | o modelo é um `.sql` que o editor entende |
| a ordem `dim` antes das fatos só existia no código | ele deduz a ordem pelas referências |
| refazer uma tabela era rodar tudo | `dbt run --select dim_pais+` roda o pedaço |
| a documentação era comentário solto | ela é gerada do próprio código |

### O que fica em cada lugar

| Arquivo | O que é |
|---|---|
| `ecox14/dbt_project.yml` | nome, pastas e a materialização padrão (`table`) |
| `ecox14/models/sources.yml` | as 5 tabelas da prata: onde o grafo começa |
| `ecox14/models/dim_pais.sql` | a dimensão |
| `ecox14/models/fato_expectativa.sql` | o fato do grão país + ano + sexo |
| `ecox14/models/fato_contexto.sql` | o fato do grão país + ano |
| `ecox14/models/vw_indicador_completo.sql` | a view que remonta a achatada |
| `~/.dbt/profiles.yml` | como conectar no banco (fora do repositório) |

`source()` aponta para tabela que o dbt **não** fez; `ref()` aponta para outro
modelo seu e é o que cria a seta do grafo. As duas fatos usam
`ref('dim_pais')` no filtro de integridade, então o dbt sabe que a dimensão
vem antes — sem ninguém escrever a ordem.

### Tabela ou view

Dimensão e fatos são **tabelas**; só a achatada é **view**. A regra geral fica
no `dbt_project.yml` e a exceção no próprio arquivo:

```sql
{{ config(materialized='view') }}
```

Trocar de um para o outro é mudar uma palavra. Vale saber: o dbt 1.12
materializa **view** por padrão, e foi preciso declarar `table` para a
dimensão e as fatos continuarem como na Aula 09.

### O que mudou no pipeline

`carga.main()` não constrói mais a Ouro: abre o banco, cria os esquemas e
copia a prata. A etapa `modelagem` roda `dbt run` e depois chama
`carga.verificar_banco()` — as mesmas provas da Aula 09.

A ordem importa. Num banco novo, a Ouro não existe quando a carga termina;
por isso a conferência saiu de `carga.main()` e passou para depois do dbt. Do
contrário, o primeiro `python src/pipeline.py` num clone limpo falharia ao
conferir tabelas que ainda não tinham sido criadas — e a mensagem apontaria
para o lugar errado.

Se o dbt falhar, `check=True` levanta erro e o pipeline para. Sem ele, o
Python diria "concluído" com a Ouro quebrada.

### Como rodar

```bash
python src/pipeline.py              # tudo, da API à Ouro
python src/pipeline.py modelagem    # só o dbt e as provas
```

Dentro de `ecox14/`:

```bash
dbt run                     # os quatro modelos, na ordem do grafo
dbt run --select dim_pais+  # a dimensão e tudo que depende dela
dbt debug                   # mostra o perfil e testa a conexão
```

O `dbt` não está no `PATH` nesta máquina; o `pipeline.py` procura o
executável em `Scripts\`, ao lado do `python.exe`.

### A migração não mudou o resultado

| Objeto | Aula 09 (Python) | Aula 10 (dbt) |
|---|---:|---:|
| `dim_pais` | 217 | 217 |
| `fato_expectativa` | 10.545 | 10.545 |
| `fato_contexto` | 4.023 | 4.023 |
| `vw_indicador_completo` | 10.545 | 10.545 |
| view contra o Parquet | 0 diferenças | 0 diferenças |

O teste foi feito com o banco apagado: `carga` recriou o `projeto.duckdb`, o
dbt construiu os quatro modelos e as provas passaram. Trocar a ferramenta sem
mudar o resultado é o objetivo de uma migração.


## O que é herdado e o que é criado

Das 31 colunas das quatro tabelas da prata, **25 vêm da fonte** — renomeadas,
tipadas e filtradas — e **6 são criadas pelo código**. A tabela enriquecida
não traz dado novo: são 17 colunas, das quais 16 já existiam e **uma é nova**,
a `dif_mediana_regiao`, que só existe depois da junção.

Contando nomes distintos, e não a soma das tabelas, a prata tem **21 colunas** —
14 vindas da fonte e **7 criadas** pelo código.

### Criadas por cálculo (atributos derivados)

| Coluna | Tabela | Função | O que é |
|---|---|---|---|
| `variacao_pct` | `expectativa_vida` | `variacao_anual()` | variação % contra o ano anterior, por país e sexo |
| `expectativa_vida_faixa` | `expectativa_vida` | `faixa_por_quartil()` | quartil da expectativa de vida |
| `escolaridade_anos_faixa` | `determinantes` | `faixa_por_quartil()` | quartil da escolaridade |
| `dif_mediana_regiao` | `indicadores_enriquecidos` | `diferenca_mediana_regiao()` | anos acima/abaixo da mediana da região do Banco Mundial, no mesmo ano e sexo |


### Criadas por cruzamento entre fontes

Vêm do `merge` com `paises.parquet`, que a WHO não tem:

| Coluna | Aparece em |
|---|---|
| `pais_nome` | `expectativa_vida`, `gasto_saude`, `determinantes`, `indicadores_enriquecidos` |
| `regiao` | `gasto_saude`, `determinantes`, `indicadores_enriquecidos` |
| `nivel_renda` | `determinantes`, `indicadores_enriquecidos` |

### Recodificadas

| Coluna | Veio de | O que mudou |
|---|---|---|
| `sexo` | `Dim1` (`SEX_MLE`, `SEX_FMLE`, `SEX_BTSX`) | traduzido e tipado como categoria |

### Exemplos de colunas herdadas

| Prata | Bronze | O que mudou |
|---|---|---|
| `expectativa_vida` | `NumericValue` | renomeada (veio de `NumericValue`, não de `Value`, que é texto) |
| `ano` | `TimeDim` | renomeada e tipada como `Int64` |
| `nivel_renda` | `incomeLevel.value` | renomeada e tipada como categoria **ordenada** |

As **7 colunas criadas** são as únicas que desaparecem quando se apaga
`dados/prata/`: são recalculadas do zero pelos scripts que geram a prata.

## Recorte 2000 a 2018

Os dados de escolaridade foram descontinuados em 2019 e sua cobertura cai no
fim: 92 países em 2018, 35 em 2019, 0 em 2020 e 2021. Apesar do `lastupdated`
da fonte indicar 2024, os dados acabam em 2019 — é o último ano com valor, não
a data de atualização, que responde à atualidade.

## Atributos derivados

**`variacao_pct`** — variação percentual contra o ano anterior, por país **e
por sexo**. A chave precisa ter as duas dimensões: agrupar só por país comara um
ano com outro sexo do mesmo ano.

São **dois sexos** — masculino e feminino — mais o **total dos dois**, que a OMS
publica na mesma tabela. Isso dá três linhas por país e ano, e por isso a chave
da variação precisa ter as duas dimensões.

O total não é a média aritmética dos dois sexos: vem da tabela de mortalidade
com os dois juntos. Em 2011 os Emirados Árabes Unidos têm masculino 82,0 e
feminino 82,0 — mesma média — e a OMS publica 81,9, abaixo dos dois. Dos 3.515
pares de país e ano, só 875 coincidem exatamente com a média simples.

| Linha | Primeiro ano | Registros sem variação |
|---|---|---|
| total | 2000 | 185 |
| masculino | 2000 | 185 |
| feminino | 2000 | 185 |

Os 555 ausentes são todos de **2000** — o primeiro ano do recorte não tem ano
anterior. De 2001 a 2018 nenhum registro fica sem valor.

As 39 variações acima de 10% não são erro — são eventos verificáveis:

| País | Ano | Variação | O que aconteceu |
|---|---|---|---|
| Central African Republic | 2009 | **−48,0%** | epidemia de HIV/AIDS e conflito |
| Central African Republic | 2010 | **+89,0%** | reversão do ano de crise |
| Haiti | 2010 | **−34,8%** | terremoto de janeiro de 2010 |
| Haiti | 2011 | **+54,1%** | recuperação do sistema de saúde |
| Somalia, Fed. Rep. | 2011 | **−30,5%** | fome de 2011 |
| Somalia, Fed. Rep. | 2012 | **+43,9%** | fim da fome |

Desvios justificados não se removem, se marcam. Remover essas linhas destruiria
dados reais, de acontecimentos reais.

**`expectativa_vida_faixa`** e **`escolaridade_anos_faixa`** — quartis: o dado é
cortado em 4 faixas do mesmo tamanho, e os pontos de corte são os percentis 25,
50 e 75 da distribuição.

| Expectativa de vida | De | até | Registros |
|---|---|---|---|
| muito baixa | 24,4 | 63,9 | 2.643 |
| baixa | 64,0 | 71,7 | 2.655 |
| alta | 71,8 | 77,1 | 2.669 |
| muito alta | 77,2 | 86,8 | 2.578 |

| Escolaridade esperada | De | até | Registros |
|---|---|---|---|
| muito baixa | 3 | 11 | 515 |
| baixa | 11 | 13 | 515 |
| alta | 13 | 15 | 514 |
| muito alta | 15 | 23 | 515 |

**`dif_mediana_regiao`** — a única coluna que depende da junção para existir. A
conta é `expectativa_vida` menos a mediana da mesma região, ano e sexo. O
detalhamento está na seção de enriquecimento.

## A pergunta responde?

Expectativa de vida média por nível de renda:

| Nível de renda | 2000 | 2018 | Ganho |
|---|---|---|---|
| Low income | 53,2 | 62,6 | **+9,4** |
| Lower middle income | 61,0 | 67,9 | +6,9 |
| Upper middle income | 69,6 | 73,8 | +4,2 |
| High income | 75,7 | 79,4 | **+3,7** |

A ordem só aparece porque a categoria de renda foi declarada **ordenada**.

O padrão do **ganho** é o achado: quanto mais baixa a renda, maior foi o
avanço. A distância entre os extremos era de 22,5 anos e é de 16,8. O PIB
multiplica por 55 entre os extremos, mas a expectativa de vida ganha 17 anos.