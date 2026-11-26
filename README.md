# Life Expectancy — bronze, prata e ouro

**Pergunta norteadora:** por que alguns países vivem mais que outros — e quanto
o nível de renda, a escolaridade e o gasto em saúde explicam da expectativa de
vida?

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

`dbt` e `duckdb` vêm do `.venv`; com o venv ativado eles ficam no `PATH`.
A documentação do dbt é gerada com `dbt docs generate` e servida com
`dbt docs serve`, dentro de `ecox14/`.

## Arquitetura

| Camada | Formato | Registros | Grão |
|---|---|---:|---|
| Bronze | JSON | 29.338 | pacote bruto da API |
| Prata | Parquet | 10.545 expectativa; 4.016 determinantes; 3.615 gasto; 217 países | país + ano (+ sexo na expectativa) |
| Ouro | DuckDB | `dim_pais` 217; `fato_expectativa` 10.545; `fato_contexto` 4.023; `vw_indicador_completo` 10.545 | país; país + ano + sexo; país + ano; país + ano + sexo |

A camada Ouro tem duas tabelas fato porque as medidas têm grãos diferentes:
`fato_expectativa` guarda medidas por sexo e `fato_contexto` guarda PIB,
escolaridade e gasto por país e ano. A view `vw_indicador_completo` remonta a
tabela achatada para consulta.

`fato_contexto` é um `FULL OUTER JOIN` entre gasto e determinantes: 430 pares
país-ano têm só PIB e escolaridade, 9 têm só gasto e 16 têm só escolaridade.

## dbt, testes e documentação

O SQL da Ouro está em `ecox14/models/`. O dbt deduz a ordem pelas
referências `source()` e `ref()`, roda os modelos e os testes.

| Objeto | Quantidade |
|---|---:|
| Modelos | 4 |
| Sources | 5 |
| Testes | 15 (3 próprios + 12 declarados em `schema.yml`) |

Testes próprios: grão de `fato_expectativa`, grão de `fato_contexto` e região
da OMS única por país. Testes declarados: `not_null`, `unique`,
`relationships` e `accepted_values`.

A documentação fica em `ecox14/models/schema.yml` e é gerada com
`dbt docs generate`. Os artefatos ficam em `ecox14/target/`, fora do Git.

## Painel e análise

O painel Streamlit fica em `dashboard/` e é consumidor da Ouro, não etapa do
pipeline. Ele tem duas páginas:

- `painel`: filtros por região, ano e sexo.
- `Resultados`: a análise da pergunta norteadora.

`dashboard/consultas.py` concentra o SQL de leitura. A conexão usa
`read_only=True` e os filtros entram como parâmetros.

A análise quantitativa roda com:

```bash
python src/analise.py
```

Ela lê `ouro.vw_indicador_completo`, usa `sexo = 'total'`, PIB per capita em
log10, regressão OLS e erro-padrão agrupado por país. A página `Resultados`
usa a mesma função.

## Resultado da análise

Amostra: 182 países em 2018; 1.922 pares país-ano no painel 2000-2018.

| Modelo | R² entre países (2018) | R² no painel | R² dentro do país |
|---|---:|---:|---:|
| Renda sozinha | 0,690 | 0,704 | 0,608 |
| Renda + escolaridade | 0,784 | 0,736 | 0,629 |
| Renda + escolaridade + gasto (% do PIB) | 0,785 | 0,736 | 0,629 |

Coeficientes do modelo completo:

| Variável | Entre países (2018) | Painel | Dentro do país |
|---|---:|---:|---:|
| PIB per capita, por 10× | +6,2 anos | +6,4 anos | +2,3 anos |
| Escolaridade, por ano | +0,40 | +0,85 | +0,42 |
| Gasto em saúde, por ponto do PIB | +0,07 (n.s.) | 0,00 (n.s.) | -0,04 (n.s.) |

n.s. = não significativo a 5%.

Leitura: a renda explica a maior parte; a escolaridade acrescenta pouco; o
gasto em saúde não acrescenta nada depois dos outros dois. Gasto per capita é
quase colinear com o PIB (r ≈ 0,9).

## Limitações

- Associação, não causalidade.
- Médias de país, não pessoas.
- Painel desbalanceado: 1.922 dos 3.515 pares possíveis; 33 dos 169 países têm
  os 19 anos completos.
- Escolaridade termina em 2019; o modelo de 2018 usa 86 países.

## Reprodutibilidade

```bash
python src/pipeline.py
streamlit run dashboard/painel.py
python src/analise.py
```

Os dados ficam fora do Git. O pipeline reconstrói a base a partir das APIs e o
`dbt test` valida a Ouro. `duckdb.exe` é baixado à parte e está no
`.gitignore`.