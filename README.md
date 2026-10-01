# Life Expectancy — bronze e prata

**Pergunta norteadora:** por que alguns países vivem mais que outros — quanto
o nível de renda, a escolaridade e o gasto em saúde explicam da expectativa
de vida?

## Fontes

| Fonte | Recurso | Registros |
|---|---|---|
| WHO Global Health Observatory | `WHOSIS_000001` expectativa de vida<br>`GHED_CHEGDP_SHA2011` gasto em saúde % do PIB<br>`GHED_CHE_pc_US_SHA2011` gasto em saúde por habitante | 18.820 |
| Banco Mundial | `NY.GDP.PCAP.CD` PIB per capita<br>`SE.SCH.LIFE` escolaridade | 10.203 |
| Banco Mundial | `/v2/country` — lista de países | 295 |

O `/v2/country` não é uma série temporal: é apenas um dicionário com nome, região,
nível de renda e coordenadas. A WHO devolve só o código ISO3 do país, então é
ele que dá nome aos registros das outras três séries.

## O que os relatórios alertaram

### Banco Mundial — `paises`

| Alerta | Correção |
|---|---|
| `id`, `name` com valores únicos | chave confirmada: `pais_id` |
| `capitalCity`, `longitude`, `latitude` com 84 ausentes (28,5%) | são os 78 agregados; capital vazia em agrupamento não se aplica |
| `region.*`, `incomeLevel.*`, `lendingType.*` com 78 ausentes (26,4%) | os mesmos agregados, separados na entrada da prata |
| 12 alertas de correlação alta | `id`, `iso2code` e `value` se repetem em cada bloco; só o `value` foi mantido |
| nomes de região com espaço no fim | `tirar_espacos()` |
| nível de renda como texto livre | `tipar_categoria()` com a ordem `Low` → `Lower middle` → `Upper middle` → `High` |

### Banco Mundial — `pib_per_capita` e `escolaridade`

| Alerta | Correção |
|---|---|
| `unit` e `obs_status` 100% vazias | removidas depois de contadas |
| `indicator.id`, `indicator.value`, `decimal` constantes | informação repetida em todas as linhas, não guardada |
| `value` com 144 ausentes (2,9%) no PIB | mantidos |
| `value` com **2.214 ausentes (42,8%)** na escolaridade | motivo de o recorte ir só até 2018 |
| `countryiso3code` com 95 e 266 ausentes | linhas de agregado sem código de país de verdade, separadas |
| 107 linhas sem PIB e sem escolaridade | territórios sem economia registrada (Gibraltar, Ilhas Cayman…), removidas |

### WHO — `indicadores`

| Alerta | Correção |
|---|---|
| `SpatialDimType` desbalanceado (80,9%) | **é o sinal do misto país/agregado**: separados pela própria coluna que declara o que cada registro é |
| `Value` traz `'53.8 [52.8-54.9]'` | número lido de `NumericValue`; nenhuma conversão perdeu dado |
| `Dim1`, `Low`, `High` com 40,6% ausentes | são os 7.648 registros dos dois indicadores de gasto, que não têm sexo nem intervalo de confiança |
| `TimeDimType` constante `"YEAR"` | confirma série anual: ano em inteiro, não em data |
| `NumericValue` com valores únicos | cada linha é uma medida própria |
| 14 alertas de correlação alta | `TimeDim`, `TimeDimensionValue`, `Begin` e `End` dizem a mesma coisa |
| não vem o nome do país | cruzamento com o dicionário do Banco Mundial, sem perder linha |

## O que cada arquivo virou

| Bronze (CSV) | Registros | → Prata (Parquet) | Registros | Chave |
|---|---|---|---|---|
| `indicadores` · `WHOSIS_000001` | 11.172 | `expectativa_vida.parquet` | 10.545 | `pais_id` + `ano` + `sexo` |
| `indicadores` · os dois de gasto | 3.824 | `gasto_saude.parquet` | 3.615 | `pais_id` + `ano` |
| `paises` | 295 | `paises.parquet` | 217 | `pais_id` |
| `pib_per_capita` | 5.035 | `determinantes_socioeconomicos.parquet` | 4.016 | `pais_id` + `ano` |
| `escolaridade` | 5.168 | ↑ mesma tabela | | |

A expectativa de vida não é "um país por ano": a WHO publica a mesma
medida para homens, mulheres e total, na mesma tabela.

## O que é herdado e o que é criado

Das 31 colunas da prata, 25 vêm da fonte — renomeadas, tipadas e
filtradas. As outras 6 são criadas pelo código.

### Criadas por cálculo (atributos derivados)

| Coluna | Tabela | Função | O que é |
|---|---|---|---|
| `variacao_pct` | `expectativa_vida` | `variacao_anual()` | variação % contra o ano anterior, por país e sexo |
| `expectativa_vida_faixa` | `expectativa_vida` | `faixa_por_quartil()` | quartil da expectativa de vida |
| `escolaridade_anos_faixa` | `determinantes` | `faixa_por_quartil()` | quartil da escolaridade |


### Criadas por cruzamento entre fontes

Vêm do `merge` com `paises.parquet`, que a WHO não tem:

| Coluna | Aparece em |
|---|---|
| `pais_nome` | `expectativa_vida`, `gasto_saude`, `determinantes` |
| `regiao` | `gasto_saude`, `determinantes` |
| `nivel_renda` | `determinantes` |

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


## Recorte 2000 a 2018

Os dados de escolaridade foram descontinuados em 2019 e sua cobertura cai no fim: 92 países
em 2018, 35 em 2019, 0 em 2020 e 2021.
Apesar do `lastupdated` da fonte indicar 2024, os dados acabam em 2019.

## Atributos derivados

**`variacao_pct`** — variação percentual contra o ano anterior, por país **e
por sexo**.

As 23 variações acima de 10% em suma não são erros — sendo possivelmente eventos verificáveis:

| País | Ano | Variação | O que aconteceu |
|---|---|---|---|
| Haiti | 2010 | **−34,2%** | terremoto de janeiro de 2010 |
| Haiti | 2011 | **+52,9%** | recuperação do sistema de saúde |
| Somalia, Fed. Rep. | 2011 | −11,5% | fome de 2011 |
| Somalia, Fed. Rep. | 2012 | +14,4% | fim da fome |
| Syrian Arab Republic | 2012 | −9,6% | guerra civil |
| Myanmar | 2008 / 2009 | −9,3% / +12,4% | ciclo político de 2008 |

Desvios justificados não se removem, se marcam. Remover essas linhas destruiria dados
reais, de acontecimentos reais.

**`expectativa_vida_faixa`** e **`escolaridade_anos_faixa`** — quartis: o dado é
cortado em 4 faixas do mesmo tamanho, e os pontos de corte são os percentis
25, 50 e 75 da própria distribuição.

| Expectativa de vida | De | até | Registros |
|---|---|---|---|
| muito baixa | 36,6 | 63,6 | 2.637 |
| baixa | 63,6 | 71,7 | 2.636 |
| alta | 71,7 | 77,0 | 2.636 |
| muito alta | 77,0 | 87,1 | 2.636 |

| Escolaridade esperada | De | até | Registros |
|---|---|---|---|
| muito baixa | 3 | 11 | 515 |
| baixa | 11 | 13 | 515 |
| alta | 13 | 15 | 514 |
| muito alta | 15 | 23 | 515 |
