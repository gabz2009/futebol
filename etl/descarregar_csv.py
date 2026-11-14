"""
=====================================================================
 DESCARREGAR O CSV DA ÉPOCA ATUAL (football-data.co.uk)
=====================================================================
 COMO CORRER (o executar_tudo.py já o faz, antes do ETL)
   python etl/descarregar_csv.py

 O QUE FAZ
   1. Descarrega o CSV da época atual (cfg.CSV_URL): resultados,
      estatísticas (remates, cantos...) e odds.
   2. Verifica-o (func/descarregar.py): colunas mínimas e nunca
      menos jogos do que o ficheiro que já existe.
   3. Só então substitui o dados/origem/P1_<época>.csv. A troca é feita
      de uma vez (os.replace): se algo falhar a meio, o ficheiro antigo
      fica intacto. As épocas passadas não são tocadas.
=====================================================================
"""
import os
import sys
import urllib.error
import urllib.request

import pandas as pd

import configuracao as cfg
import func.descarregar as descarregar


def jogos_no_ficheiro_atual():
    if not cfg.FICHEIRO_CSV_ATUAL.exists():
        return 0
    atual = pd.read_csv(cfg.FICHEIRO_CSV_ATUAL, dtype=str, encoding="utf-8-sig")
    return len(atual.dropna(subset=["HomeTeam", "AwayTeam"]))


def main():
    # Um navegador "normal": alguns sites recusam pedidos sem identificação
    pedido = urllib.request.Request(cfg.CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            conteudo = resposta.read()
    except urllib.error.HTTPError as erro:
        sys.exit(f"O site respondeu {erro.code} ({erro.reason}) para {cfg.CSV_URL}. Nada foi gravado.")
    except urllib.error.URLError as erro:
        sys.exit(f"Sem ligação ao football-data.co.uk ({erro.reason}). Nada foi gravado.")

    antes = jogos_no_ficheiro_atual()
    tabela, motivo = descarregar.validar_csv(conteudo, antes)
    if tabela is None:
        sys.exit(f"CSV recusado: {motivo}. O ficheiro atual ficou como estava.")

    # Grava primeiro num ficheiro temporário e só depois troca (de uma vez só)
    temporario = cfg.FICHEIRO_CSV_ATUAL.with_suffix(".tmp")
    temporario.write_bytes(conteudo)
    os.replace(temporario, cfg.FICHEIRO_CSV_ATUAL)
    print(f"Gravado {cfg.FICHEIRO_CSV_ATUAL.name}: {len(tabela)} jogos (antes {antes}), "
          f"último jogo a {tabela['Date'].iloc[-1]}")


if __name__ == "__main__":
    main()