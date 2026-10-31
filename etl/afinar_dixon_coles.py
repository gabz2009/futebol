"""
=====================================================================
 AFINAR O PESO DO TEMPO (XI) E A PENALIZAÇÃO (RIDGE) DO DIXON-COLES
=====================================================================
 COMO CORRER (uma vez, depois das variáveis; demora cerca de 8 min)
   python etl/afinar_dixon_coles.py

 O QUE FAZ
   Para cada combinação de XI e RIDGE, prevê todos os jogos das épocas
   de cfg.USOS_AFINACAO (cada jogo só com os jogos anteriores, como no
   walk-forward) e calcula o log loss médio. Escolhe a combinação com
   menor log loss. O teste nunca entra na escolha.

 No fim mostra as linhas DC_XI e DC_RIDGE para copiar para configuracao.py.
=====================================================================
"""
import itertools
import sqlite3
import time
from contextlib import closing

import pandas as pd

import configuracao as cfg
import func.avaliacao as av
import func.dixon_coles as dc

GRELHA_XI = [0.0, 0.001, 0.0019]      # 0 = sem peso do tempo; 0,0019 = metade do peso ao fim de 1 ano
GRELHA_RIDGE = [1, 2, 5]


def main():
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        jogos = pd.read_sql("SELECT JogoID, Epoca, Data, EquipaCasa, EquipaFora, GolosCasa, GolosFora FROM jogos", ligacao)
        variaveis = pd.read_sql("SELECT * FROM variaveis ORDER BY Data, JogoID", ligacao)

    # A 1.ª época dos dados não se pode prever (não há jogos antes dela)
    epocas = [e for e in sorted(variaveis.loc[variaveis["Uso"].isin(cfg.GAP_AFINACAO), "Epoca"].unique())
              if e != cfg.EPOCAS_ESPERADAS[0]]
    melhor = None
    for xi, ridge in itertools.product(GRELHA_XI, GRELHA_RIDGE):
        inicio = time.time()
        previsor = dc.criar_previsor(jogos, xi, ridge)
        erros = []
        for epoca in epocas:
            teste = variaveis[variaveis["Epoca"] == epoca]
            erros.append(av.medidas_por_jogo(previsor(None, teste), teste["Resultado"])["LogLoss"])
        erro = pd.concat(erros).mean()
        print(f"XI={xi:<6} RIDGE={ridge:<2} | log loss {erro:.4f} ({time.time() - inicio:.0f} s)", flush=True)
        if melhor is None or erro < melhor[0]:
            melhor = (erro, xi, ridge)

    print("\nCopia para configuracao.py:\n")
    print(f"DC_XI = {melhor[1]}")
    print(f"DC_RIDGE = {melhor[2]}")


if __name__ == "__main__":
    main()