import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/who_gho")
PRATA = Path("dados/prata")
PADRAO = "indicadores_*.csv"
INDICADOR = "WHOSIS_000001"

MAPA_SEXO = {"SEX_BTSX": "total", "SEX_FMLE": "feminino", "SEX_MLE": "masculino"}

FAIXA_ESPERATIVA = ["muito baixa", "baixa", "alta", "muito alta"]

COLUNAS = ["pais_id", "pais_nome", "ano", "sexo", "regiao_oms",
           "expectativa_vida", "ic_baixo", "ic_alto",
           "variacao_pct", "expectativa_vida_faixa"]


def carregar():
    arquivos = sorted(BRONZE.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {BRONZE}")
    caminho = arquivos[-1]
    df = pd.read_csv(caminho)
    print("lido:", caminho.name, df.shape)
    return df[df["IndicatorCode"] == INDICADOR].copy(), caminho


def tipar_sexo(df):
    antes = df["Dim1"].isna().sum()
    df["sexo"] = df["Dim1"].map(MAPA_SEXO)
    print("sexo sem rotulo:", df["sexo"].isna().sum() - antes)
    df["sexo"] = pd.Categorical(df["sexo"], list(MAPA_SEXO.values()))
    return df


def tipar_ano(df):
    df["ano"] = pd.to_numeric(df["TimeDim"], errors="coerce").astype("Int64")
    return df


def separar_agregados(df):
    e_pais = df["SpatialDimType"] == "COUNTRY"
    print("paises   :", e_pais.sum())
    print("agregados:", (~e_pais).sum())
    return df[e_pais].copy()


def conferir_chave(df, chave=["pais_id", "ano", "sexo"]):
    repetidas = df.duplicated(subset=chave).sum()
    print("chaves repetidas:", repetidas)
    if repetidas:
        print(df[df.duplicated(subset=chave, keep=False)])
    return df.drop_duplicates(subset=chave)


def remover_erros(df, coluna, minimo, maximo):
    valido = df[coluna].between(minimo, maximo)
    print("removidas:", (~valido).sum())
    return df[valido].copy()


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "expectativa_vida.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def registrar(origem, destino, antes, depois, decisoes):
    info = {
        "origem": origem.name,
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
    df, origem = carregar()
    antes = len(df)
    print(df.isna().sum())

    df = tipar_sexo(df)
    df = tipar_ano(df)
    df = limpeza.tipar_numero(df, ["NumericValue", "Low", "High"])
    df = df.rename(columns={
        "SpatialDim": "pais_id",
        "ParentLocation": "regiao_oms",
        "NumericValue": "expectativa_vida",
        "Low": "ic_baixo",
        "High": "ic_alto",
    })
    df = separar_agregados(df)
    df = conferir_chave(df)
    df = remover_erros(df, "expectativa_vida", 0, 100)
    df = limpeza.cruzar_com_paises(df, PRATA, ["pais_nome", "regiao"])
    df = limpeza.variacao_anual(df, "pais_id", "ano", "expectativa_vida")
    df = limpeza.faixa_por_quartil(df, "expectativa_vida", FAIXA_ESPERATIVA)

    destino = salvar(df[COLUNAS])
    registrar(origem, destino, antes, len(df), [
        "codigo de sexo traduzido e tipado como categoria",
        "ano convertido para inteiro, nao para data",
        "valor lido de NumericValue, nao de Value que vem como texto com intervalo",
        "agregados separados pela declaracao SpatialDimType da propria fonte",
        "nome do pais e regiao cruzados com o Banco Mundial",
        "fora de 0 a 100 removido: a faixa vem do dominio",
        "derivados: variacao_pct e expectativa_vida_faixa",
    ])


if __name__ == "__main__":
    main()