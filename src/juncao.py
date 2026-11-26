

import logging

log = logging.getLogger(__name__)


def conferir_chaves(esquerda, direita, col_esq, col_dir):
    
    esq = set(esquerda[col_esq].dropna())
    dir_ = set(direita[col_dir].dropna())

    so_esquerda = esq - dir_
    so_direita = dir_ - esq
    nos_dois = esq & dir_

    log.info("chaves so na esquerda (%s): %s", col_esq, len(so_esquerda))
    log.info("chaves so na direita  (%s): %s", col_dir, len(so_direita))
    log.info("chaves nos dois: %s", len(nos_dois))

    if so_esquerda:
        log.debug("  exemplos so na esquerda: %s", sorted(so_esquerda)[:5])
    if so_direita:
        log.debug("  exemplos so na direita: %s", sorted(so_direita)[:5])

    return so_esquerda, so_direita, nos_dois


def juntar(esquerda, direita, col_esq, col_dir, relacao="many_to_one"):
    
    return esquerda.merge(
        direita,
        left_on=col_esq,
        right_on=col_dir,
        how="left",
        validate=relacao,
    )


def validar(esquerda, resultado, coluna_da_direita):
    
    sem_par = resultado[coluna_da_direita].isna()
    total = int(sem_par.sum())

    log.info("linhas na esquerda: %s", len(esquerda))
    log.info("linhas no resultado: %s", len(resultado))
    if total:
        log.warning("sem par: %s", total)
    else:
        log.info("sem par: 0")

    if len(resultado) < len(esquerda):
        log.warning("o resultado perdeu linhas. Juncao do tipo errado?")
    elif len(resultado) > len(esquerda):
        log.warning("o resultado ganhou linhas. A chave repete na direita.")

    return resultado[sem_par]
