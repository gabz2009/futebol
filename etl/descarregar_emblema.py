"""
=====================================================================
 DESCARREGAR OS EMBLEMAS DOS CLUBES (TheSportsDB)
=====================================================================
 COMO CORRER (uma vez; outra vez só quando subir uma equipa nova)
   python etl/descarregar_emblemas.py

 O QUE FAZ
   Para cada uma das equipas da base de dados (as de cfg.NOMES_APRESENTACAO),
   pesquisa o nome no TheSportsDB e grava as respostas TAL COMO VIERAM
   em dados/origem/emblemas_thesportsdb.json. Não escolhe nada: é o ETL
   que escolhe a equipa certa em cada resposta (func/emblemas.py).

 A API
   Gratuita, com a chave pública "3" (não precisa de registo). Tem um
   limite de pedidos por minuto, por isso há uma pausa entre pedidos.
=====================================================================
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import configuracao as cfg

PAUSA_SEGUNDOS = 4        # cerca de 24 pedidos por minuto, abaixo do limite da chave gratuita
ESPERA_LIMITE = 60
TENTATIVAS = 5

def pesquisar(termo):
    endereco = f"{cfg.THESPORTSDB_URL}?{urllib.parse.urlencode({'t': termo})}"
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(endereco, timeout=30) as resposta:
                return json.load(resposta).get("teams")          # None quando não encontra nada
        except urllib.error.HTTPError as erro:
            if erro.code != 429 or tentativa == TENTATIVAS:
                raise
            # 429 = demasiados pedidos: a API às vezes diz quanto esperar (Retry-After)
            espera = int(erro.headers.get("Retry-After") or ESPERA_LIMITE)
            print(f"   limite de pedidos atingido: a esperar {espera} s (tentativa {tentativa} de {TENTATIVAS})")
            time.sleep(espera)


def main():
    respostas = {}
    for equipa in sorted(cfg.NOMES_APRESENTACAO):
        termo = cfg.NOMES_THESPORTSDB.get(equipa, equipa)
        try:
            respostas[equipa] = {"pesquisa": termo, "equipas": pesquisar(termo)}
        except (urllib.error.URLError, TimeoutError) as erro:
            sys.exit(f"Erro ao pesquisar '{termo}' ({erro}). Nada foi gravado.")
        encontradas = len(respostas[equipa]["equipas"] or [])
        print(f"{equipa:16s} pesquisa '{termo}': {encontradas} resultado(s)")
        time.sleep(PAUSA_SEGUNDOS)

    dados = {"descarregado_em": datetime.now().isoformat(timespec="seconds"), "respostas": respostas}
    cfg.FICHEIRO_EMBLEMAS.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Gravado {cfg.FICHEIRO_EMBLEMAS.name}")


if __name__ == "__main__":
    main()