import json
import logging
from datetime import datetime

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

PADRAO_PAISES = "paises_*.json"

SERIES = {
    "pib_per_capita_*.json": "pib_per_capita_usd",
    "escolaridade_*.json": "escolaridade_anos",
}

COLUNAS_VAZIAS = ["unit", "obs_status", "decimal"]

FAIXA_ESCOLARIDADE = ["muito baixa", "baixa", "alta", "muito alta"]

COLUNAS = ["pais_id", "pais_nome", "regiao", "nivel_renda", "ano",
           "pib_per_capita_usd", "escolaridade_anos", "escolaridade_anos_faixa"]


def carregar(prefixo):
    arquivos = sorted(config.BRONZE_BANCO.glob(prefixo))
    if not arquivos:
        raise FileNotFoundError(
            f"nada com o padrao {prefixo} em {config.BRONZE_BANCO}")
    caminho = arquivos[-1]
    with caminho.open(encoding="utf-8") as f:
        df = pd.json_normalize(json.load(f))
    log.info("lido: %s, %s registros", caminho.name, len(df))
    return df, caminho


def tirar_colunas_vazias(df):
    
    vazias = []
    for coluna in COLUNAS_VAZIAS:
        texto = df[coluna].astype("string").str.strip().fillna("")
        if texto.eq("").all():
            vazias.append(coluna)
    log.info("colunas sem nenhum valor: %s", vazias or "nenhuma")
    return df.drop(columns=vazias)


def separar_agregados(df):
    paises, _ = carregar(PADRAO_PAISES)
    e_pais = paises["region.value"] != "Aggregates"
    validos = set(paises.loc[e_pais, "id"])
    log.info("paises: %s | agregados: %s",
             len(validos), int((~e_pais).sum()))

    antes = len(df)
    df = df[df["countryiso3code"].isin(validos)].copy()
    log.info("linhas antes: %s, depois: %s", antes, len(df))
    return df


def conferir_chave(df, chave=["pais_id", "ano"]):
    repetidas = int(df.duplicated(subset=chave).sum())
    if repetidas:
        log.warning("chaves repetidas: %s", repetidas)
    else:
        log.debug("chaves repetidas: 0")
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
    config.PRATA.mkdir(parents=True, exist_ok=True)
    destino = config.PRATA / "determinantes_socioeconomicos.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s, %s", destino.name, df.shape)
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
    config.PRATA.mkdir(parents=True, exist_ok=True)
    with (config.PRATA / "proveniencia.jsonl").open("a", encoding="utf-8") as f:
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
            
            
            
            df = df.merge(parte, on=["pais_id", "ano"], how="outer",
                          validate="one_to_one")
            so_escolaridade = (df["pib_per_capita_usd"].isna()
                               & df["escolaridade_anos"].notna())
            log.info("linhas so com escolaridade (motivo do outer): %s",
                     int(so_escolaridade.sum()))

    df = limpeza.cruzar_com_paises(df, ["pais_nome", "regiao", "nivel_renda"])
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
    config.configurar_log()
    main()
