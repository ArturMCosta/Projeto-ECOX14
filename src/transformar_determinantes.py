import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/banco_mundial")
PRATA = Path("dados/prata")

SERIES = {
    "pib_per_capita_*.csv": "pib_per_capita_usd",
    "escolaridade_*.csv": "escolaridade_anos",
}

COLUNAS_VAZIAS = ["unit", "obs_status", "decimal"]

FAIXA_ESCOLARIDADE = ["muito baixa", "baixa", "alta", "muito alta"]

COLUNAS = ["pais_id", "pais_nome", "regiao", "nivel_renda", "ano",
           "pib_per_capita_usd", "escolaridade_anos", "escolaridade_anos_faixa"]


def carregar(prefixo):
    arquivos = sorted(BRONZE.glob(prefixo))
    if not arquivos:
        raise FileNotFoundError(f"nada com o padrao {prefixo} em {BRONZE}")
    caminho = arquivos[-1]
    df = pd.read_csv(caminho)
    print("lido:", caminho.name, df.shape)
    return df, caminho


def tirar_colunas_vazias(df):
    vazias = [c for c in COLUNAS_VAZIAS if df[c].isna().all()]
    print("colunas vazias:", vazias)
    return df.drop(columns=vazias)


def separar_agregados(df):
    paises = pd.read_csv(sorted(BRONZE.glob("paises_*.csv"))[-1])
    e_pais = paises["region.value"] != "Aggregates"
    validos = set(paises.loc[e_pais, "id"])
    print("paises   :", len(validos))
    print("agregados:", (~e_pais).sum())

    antes = len(df)
    df = df[df["countryiso3code"].isin(validos)].copy()
    print("linhas antes:", antes, "depois:", len(df))
    return df


def conferir_chave(df, chave=["pais_id", "ano"]):
    repetidas = df.duplicated(subset=chave).sum()
    print("chaves repetidas:", repetidas)
    return df.drop_duplicates(subset=chave)


def preparar(prefixo, coluna):
    df, _ = carregar(prefixo)
    df["ano"] = pd.to_numeric(df["date"], errors="coerce").astype("Int64")
    df = tirar_colunas_vazias(df)
    df = separar_agregados(df)
    df = df.rename(columns={"countryiso3code": "pais_id", "value": coluna})
    df = limpeza.tipar_numero(df, [coluna])
    return conferir_chave(df)[["pais_id", "ano", coluna]]


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "determinantes_socioeconomicos.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def registrar(destino, antes, depois, decisoes):
    info = {
        "origem": "pib_per_capita + escolaridade (Banco Mundial)",
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": depois,
        "decisoes": decisoes,
        "transformado_em": datetime.now().isoformat(timespec="seconds"),
    }
    PRATA.mkdir(parents=True, exist_ok=True)
    with (PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    antes = 0
    df = None
    for prefixo, coluna in SERIES.items():
        parte = preparar(prefixo, coluna)
        antes += len(parte)
        if df is None:
            df = parte
        else:
            df = df.merge(parte, on=["pais_id", "ano"], how="outer")

    df = limpeza.cruzar_com_paises(df, PRATA, ["pais_nome", "regiao", "nivel_renda"])
    df = limpeza.remover_vazias(df, ["pib_per_capita_usd", "escolaridade_anos"])
    df = limpeza.faixa_por_quartil(df, "escolaridade_anos", FAIXA_ESCOLARIDADE)

    destino = salvar(df[COLUNAS])
    registrar(destino, antes, len(df), [
        "ano convertido para inteiro, nao para data",
        "colunas vazias unit, obs_status e decimal removidas depois de contadas",
        "agregados regionais separados: nao sao pais",
        "pib e escolaridade juntos por pais e ano",
        "linhas sem PIB e sem escolaridade removidas: territorio sem economia registrada",
        "nome, regiao e nivel de renda cruzados com o dicionario de paises",
        "derivado: escolaridade_anos_faixa por quartil",
    ])


if __name__ == "__main__":
    main()