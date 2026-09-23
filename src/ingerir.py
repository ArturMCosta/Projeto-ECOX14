from pathlib import Path
import kagglehub
from datetime import date, datetime
import shutil
import json

# PASSO 4
DATASET = "kumarajarshi/life-expectancy-who"
BRONZE = Path("dados/bronze/life_expectancy_who")

def baixar():
    pasta = kagglehub.dataset_download(DATASET)
    print("baixado em:", pasta)
    return Path(pasta)

# PASSO 5
def localizar(pasta):
    arquivos = list(pasta.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError("nenhum CSV")
    print("encontrados:", [a.name for a in arquivos])
    return arquivos[0]

# PASSO 6
def copiar(origem):
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"life_expectancy_{hoje}.csv"
    shutil.copy(origem, destino)
    return destino

# PASSO 7
def registrar(origem, destino):
    info = {
        "fonte": DATASET,
        "arquivo_origem": origem.name,
        "arquivo_bronze": destino.name,
        "extraido_em": datetime.now().isoformat()
    }
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")

# PASSO 8
def main():
    pasta = baixar()
    origem = localizar(pasta)
    destino = copiar(origem)
    registrar(origem, destino)
    print("Pipeline de ingestão concluído com sucesso!")

if __name__ == "__main__":
    main()