# Life Expectancy — bronze e prata

**Pergunta norteadora:** por que alguns países vivem mais que outros — quanto
o nível de renda, a escolaridade e o gasto em saúde explicam da expectativa
de vida?

## Como rodar

```
pip install -r requirements.txt

python src/ingerir_who_gho.py
python src/ingerir_banco_mundial.py

python src/explorar.py banco_mundial paises_*.csv
python src/explorar.py banco_mundial pib_per_capita_*.csv
python src/explorar.py banco_mundial escolaridade_*.csv
python src/explorar.py who_gho indicadores_*.csv

python src/transformar_paises.py
python src/transformar_expectativa_vida.py
python src/transformar_gasto_saude.py
python src/transformar_determinantes.py
```

## Fontes

| Fonte | Indicadores |
|---|---|
| WHO Global Health Observatory | `WHOSIS_000001` expectativa de vida<br>`GHED_CHEGDP_SHA2011` gasto em saúde % do PIB<br>`GHED_CHE_pc_US_SHA2011` gasto em saúde por habitante |
| Banco Mundial | `NY.GDP.PCAP.CD` PIB per capita<br>`SE.SCH.LIFE` escolaridade |

## O que os relatórios alertaram

Alertas da seção **Alerts** de cada relatório, e a correção aplicada.

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
| `Value` traz `'53.8 [52.8-54.9]'` | número lido de `NumericValue`; em nenhuma conversão se perdeu dados |
| `Dim1`, `Low`, `High` com 40,6% ausentes | são os 7.648 registros dos dois indicadores de gasto, que não têm sexo nem intervalo de confiança |
| `TimeDimType` constante `"YEAR"` | confirma série anual: ano em inteiro, não em data |
| `NumericValue` com valores únicos | cada linha é uma medida própria |
| 14 alertas de correlação alta | `TimeDim`, `TimeDimensionValue`, `Begin` e `End` dizem a mesma coisa |
| não vem o nome do país | cruzamento com o dicionário do Banco Mundial, sem perder linha |

## O que cada arquivo virou

| Bronze (CSV) | Registros | → Prata (Parquet) | Registros |
|---|---|---|---|
| `indicadores` · `WHOSIS_000001` | 11.172 | `expectativa_vida.parquet` | 10.545 |
| `indicadores` · `GHED_CHEGDP_SHA2011` e `GHED_CHE_pc_US_SHA2011` | 3.824 | `gasto_saude.parquet` | 3.615 |
| `paises` | 295 | `paises.parquet` | 217 |
| `pib_per_capita` | 5.035 | `determinantes_socioeconomicos.parquet` | 4.016 |
| `escolaridade` | 5.168 | `determinantes_socioeconomicos.parquet` | |

## Chaves

| Tabela | Chave |
|---|---|
| `paises` | `pais_id` |
| `expectativa_vida` | `pais_id` + `ano` + `sexo` |
| `gasto_saude` | `pais_id` + `ano` |
| `determinantes_socioeconomicos` | `pais_id` + `ano` |

A expectativa de vida **não** é dado por "um país por ano": a WHO publica a mesma
medida separada para homens, mulheres e total, na mesma tabela.

## Recorte 2000 a 2018

A escolaridade foi descontinuada em 2019 e sua cobertura cai no fim: 92 países
em 2018, 35 em 2019, 0 em 2020 e 2021.
Atenção ao `lastupdated` da fonte: a escolaridade marca 2024, mas o dado acaba em 2019.

## Atributos derivados

**`variacao_pct`** — variação percentual contra o ano anterior, por país **e
por sexo**. Os 555 ausentes são os primeiros anos: 185 países × 3 sexos.

A chave precisa ter as duas dimensões. Agrupar só por país comara um ano com
outro sexo do mesmo ano, porque as linhas alternam de sexo dentro do ano.

As 23 variações acima de 10% não são erro — são eventos verificáveis:

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
cortado em 4 faixas do mesmo tamanho, e os pontos de corte são os percentis 25,
50 e 75 da própria distribuição.

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
