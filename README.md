# Life Expectancy — bronze e prata

**Pergunta norteadora:** por que alguns países vivem mais que outros — quanto
o nível de renda, a escolaridade e o gasto em saúde explicam da expectativa
de vida?

## Como rodar

```
pip install -r requirements.txt

python src/ingerir_who_gho.py
python src/ingerir_banco_mundial.py

python src/explorar.py banco_mundial paises_*.json
python src/explorar.py banco_mundial pib_per_capita_*.json
python src/explorar.py banco_mundial escolaridade_*.json
python src/explorar.py who_gho expectativa_vida_*.json
python src/explorar.py who_gho gasto_saude_pct_pib_*.json
python src/explorar.py who_gho gasto_saude_per_capita_*.json

python src/transformar_paises.py
python src/transformar_expectativa_vida.py
python src/transformar_gasto_saude.py
python src/transformar_determinantes.py
```

A exploração vem antes da transformação porque **não se limpa antes de saber o
que está errado**. Cada script de transformação lê um pacote por vez.

## Fontes

| Fonte | Pacote | Formato | Registros |
|---|---|---|---|
| WHO Global Health Observatory | `WHOSIS_000001` expectativa de vida | JSON | 11.172 |
| WHO Global Health Observatory | `GHED_CHEGDP_SHA2011` gasto em saúde % do PIB | JSON | 3.824 |
| WHO Global Health Observatory | `GHED_CHE_pc_US_SHA2011` gasto em saúde por habitante | JSON | 3.824 |
| Banco Mundial | `/v2/country` lista de países | JSON | 296 |
| Banco Mundial | `NY.GDP.PCAP.CD` PIB per capita | JSON | 5.054 |
| Banco Mundial | `SE.SCH.LIFE` escolaridade esperada | JSON | 5.168 |

A bronze guarda **um arquivo por pacote de dados, no formato que o servidor
entregou** — 29.338 registros no total. Converter formato é transformação, e
isso pertence à camada seguinte.

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
| `unit` e `obs_status` 100% vazias | removidas depois de contadas |
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

Na expectativa de vida, 627 das 11.172 linhas eram grupos de países; no
gasto em saúde, 209 das 3.824. Na lista de países, 79 dos 296 registros eram
agregados.
| `paises` | 296 | `paises.parquet` | 217 | `pais_id` |
| `pib_per_capita` + `escolaridade` | 10.222 | `determinantes_socioeconomicos.parquet` | 4.016 | `pais_id` + `ano` |

A expectativa de vida **não** é "um país por ano": a WHO publica a mesma
medida para homens, mulheres e total, na mesma tabela.

Um pacote pode virar uma tabela com dois pacotes (junção por país e ano), e um
mesmo pacote pode alimentar mais de uma tabela.

## Chaves

| Tabela | Chave |
|---|---|
| `paises` | `pais_id` |
| `expectativa_vida` | `pais_id` + `ano` + `sexo` |
| `gasto_saude` | `pais_id` + `ano` |
| `determinantes_socioeconomicos` | `pais_id` + `ano` |

## O que é herdado e o que é criado

Das 31 colunas da prata, **25 vêm da fonte** — renomeadas, tipadas e
filtradas. As outras **6 são criadas pelo código**.

### Criadas por cálculo (atributos derivados)

| Coluna | Tabela | Função | O que é |
|---|---|---|---|
| `variacao_pct` | `expectativa_vida` | `variacao_anual()` | variação % contra o ano anterior, por país e sexo |
| `expectativa_vida_faixa` | `expectativa_vida` | `faixa_por_quartil()` | quartil da expectativa de vida |
| `escolaridade_anos_faixa` | `determinantes` | `faixa_por_quartil()` | quartil da escolaridade |

Detalhes e cortes destas 3 colunas em [Atributos derivados](#atributos-derivados).

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

As 3 colunas derivadas são as únicas que desaparecem quando se apaga
`dados/prata/`: são recalculadas do zero pelo `limpeza.py`.

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

## Git

Sobe o `src/`, o `README.md`, o `requirements.txt`, a bronze e a
proveniência. Não sobe a prata nem os relatórios — um comando refaz.

**Nota:** `explorar.py` depende do `scipy`. Se o Windows bloquear a biblioteca,
desativar em **Configurações → Segurança do Windows → Controle de Aplicativo
Inteligente**.