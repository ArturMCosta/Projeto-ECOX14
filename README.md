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

A exploração vem antes da transformação porque **não se limpa antes de saber o
que está errado**.

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
| `Value` traz `'53.8 [52.8-54.9]'` | número lido de `NumericValue`; nenhuma conversão comeu dado |
| `Dim1`, `Low`, `High` com 40,6% ausentes | são exclusivos do indicador de expectativa de vida |
| `TimeDimType` constante `"YEAR"` | confirma série anual: ano em inteiro, não em data |
| `NumericValue` com valores únicos | cada linha é uma medida própria |
| 14 alertas de correlação alta | `TimeDim`, `TimeDimensionValue`, `Begin` e `End` dizem a mesma coisa |
| não vem o nome do país | cruzamento com o dicionário do Banco Mundial, sem perder linha |

## O que cada arquivo virou

| Bronze (CSV) | Registros | → Prata (Parquet) | Registros |
|---|---|---|---|
| `indicadores` · `WHOSIS_000001` | 11.172 | `expectativa_vida.parquet` | 10.545 |
| `indicadores` · os dois de gasto | 3.824 | `gasto_saude.parquet` | 3.615 |
| `paises` | 295 | `paises.parquet` | 217 |
| `pib_per_capita` | 5.035 | `determinantes_socioeconomicos.parquet` | 4.016 |
| `escolaridade` | 5.168 | ↑ mesma tabela | |

Um CSV pode virar duas tabelas (separado por `IndicatorCode`) e dois CSVs podem
virar uma tabela só (junção por país e ano).

## Chaves

| Tabela | Chave |
|---|---|
| `paises` | `pais_id` |
| `expectativa_vida` | `pais_id` + `ano` + `sexo` |
| `gasto_saude` | `pais_id` + `ano` |
| `determinantes_socioeconomicos` | `pais_id` + `ano` |

A expectativa de vida **não** é "um país por ano": a WHO publica a mesma
medida para homens, mulheres e total na mesma tabela.

## Recorte 2000 a 2018

A escolaridade foi descontinuada em 2019 e sua cobertura cai no fim: 92 países
em 2018, 35 em 2019, **zero em 2020 e 2021**. Com o recorte anterior o projeto
carregava três anos vazios, e nenhum script avisava.

Atenção ao `lastupdated`: a escolaridade marca 2024, mas o dado acaba em 2019.
Quem responde à atualidade é o **último ano com valor**.

## Atributos derivados

`variacao_pct` (contra o ano anterior, por país e sexo), `expectativa_vida_faixa`
e `escolaridade_anos_faixa` (quartis).

As 519 variações acima de 10% **não são erro**: Haiti em 2011 (+67,0%, após o
terremoto), Somália em 2012 (+20,3%, fim da fome),Síria em 2015–2017 (−15,3% a
+14,6%, guerra civil). Extremo legítimo se marca, não se remove.

## Git

Sobe o `src/`, o `README.md`, o `requirements.txt`, a bronze e a
proveniência. Não sobe a prata nem os relatórios — um comando refaz.

**Nota:** `explorar.py` depende do `scipy`. Se o Windows bloquear a biblioteca,
desativar em **Configurações → Segurança do Windows → Controle de Aplicativo
Inteligente**.