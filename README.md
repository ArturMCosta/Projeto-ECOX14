# Life Expectancy — bronze, prata e ouro

**Pergunta norteadora:** por que alguns países vivem mais que outros — e quanto
o nível de renda, a escolaridade e o gasto em saúde explicam essa diferença na
expectativa de vida?

Projeto de engenharia de dados ponta a ponta: coleta de duas APIs públicas,
transformação em camadas bronze, prata e ouro, modelagem em SQL com dbt,
testes, documentação, painel Streamlit e análise quantitativa reproduzível.

## Como rodar

O projeto roda **dentro do `.venv`**. Na primeira vez:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Em cada terminal novo, ative o venv antes de rodar qualquer comando:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell recusar o script por política de execução:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Pipeline completo, de qualquer pasta:

```bash
python src/pipeline.py
```

| Etapa | O que faz |
|---|---|
| `ingestao` | baixa 3 indicadores da OMS e 3 do Banco Mundial |
| `transformacao` | gera as 4 tabelas da prata |
| `enriquecimento` | gera `indicadores_enriquecidos.parquet` |
| `carga` | cria o banco DuckDB com a prata |
| `modelagem` | roda o dbt: 4 modelos da Ouro e 15 testes |

Retomar de uma etapa, sem refazer as anteriores:

```bash
python src/pipeline.py enriquecimento
```

O pipeline produz os dados; painel e análise rodam à parte:

```bash
streamlit run dashboard/painel.py
python src/analise.py
```

`dbt` e a biblioteca Python do DuckDB vêm do `.venv`; o executável
`duckdb.exe` é baixado à parte. Com o venv ativado, os comandos Python ficam
no `PATH`. A documentação do dbt é gerada com `dbt docs generate` e servida
com `dbt docs serve`, dentro de `ecox14/`.

## Fontes e volume

| Fonte | Pacote | Registros |
|---|---|---:|
| WHO Global Health Observatory | `WHOSIS_000001` — expectativa de vida | 11.172 |
| WHO Global Health Observatory | `GHED_CHEGDP_SHA2011` — gasto em saúde % do PIB | 3.824 |
| WHO Global Health Observatory | `GHED_CHE_pc_US_SHA2011` — gasto em saúde por habitante | 3.824 |
| Banco Mundial | `/v2/country` — lista de países | 296 |
| Banco Mundial | `NY.GDP.PCAP.CD` — PIB per capita | 5.054 |
| Banco Mundial | `SE.SCH.LIFE` — escolaridade esperada | 5.168 |

A camada bronze guarda um arquivo por pacote de dados, no formato entregue
pelo servidor: 29.338 registros no total. A WHO devolve apenas o código ISO3
do país; o nome, a região, o nível de renda e as coordenadas vêm do Banco
Mundial.

## Da bronze à prata

| Bronze (JSON) | Registros | → Prata (Parquet) | Registros | Chave |
|---|---:|---|---:|---|
| `expectativa_vida` | 11.172 | `expectativa_vida.parquet` | 10.545 | `pais_id` + `ano` + `sexo` |
| `gasto_saude_pct_pib` + `gasto_saude_per_capita` | 3.824 | `gasto_saude.parquet` | 3.615 | `pais_id` + `ano` |
| `paises` | 296 | `paises.parquet` | 217 | `pais_id` |
| `pib_per_capita` + `escolaridade` | 10.222 | `determinantes_socioeconomicos.parquet` | 4.016 | `pais_id` + `ano` |

Na expectativa de vida, 627 das 11.172 linhas eram grupos de países; no
gasto em saúde, 209 das 3.824. Na lista de países, 79 dos 296 registros
eram agregados.

A quinta tabela não vem de um pacote novo: `indicadores_enriquecidos.parquet`
junta três das anteriores e tem as 10.545 linhas da expectativa de vida, o
grão mais fino, com gasto, PIB, escolaridade, região e nível de renda ao lado.

A expectativa de vida não é "um país por ano": a OMS publica a mesma medida
para homens, mulheres e total.

### Qualidade dos dados

Alertas principais e correções aplicadas:

- Banco Mundial — `paises`: 84 ausentes em capital/coordenadas são agregados;
  regiões e níveis de renda faltantes são os mesmos agregados; nomes de
  região com espaço no fim foram aparados; nível de renda virou categoria
  ordenada.
- Banco Mundial — PIB e escolaridade: colunas constantes ou vazias foram
  removidas; 144 valores ausentes no PIB e 2.214 na escolaridade foram
  mantidos; 107 linhas sem PIB nem escolaridade (territórios) foram removidas.
- WHO: `SpatialDimType` desbalanceado era o sinal do misto país/agregado;
  `Value` trazia texto com intervalo e foi lido de `NumericValue`;
  `TimeDimType` constante confirmou série anual.

Os 39 casos com variação acima de 10% em um ano não são erro: são eventos
reais, como Haiti 2010, República Centro-Africana 2009 e Somália 2011.

### Enriquecimento

A série de expectativa de vida fica sempre à esquerda, porque é o grão mais
fino e a medida que responde à pergunta. As junções são `many_to_one`:

| Junção | Antes | Depois | Sem par |
|---|---:|---:|---:|
| expectativa → `gasto_saude` | 10.545 | 10.545 | 345 |
| expectativa → `determinantes` | 10.545 | 10.545 | 111 |
| expectativa → `paises` | 10.545 | 10.545 | 0 |

Nenhuma linha se perdeu nem se repetiu. As 345 e 111 sem par são lacunas da
fonte.

32 países do cadastro não têm série de expectativa de vida; começando pela
série, eles não entram. É uma decisão registrada, não um acidente.

O atributo `dif_mediana_regiao` só existe depois da junção: anos acima ou
abaixo da mediana da região do Banco Mundial, no mesmo ano e sexo. As maiores
distâncias negativas coincidem com os mesmos eventos da seção anterior.

### A armadilha do grão

As colunas de dinheiro se repetem nas três linhas de sexo do mesmo país e
ano. Na tabela enriquecida, a soma de `gasto_saude_per_capita_usd` em 2018 é
2,58 vezes maior que a soma correta, porque soma cada país três vezes. Para
dinheiro, use `gasto_saude.parquet` ou `determinantes_socioeconomicos.parquet`.

## Modelagem e carga: a camada Ouro

A camada Ouro vive em DuckDB, um banco em arquivo, sem servidor. A Prata entra
como está, via `read_parquet`; a Ouro nasce dentro do banco, escrita em SQL
pelo dbt.

| Objeto | Tipo | Uma linha é | Linhas |
|---|---|---|---:|
| `ouro.dim_pais` | dimensão | um país | 217 |
| `ouro.fato_expectativa` | fato | um país, um ano, um sexo | 10.545 |
| `ouro.fato_contexto` | fato | um país, um ano | 4.023 |
| `ouro.vw_indicador_completo` | view | um país, um ano, um sexo | 10.545 |

A fato de expectativa tem chave `(pais_id, ano, sexo)`; a fato de contexto
tem chave `(pais_id, ano)`. Existem duas fatos porque as medidas têm grãos
diferentes: expectativa, intervalo de confiança, variação e faixa existem por
sexo; PIB, escolaridade e gasto existem por país e ano.

`fato_contexto` é um `FULL OUTER JOIN` entre gasto e determinantes: 430 pares
país-ano têm só PIB e escolaridade, 9 têm só gasto e 16 têm só escolaridade.
A carga descarta 38 linhas de gasto (Cook Islands e Niue, sem cadastro de
país).

A view `vw_indicador_completo` remonta a tabela achatada. A conferência é um
`EXCEPT` nos dois sentidos entre a view e o Parquet: zero diferenças.

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

## Construção da Ouro com dbt

O SQL da Ouro virou um arquivo por tabela em `ecox14/models/`, executado pelo
dbt. Antes, as tabelas eram criadas por `CREATE TABLE` dentro de strings no
Python.

| Antes, no Python | Agora, com o dbt |
|---|---|
| sem editor conferindo sintaxe | modelo `.sql` que o editor entende |
| ordem `dim` antes das fatos só no código | deduz a ordem pelas referências |
| refazer uma tabela era rodar tudo | `dbt run --select dim_pais+` roda o pedaço |
| documentação era comentário solto | gerada do próprio código |

`source()` aponta para tabela que o dbt não fez; `ref()` aponta para outro
modelo seu e cria a seta do grafo. As duas fatos usam `ref('dim_pais')` no
filtro de integridade, então o dbt sabe que a dimensão vem antes.

Dimensão e fatos são tabelas; só a achatada é view. A regra geral fica no
`dbt_project.yml` e a exceção no próprio arquivo:

```sql
{{ config(materialized='view') }}
```

O dbt 1.12 materializa view por padrão; foi preciso declarar `table` para
dimensão e fatos continuarem como antes.

A etapa `modelagem` roda `dbt run`, depois `dbt test` e por fim
`carga.verificar_banco()`. Se o dbt falhar, `check=True` levanta erro e o
pipeline para. A migração não mudou o resultado: 217, 10.545, 4.023 e 10.545
linhas, com zero diferenças entre a view e o Parquet.

## Testes, documentação e o painel

A conferência da Ouro continua em `carga.conferir()`, mas agora as regras
também estão escritas como testes. Em dado, o código pode estar certo e o dado
chegar errado da fonte; um teste automatizado confere isso a cada execução do
pipeline.

O dbt aceita dois tipos. O **teste pronto** é declarado no `schema.yml` e o
dbt escreve a consulta: `unique`, `not_null`, `relationships` e
`accepted_values`. O **teste próprio** é um `.sql` em `ecox14/tests/`, para o
que nenhum teste pronto cobre — no nosso caso, chave composta.

A convenção é ao contrário do que parece: **o teste passa quando devolve zero
linhas**. Ele procura o defeito, e o sucesso é não achar.

### As provas manuais viraram regra

| Conferência anterior | Onde está agora |
|---|---|
| grão país + ano + sexo repetido | `tests/grao_fato_expectativa.sql` |
| grão país + ano repetido | `tests/grao_fato_contexto.sql` |
| fato sem país na dimensão | `relationships` no `schema.yml` |
| país repetido na dimensão | `unique` e `not_null` no `schema.yml` |
| país em duas regiões da OMS | `tests/regiao_oms_unica.sql` |
| view contra o Parquet | continua no `carga.conferir()` |

`unique` não serve para chave composta, porque olha uma coluna só; por isso as
duas fatos precisam do `GROUP BY` escrito à mão.

Ao todo são 15 testes: 3 próprios e 12 declarados. `dbt test` roda na etapa
`modelagem`, com `check=True`: teste que falha interrompe o pipeline.

### Documentação gerada do código

As descrições de cada modelo e de cada coluna estão no `schema.yml`, ao lado
do teste daquela coluna. O dbt gera um site a partir disso:

```bash
cd ecox14
dbt docs generate
dbt docs serve
```

O site mostra o grafo dos modelos, o que cada coluna significa e de onde ela
vem. Não existe texto paralelo para ficar desatualizado.

### O painel é consumidor, não produtor

`dashboard/` fica fora de `src/` de propósito: o painel não é etapa do
pipeline. Ele lê a Ouro e não escreve nada.

| Arquivo | O que é |
|---|---|
| `dashboard/consultas.py` | o SQL de leitura, uma função por pergunta |
| `dashboard/painel.py` | a página principal do app |
| `dashboard/pages/Resultados.py` | a análise da pergunta norteadora |

```bash
streamlit run dashboard/painel.py
```

O app tem duas páginas: `painel` e `Resultados`. Os filtros são as 7 regiões
do Banco Mundial, os 19 anos de 2000 a 2018 e os 3 recortes de sexo.

Três decisões que estão no código:

- `read_only=True` na conexão: o banco recusa escrita e o painel aberto não
  trava o arquivo para o pipeline.
- valor que vem da tela entra como parâmetro (`?`), nunca concatenado — é o
  que evita injeção de SQL.
- o filtro de sexo existe porque a série tem três recortes por país e ano; sem
  ele, o mesmo país seria contado três vezes.

O rodapé diz de onde veio cada número. Proveniência não é enfeite: no momento
em que o número aparece na tela de alguém, ele deixa de ser seu.

## O que é herdado e o que é criado

Das 31 colunas das quatro tabelas da prata, **25 vêm da fonte** — renomeadas,
tipadas e filtradas — e **6 são criadas pelo código**. A tabela enriquecida
não traz dado novo: são 17 colunas, das quais 16 já existiam e **uma é nova**,
a `dif_mediana_regiao`, que só existe depois da junção.

Contando ocorrências nas quatro tabelas são 31 colunas; contando **nomes
distintos**, a prata tem **21 colunas**: 14 vindas da fonte e **7 criadas** pelo
código.

### Criadas por cálculo

| Coluna | Tabela | O que é |
|---|---|---|
| `variacao_pct` | `expectativa_vida` | variação % contra o ano anterior, por país e sexo |
| `expectativa_vida_faixa` | `expectativa_vida` | quartil da expectativa de vida |
| `escolaridade_anos_faixa` | `determinantes` | quartil da escolaridade |
| `dif_mediana_regiao` | `indicadores_enriquecidos` | anos acima/abaixo da mediana da região, no mesmo ano e sexo |

### Criadas por cruzamento entre fontes

Vêm do `merge` com `paises.parquet`, que a WHO não tem: `pais_nome`, `regiao`
e `nivel_renda`.

### Recodificadas

`sexo` veio de `Dim1` (`SEX_MLE`, `SEX_FMLE`, `SEX_BTSX`) e foi traduzido e
tipado como categoria.

### Exemplos de colunas herdadas

| Prata | Bronze | O que mudou |
|---|---|---|
| `expectativa_vida` | `NumericValue` | renomeada |
| `ano` | `TimeDim` | renomeada e tipada como `Int64` |
| `nivel_renda` | `incomeLevel.value` | renomeada e tipada como categoria ordenada |

As 7 colunas criadas são as únicas que desaparecem quando se apaga
`dados/prata/`: são recalculadas do zero pelos scripts que geram a prata.

## Recorte 2000 a 2018

Os dados de escolaridade foram descontinuados em 2019 e sua cobertura cai no
fim: 92 países em 2018, 35 em 2019, 0 em 2020 e 2021. Apesar do
`lastupdated` da fonte indicar 2024, os dados acabam em 2019 — é o último ano
com valor, não a data de atualização, que responde à atualidade.

## Atributos derivados

`variacao_pct` é a variação percentual contra o ano anterior, por país e por
sexo. São dois sexos — masculino e feminino — mais o total dos dois, que a
OMS publica na mesma tabela. Isso dá três linhas por país e ano, e por isso a
chave da variação precisa ter as duas dimensões.

O total não é a média aritmética dos dois sexos: vem da tabela de mortalidade
com os dois juntos. Em 2011 os Emirados Árabes Unidos têm masculino 82,0 e
feminino 82,0 — mesma média — e a OMS publica 81,9, abaixo dos dois. Dos
3.515 pares de país e ano, só 875 coincidem exatamente com a média simples.

Os 555 registros sem variação são todos de 2000 — o primeiro ano do recorte
não tem ano anterior. De 2001 a 2018 nenhum registro fica sem valor.

Os 39 desvios grandes já foram explicados em **Qualidade dos dados**: são
eventos reais e, por isso, foram marcados em vez de removidos.

`expectativa_vida_faixa` e `escolaridade_anos_faixa` são quartis: o dado é
cortado em 4 faixas do mesmo tamanho, com pontos de corte nos percentis 25,
50 e 75.

`dif_mediana_regiao` é a única coluna que depende da junção para existir: a
conta é expectativa de vida menos a mediana da mesma região, ano e sexo.

## A pergunta tem resposta?

A pergunta tem duas partes: por que alguns países vivem mais que outros, e
quanto renda, escolaridade e gasto em saúde explicam. A primeira os dados
descrevem; a segunda exige um modelo. Tudo abaixo usa o recorte de sexo
**total** — usar os três contaria cada país três vezes.

### O gradiente de renda

Expectativa de vida média por nível de renda:

| Nível de renda | 2000 | 2018 | Ganho |
|---|---:|---:|---:|
| Low income | 53,6 | 62,8 | +9,2 |
| Lower middle income | 61,0 | 67,9 | +6,9 |
| Upper middle income | 69,6 | 73,8 | +4,2 |
| High income | 75,7 | 79,4 | +3,7 |

A ordem só aparece porque a categoria de renda foi declarada ordenada.

O padrão do **ganho** é o achado: quanto mais baixa a renda, maior foi o
avanço. A distância entre os extremos era de 22,1 anos e é de 16,6. O PIB
multiplica por 55 entre os extremos, mas a expectativa de vida ganha cerca de
16 anos — a relação é logarítmica, não linear.

### Quanto cada fator explica

Método: mínimos quadrados sobre a view da Ouro — a linha que mais se aproxima
dos pontos — com `sexo = 'total'`, PIB per capita em escala log (cada 10 vezes
de renda é uma unidade), erro-padrão agrupado por país e, no painel, efeito
fixo de ano. O R² mede o quanto o modelo melhora o palpite em relação a chutar
a média: vai de 0 a 1, e 0,70 quer dizer 70%. Foi escolhido porque a pergunta
pede uma porcentagem de explicação; os coeficientes mostram o tamanho do efeito.
O modelo é leitura da Ouro, não etapa do pipeline: `python src/analise.py`
imprime as tabelas abaixo e a página **Resultados** do painel mostra as mesmas.
Nessa página é possível escolher o ano do corte entre países; os modelos de
painel e dentro do país continuam fixos, porque usam todos os anos de uma vez.
Escolaridade e gasto limitam a amostra: 92 países têm escolaridade em 2018 na
prata, 87 entre os com expectativa de vida, e 86 têm expectativa, PIB,
escolaridade e gasto.

**Entre países, em 2018.**

| Modelo | Países | R² |
|---|---:|---:|
| Renda | 182 | 0,690 |
| Renda, só os casos completos | 86 | 0,767 |
| Renda + escolaridade | 86 | 0,784 |
| Renda + escolaridade + gasto (% do PIB) | 86 | 0,785 |

A primeira linha usa o maior recorte possível: 182 países têm expectativa e
PIB, mas só 86 têm também escolaridade e gasto. As três linhas seguintes usam
sempre esses 86, para que a diferença de R² venha das variáveis, não da amostra.
Por isso a base justa para medir a escolaridade é 0,767, e não 0,690.

**No painel, 2000 a 2018** — 1.922 pares país-ano, de 169 países:

| Modelo | R² |
|---|---:|
| Renda | 0,704 |
| Renda + escolaridade | 0,736 |
| Renda + escolaridade + gasto (% do PIB) | 0,736 |

**Dentro do país** — os mesmos 1.922 pares, com efeito fixo de país e de ano,
o que usa só a variação de cada país contra ele mesmo. Em vez de perguntar se
um país rico vive mais que um pobre, a conta pergunta se um país vive mais
quando ele próprio fica mais rico:

| Modelo | R² |
|---|---:|
| Renda | 0,608 |
| Renda + escolaridade | 0,629 |
| Renda + escolaridade + gasto (% do PIB) | 0,629 |

Coeficientes do modelo completo:

| Variável | Entre países (2018) | Painel com ano | Dentro do país |
|---|---:|---:|---:|
| PIB per capita, por 10× | +6,2 anos | +6,4 anos | +2,3 anos |
| Escolaridade, por ano | +0,40 | +0,85 | +0,42 |
| Gasto saúde, por ponto do PIB | +0,07 (n.s.) | 0,00 (n.s.) | -0,04 (n.s.) |

n.s. = não significativo a 5%.

### O que os números dizem

- **Quem vive mais, em média, são os países com maior renda.** Com os 182
  países de 2018, a renda sozinha acompanha 69% da variação; nos 86 países com
  todos os dados, 76,7%. Com os controles, dez vezes mais renda vale 6,2 anos
  entre países e 2,3 dentro do país.
- **A escolaridade ajuda um pouco.** Nos mesmos 86 países, o R² sai de 0,767
  para 0,784 em 2018. Um ano a mais de escolaridade aparece com 0,4 a 0,85
  ano a mais de expectativa.
- **O gasto em saúde não muda esse resultado.** Sozinho ele até se parece com
  a expectativa, mas quando renda e escolaridade entram o coeficiente vai a
  zero. Gasto per capita dá o mesmo e é quase colinear com o PIB (r ≈ 0,9).
- **Entre e dentro são respostas diferentes.** Um país dez vezes mais rico tem
  6,2 anos a mais que outro; um país que ficou dez vezes mais rico no período
  ganha 2,3. O resto da vantagem dos ricos não é renda: é o que o efeito fixo
  de país captura — história, sistema de saúde, ambiente — e este dado não
  abre essa caixa.

### O que o dado não permite dizer

- **Associação, não causalidade.** Renda, escolaridade e gasto andam juntos; o
  modelo mede o quanto a variação de um acompanha a do outro, não o efeito de
  mudar um deles.
- **Médias de país, não pessoas.** Nada aqui diz sobre um indivíduo: a relação
  entre países pode não valer dentro deles.
- **O painel é desbalanceado.** São 1.922 dos 3.515 pares possíveis; só 33 dos
  169 países têm os 19 anos completos. Quem entra é quem tem escolaridade
  medida, e isso não é aleatório.
- **A escolaridade acaba em 2019 e cai no fim do recorte:** 107 países em
  2002, 92 em 2018 na prata e 87 entre os 185 com expectativa de vida. Por
  isso o modelo de 2018 usa 86 países, e não os 182 com PIB.

## Reprodutibilidade

```bash
python src/pipeline.py
streamlit run dashboard/painel.py
python src/analise.py
```

Os dados ficam fora do Git. O pipeline reconstrói a base a partir das APIs e o
`dbt test` valida a Ouro. `duckdb.exe` é baixado à parte e está no
`.gitignore`.