"""
=====================================================================
 DESCARREGAR AS FICHAS DOS JOGOS (API não oficial da ESPN)
=====================================================================
 COMO CORRER (o executar_tudo.py já o corre, a seguir ao calendário)
   python etl/descarregar_jogadores.py

 O QUE FAZ
   Vê no calendário que dias têm jogos terminados sem ficha gravada,
   pede à ESPN os jogos desses dias e grava a ficha de cada um TAL
   COMO VEIO em dados/origem/espn/ (um ficheiro por jogo). Na
   primeira vez apanha a época toda; depois só os jogos novos.

 SE A ESPN FALHAR
   A API não é oficial e pode mudar ou falhar. Nesse caso avisa e
   termina sem erro: as fichas já gravadas continuam a servir e o
   resto do executar_tudo.py corre na mesma.
=====================================================================
"""
import json
import os
import time
import urllib.error
import urllib.request

import configuracao as cfg
import func.espn as espn


def pedir(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": cfg.ESPN_USER_AGENT})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)


def gravar(caminho, dados):
    """Grava primeiro num .tmp e só depois troca: um ficheiro a meio nunca fica com o nome final."""
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)


def main():
    cfg.PASTA_ESPN.mkdir(parents=True, exist_ok=True)
    calendario = json.loads(cfg.FICHEIRO_CALENDARIO.read_text(encoding="utf-8"))
    dias = espn.dias_por_descarregar(calendario, cfg.PASTA_ESPN)
    novas = 0
    try:
        for dia in dias:
            jogos = pedir(f"{cfg.ESPN_URL}/scoreboard?dates={dia.replace('-', '')}")["events"]
            for jogo in jogos:
                caminho = cfg.PASTA_ESPN / f"{dia}_{jogo['id']}.json"
                if caminho.exists() or not jogo["status"]["type"]["completed"]:
                    continue
                time.sleep(cfg.ESPN_PAUSA)
                ficha = pedir(f"{cfg.ESPN_URL}/summary?event={jogo['id']}")
                if espn.ficha_completa(ficha):
                    gravar(caminho, ficha)
                    novas += 1
                else:
                    print(f"{dia} {jogo['name']}: a ficha ainda está incompleta, fica para a próxima")
            time.sleep(cfg.ESPN_PAUSA)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as erro:
        print(f"AVISO: a ESPN falhou ({erro}). Ficam as {novas} fichas novas gravadas até aqui; "
              "as que faltam vêm na próxima vez.")
    total = len(list(cfg.PASTA_ESPN.glob("*.json")))
    print(f"Fichas novas: {novas} | dias vistos: {len(dias)} | fichas na pasta: {total}")


if __name__ == "__main__":
    main()