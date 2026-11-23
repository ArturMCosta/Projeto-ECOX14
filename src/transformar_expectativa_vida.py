import json
import logging
from datetime import datetime

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

PADRAO = "expectativa_vida_*.json"

MAPA_SEXO = {"SEX_BTSX": "total", "SEX_FMLE": "feminino", "SEX_MLE": "masculino"}

FAIXA_ESPERATIVA = ["muito baixa", "baixa", "alta", "muito alta"]

COLUNAS = ["pais_id", "pais_nome", "ano", "sexo", "regiao_oms",
           "expectativa_vida", "ic_baixo", "ic_alto",
           "variacao_pct", "expectativa_vida_faixa"]


def carregar():
    arquivos = sorted(config.BRONZE_WHO.glob(PADRAO))
    if not arquivos:
        raise FileNotFoundError(f"nada em {config.BRONZE_WHO}")
    caminho = arquivos[-1]
    with caminho.open(encoding="utf-8") as f:
        df = pd.DataFrame(json.load(f))
    log.info("lido: %s, %s registros", caminho.name, len(df))
    log.debug("ausentes por coluna:\n%s", df.isna().sum())
    return df, caminho


def tipar_sexo(df):
    antes = df["Dim1"].isna().sum()
    df["sexo"] = df["Dim1"].map(MAPA_SEXO)
    sem_rotulo = df["sexo"].isna().sum() - antes
    if sem_rotulo:
        log.warning("sexo sem rotulo: %s", sem_rotulo)
    else:
        log.debug("sexo sem rotulo: 0")
    df["sexo"] = pd.Categorical(df["sexo"], list(MAPA_SEXO.values()))
    return df


def tipar_ano(df):
    df["ano"] = pd.to_numeric(df["TimeDim"], errors="coerce").astype("Int64")
    return df


def separar_agregados(df):
    e_pais = df["SpatialDimType"] == "COUNTRY"
    log.info("paises: %s | agregados: %s",
             int(e_pais.sum()), int((~e_pais).sum()))
    return df[e_pais].copy()


def conferir_chave(df, chave=["pais_id", "ano", "sexo"]):
    repetidas = int(df.duplicated(subset=chave).sum())
    if repetidas:
        log.warning("chaves repetidas: %s", repetidas)
        log.debug("%s", df[df.duplicated(subset=chave, keep=False)])
    else:
        log.debug("chaves repetidas: 0")
    return df.drop_duplicates(subset=chave)


def remover_erros(df, coluna, minimo, maximo):
    valido = df[coluna].between(minimo, maximo)
    if (~valido).sum():
        log.warning("%s fora de %s a %s: %s removidas",
                    coluna, minimo, maximo, int((~valido).sum()))
    return df[valido].copy()


def salvar(df):
    config.PRATA.mkdir(parents=True, exist_ok=True)
    destino = config.PRATA / "expectativa_vida.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s, %s", destino.name, df.shape)
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
    config.PRATA.mkdir(parents=True, exist_ok=True)
    with (config.PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    df, origem = carregar()
    antes = len(df)

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
    df = limpeza.cruzar_com_paises(df, ["pais_nome", "regiao"])
    df = limpeza.variacao_anual(df, ["pais_id", "sexo"], "ano",
                                "expectativa_vida")
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
    config.configurar_log()
    main()
