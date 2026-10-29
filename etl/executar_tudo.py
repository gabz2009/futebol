import subprocess
import sys

from pathlib import Path 

PASTA_ETL = Path(__file__).resolve().parent
PASSOS = ["executar_etl.py", "criar_variaveis.py"]

def main():
    for passo in PASSOS:
        print(f"\n ===== {passo} =====")
        resultado = subprocess.run([sys.executable, str(PASTA_ETL / passo)])
        if resultado.returncode != 0:
            print(f"Erro ao executar {passo}. Saindo.")
            sys.exit(resultado.returncode)
        
    print("\n Tudo concluído.")

if __name__ == "__main__":
    main()