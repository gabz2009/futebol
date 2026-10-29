"""
=====================================================================
 AFINAR OS PARÂMETROS DOS GAP RATINGS
=====================================================================
 COMO CORRER (uma vez, depois do ETL)
   python etl/afinar_gap.py

 O QUE FAZ
   Para cada estatística (remates falhados, remates à baliza, cantos),
   experimenta várias combinações de LAMBDA, PHI1 e PHI2 e escolhe a
   que prevê melhor essa estatística: o menor erro quadrático médio
   entre o esperado e o real. É o método do artigo de Wheatcroft.

 SEM FUGA DE INFORMAÇÃO
   - O erro só é medido nas épocas de TREINO. A validação e o teste
     não entram na escolha.
   - Afina-se a previsão dos remates e cantos, não do resultado.

 No fim mostra o bloco GAP_PARAMETROS para copiar para configuracao.py.
=====================================================================
"""
import itertools
import sqlite3
from contextlib import closing

import numpy as np
import pandas as pd

import configuracao as cfg
import func.gap_ratings as gap



def main():
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        jogos = pd.read_sql("SELECT * FROM jogos", ligacao, parse_dates=["Data"])
        epocas = pd.read_sql("SELECT Epoca, Uso FROM epocas", ligacao)

    jogos = gap.ordenar(gap.acrescentar_estatisticas(jogos))
    treino = jogos["Epoca"].isin(epocas.loc[epocas["Uso"] == "Treino", "Epoca"]).to_numpy()

    escolhidos = {}
    for nome, (col_casa, col_fora) in cfg.ESTATISTICAS.items():
        real = np.concatenate([jogos[col_casa].to_numpy()[treino], jogos[col_fora].to_numpy()[treino]])
        # Referência: prever sempre a média do treino (sem ratings nenhuns)
        erro_media = np.mean((real - real.mean()) ** 2)

        melhor = None
        for lam, phi1, phi2 in itertools.product(cfg.GRELHA_LAMBDA, cfg.GRELHA_PHI, cfg.GRELHA_PHI):
            casa, fora = gap.esperado_por_jogo(jogos, col_casa, col_fora, lam, phi1, phi2)
            previsto = np.concatenate([np.array(casa)[treino], np.array(fora)[treino]])
            erro = np.mean((real - previsto) ** 2)
            if melhor is None or erro < melhor[0]:
                melhor = (erro, lam, phi1, phi2)

        erro, lam, phi1, phi2 = melhor
        print(f"{nome:9s} lambda={lam:.2f} phi1={phi1:.1f} phi2={phi2:.1f} | "
              f"erro GAP={erro:.3f} vs prever a média={erro_media:.3f} "
              f"({(1 - erro / erro_media):.0%} melhor)")
        escolhidos[nome] = (col_casa, col_fora, lam, phi1, phi2)

    print("\nCopia para configuracao.py:\n")
    print("GAP_PARAMETROS = {")
    for nome, (col_casa, col_fora, lam, phi1, phi2) in escolhidos.items():
        print(f'    "{nome}": {{"casa": "{col_casa}", "fora": "{col_fora}", '
              f'"lambda": {lam}, "phi1": {phi1}, "phi2": {phi2}}},')
    print("}")


if __name__ == "__main__":
    main()