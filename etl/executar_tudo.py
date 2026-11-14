import subprocess
import sys

from pathlib import Path 

PASTA_ETL = Path(__file__).resolve().parent
DOWNLOADS = ["descarregar_calendario.py", "descarregar_csv.py", "descarregar_jogadores.py"]
PASSOS = ["executar_etl.py", "processar_jogadores.py", "criar_variaveis.py", "prever.py", "carregar_warehouse.py"]

def main():
    passos = PASSOS if "--sem-internet" in sys.argv else DOWNLOADS + PASSOS
    for passo in passos:
        print(f"\n ===== {passo} =====")
        resultado = subprocess.run([sys.executable, str(PASTA_ETL / passo)])
        if resultado.returncode != 0:
            print(f"Erro ao executar {passo}. Saindo.")
            sys.exit(resultado.returncode)
        
    print("\n Tudo concluído.")

if __name__ == "__main__":
    main()