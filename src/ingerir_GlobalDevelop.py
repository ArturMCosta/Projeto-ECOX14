from pathlib import Path
import kagglehub
from datetime import date, datetime
import shutil
import json

# PASSO 4
DATASET = "yogeshm01/global-development-data-19602025"
BRONZE = Path("dados/bronze/global_development")

def baixar():
    pasta = kagglehub.dataset_download(DATASET)
    print("baixado em:", pasta)
    return Path(pasta)

# PASSO 5
def localizar(pasta):
    # Constrói o caminho direto para o arquivo específico
    arquivo = pasta / "WDICSV.csv"
    
    if not arquivo.exists():
        disponiveis = [a.name for a in pasta.glob("*.csv")]
        raise FileNotFoundError(f"Arquivo '{ARQUIVO_ALVO}' não encontrado. Disponíveis na pasta: {disponiveis}")
        
    print("Encontrado:", arquivo.name)
    return arquivo

# PASSO 6
def copiar(origem):
    BRONZE.mkdir(parents=True, exist_ok=True)
    hoje = date.today().strftime("%Y%m%d")
    destino = BRONZE / f"global_development_{hoje}.csv"
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
    print("Ingestão do dataset de desenvolvimento concluída!")

if __name__ == "__main__":
    main()