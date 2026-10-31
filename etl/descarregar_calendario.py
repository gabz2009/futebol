"""
=====================================================================
 DESCARREGAR O CALENDÁRIO DA ÉPOCA ATUAL (API do football-data.org)
=====================================================================
 COMO CORRER (antes do ETL, sempre que quiseres atualizar o calendário)
   python etl/descarregar_calendario.py

 O QUE FAZ
   Pede à API todos os jogos da época atual (os jogados e os que
   faltam) e grava a resposta TAL COMO VEIO em dados/origem/.
   Não transforma nada: isso é trabalho do ETL, que lê este ficheiro
   como lê os CSV. Assim o ETL corre sem internet e dá sempre o mesmo
   resultado com os mesmos ficheiros.

 A CHAVE (TOKEN)
   Fica no ficheiro .env, na raiz do projeto, numa linha assim:
     FOOTBALL_DATA_TOKEN=a_tua_chave
   O .env está no .gitignore: a chave nunca vai para o GitHub.
=====================================================================
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

import configuracao as cfg


def ler_chave():
    """Lê FOOTBALL_DATA_TOKEN do ficheiro .env."""
    if not cfg.FICHEIRO_CHAVE.exists():
        sys.exit(f"Não existe {cfg.FICHEIRO_CHAVE}. Cria-o com a linha FOOTBALL_DATA_TOKEN=a_tua_chave")
    for linha in cfg.FICHEIRO_CHAVE.read_text(encoding="utf-8").splitlines():
        nome, _, valor = linha.partition("=")
        if nome.strip() == "FOOTBALL_DATA_TOKEN" and valor.strip():
            return valor.strip()
    sys.exit(f"{cfg.FICHEIRO_CHAVE} não tem a linha FOOTBALL_DATA_TOKEN=...")


def main():
    pedido = urllib.request.Request(f"{cfg.API_URL}?season={cfg.API_EPOCA}",
                                    headers={"X-Auth-Token": ler_chave()})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            dados = json.load(resposta)
    except urllib.error.HTTPError as erro:
        motivos = {400: "pedido inválido (vê o API_URL e o API_EPOCA)",
                   403: "chave errada ou sem acesso a esta competição",
                   429: "demasiados pedidos: espera um minuto e tenta outra vez"}
        sys.exit(f"A API respondeu {erro.code}: {motivos.get(erro.code, erro.reason)}. Nada foi gravado.")
    except urllib.error.URLError as erro:
        sys.exit(f"Sem ligação à API ({erro.reason}). Nada foi gravado.")

    # Guarda-se também quando foi descarregado (a API não diz)
    dados["descarregado_em"] = datetime.now().isoformat(timespec="seconds")
    cfg.FICHEIRO_CALENDARIO.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    estados = {}
    for jogo in dados["matches"]:
        estados[jogo["status"]] = estados.get(jogo["status"], 0) + 1
    print(f"Gravado {cfg.FICHEIRO_CALENDARIO.name}: {len(dados['matches'])} jogos {estados}")


if __name__ == "__main__":
    main()