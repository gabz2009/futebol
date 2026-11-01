"""
=====================================================================
 SIMULAÇÃO DO RESTO DA ÉPOCA (MONTE CARLO)
=====================================================================
 A IDEIA
   Cada jogo que falta é "jogado" à sorte com as probabilidades do
   modelo final (ex.: 60% casa, 25% empate, 15% fora). Juntam-se os
   pontos aos que cada equipa já tem e faz-se a classificação final.
   Repete-se cfg.SIMULACOES vezes (10 000). Se o Benfica acabar em
   1.º em 3 800 simulações, tem 38% de ser campeão.

 DESEMPATES (regulamento da Liga Portugal)
   1. Pontos   2. Pontos nos jogos entre as equipas empatadas
   3. Diferença de golos nesses jogos   4. Diferença de golos geral ...
   Na simulação só se sorteia vitória / empate / derrota, não os golos.
   Por isso: 1 e 2 são aplicados como no regulamento; a seguir usa-se a
   diferença de golos dos jogos JÁ jogados; e no fim, se ainda houver
   empate, sorteia-se.

 SIMPLIFICAÇÃO (fica no README)
   As probabilidades dos jogos que faltam ficam fixas dentro de cada
   simulação: se uma equipa ganhar 5 jogos seguidos numa simulação, não
   fica "mais forte" nos seguintes. É o método mais usado; a versão
   que atualiza os ratings dentro da simulação é bem mais complexa.

 RESULTADOS CONHECIDOS
   Os jogos terminados vêm da API (golos), incluindo os que ainda não
   estão no CSV. O controlo C18 do ETL garante que, nos jogos que estão
   nas duas fontes, os golos são iguais.
=====================================================================
"""
import numpy as np
import pandas as pd

import configuracao as cfg


def resultados_da_api(calendario, origem_calendario):
    """Golos dos jogos já terminados segundo a API (incluindo os que ainda não estão no CSV)."""
    golos = calendario[["JogoID", "IdAPI", "Estado"]].merge(
        origem_calendario[["IdAPI", "GolosCasaAPI", "GolosForaAPI"]], on="IdAPI", validate="one_to_one")
    terminados = golos[(golos["Estado"] == "FINISHED") & golos["GolosCasaAPI"].notna()]
    return terminados.rename(columns={"GolosCasaAPI": "GolosCasa", "GolosForaAPI": "GolosFora"})[
        ["JogoID", "GolosCasa", "GolosFora"]]


def preparar_jogos(previsoes, resultados):
    """Um jogo por linha: jornada, equipas, golos (se já terminou) e probabilidades do modelo final.
    resultados = JogoID, GolosCasa, GolosFora dos jogos já terminados."""
    jogos = previsoes[["JogoID", "Jornada", "EquipaCasa", "EquipaFora", "ProbCasa", "ProbEmpate", "ProbFora"]].merge(
        resultados, on="JogoID", how="left", validate="one_to_one")
    jogos["Terminado"] = jogos["GolosCasa"].notna()
    return jogos


def pontos_do_jogo(golos_casa, golos_fora):
    """(pontos da casa, pontos de fora)."""
    return np.where(golos_casa > golos_fora, 3, np.where(golos_casa == golos_fora, 1, 0)), \
           np.where(golos_fora > golos_casa, 3, np.where(golos_casa == golos_fora, 1, 0))


def classificacao_atual(jogos):
    """Classificação com os jogos já terminados, ordenada pelo regulamento:
    pontos, confronto direto (pontos e diferença de golos), diferença de golos,
    vitórias e golos marcados."""
    feitos = jogos[jogos["Terminado"]]
    equipas = sorted(set(jogos["EquipaCasa"]) | set(jogos["EquipaFora"]))
    casa = pd.DataFrame({"Equipa": feitos["EquipaCasa"], "Adversario": feitos["EquipaFora"],
                         "Marcados": feitos["GolosCasa"], "Sofridos": feitos["GolosFora"]})
    fora = pd.DataFrame({"Equipa": feitos["EquipaFora"], "Adversario": feitos["EquipaCasa"],
                         "Marcados": feitos["GolosFora"], "Sofridos": feitos["GolosCasa"]})
    linhas = pd.concat([casa, fora], ignore_index=True)
    linhas["Pontos"] = pontos_do_jogo(linhas["Marcados"], linhas["Sofridos"])[0]
    linhas["Vitoria"] = (linhas["Pontos"] == 3).astype(int)
    linhas["Empate"] = (linhas["Pontos"] == 1).astype(int)
    linhas["Derrota"] = (linhas["Pontos"] == 0).astype(int)

    tabela = (linhas.groupby("Equipa")
              .agg(Jogos=("Pontos", "size"), Vitorias=("Vitoria", "sum"), Empates=("Empate", "sum"),
                   Derrotas=("Derrota", "sum"), GolosMarcados=("Marcados", "sum"),
                   GolosSofridos=("Sofridos", "sum"), Pontos=("Pontos", "sum"))
              .reindex(equipas, fill_value=0).reset_index())
    tabela["DiferencaGolos"] = tabela["GolosMarcados"] - tabela["GolosSofridos"]

    # Confronto direto: pontos e diferença de golos SÓ nos jogos entre equipas com os mesmos pontos
    pontos = tabela.set_index("Equipa")["Pontos"]
    entre_empatadas = linhas[linhas["Equipa"].map(pontos) == linhas["Adversario"].map(pontos)]
    direto = entre_empatadas.groupby("Equipa").agg(PontosDireto=("Pontos", "sum"),
                                                   Marcados=("Marcados", "sum"), Sofridos=("Sofridos", "sum"))
    tabela = tabela.merge(direto, on="Equipa", how="left").fillna({"PontosDireto": 0, "Marcados": 0, "Sofridos": 0})
    tabela["DiferencaDireto"] = tabela["Marcados"] - tabela["Sofridos"]

    tabela = tabela.sort_values(["Pontos", "PontosDireto", "DiferencaDireto", "DiferencaGolos", "Vitorias",
                                 "GolosMarcados"], ascending=False).reset_index(drop=True)
    tabela.insert(0, "Posicao", np.arange(1, len(tabela) + 1))
    return tabela.drop(columns=["PontosDireto", "Marcados", "Sofridos", "DiferencaDireto"])


def simular(jogos, simulacoes=cfg.SIMULACOES, semente=cfg.SEMENTE):
    """Devolve (equipas, pontos finais, posições finais); pontos e posições têm uma
    linha por simulação e uma coluna por equipa."""
    equipas = sorted(set(jogos["EquipaCasa"]) | set(jogos["EquipaFora"]))
    n = len(equipas)
    posicao = {equipa: i for i, equipa in enumerate(equipas)}
    feitos, falta = jogos[jogos["Terminado"]], jogos[~jogos["Terminado"]]

    # 1. O que já se sabe: pontos, diferença de golos e confrontos diretos dos jogos terminados
    pontos_base = np.zeros(n)
    diferenca = np.zeros(n)
    direto_base = np.zeros((n, n))           # direto[i, j] = pontos de i nos jogos contra j
    pc, pf = pontos_do_jogo(feitos["GolosCasa"].to_numpy(), feitos["GolosFora"].to_numpy())
    for c, f, p_casa, p_fora, gc, gf in zip(feitos["EquipaCasa"].map(posicao), feitos["EquipaFora"].map(posicao),
                                            pc, pf, feitos["GolosCasa"], feitos["GolosFora"]):
        pontos_base[c] += p_casa
        pontos_base[f] += p_fora
        diferenca[c] += gc - gf
        diferenca[f] += gf - gc
        direto_base[c, f] += p_casa
        direto_base[f, c] += p_fora

    # 2. Sortear os jogos que faltam: um número entre 0 e 1 por jogo e por simulação
    gerador = np.random.default_rng(semente)
    sorteio = gerador.random((simulacoes, len(falta)))
    p_casa, p_empate = falta["ProbCasa"].to_numpy(), falta["ProbEmpate"].to_numpy()
    vitoria_casa = sorteio < p_casa
    empate = (sorteio >= p_casa) & (sorteio < p_casa + p_empate)
    pontos_casa = 3 * vitoria_casa + empate                  # simulações x jogos
    pontos_fora = 3 * (~vitoria_casa & ~empate) + empate

    # 3. Somar os pontos de cada equipa (matriz que liga cada jogo às suas equipas)
    i_casa, i_fora = falta["EquipaCasa"].map(posicao).to_numpy(), falta["EquipaFora"].map(posicao).to_numpy()
    em_casa = np.zeros((len(falta), n))
    em_casa[np.arange(len(falta)), i_casa] = 1
    fora_de_casa = np.zeros((len(falta), n))
    fora_de_casa[np.arange(len(falta)), i_fora] = 1
    pontos = pontos_base + pontos_casa @ em_casa + pontos_fora @ fora_de_casa

    # 4. Confronto direto em cada simulação
    direto = np.repeat(direto_base[None, :, :], simulacoes, axis=0)
    for k, (c, f) in enumerate(zip(i_casa, i_fora)):
        direto[:, c, f] += pontos_casa[:, k]
        direto[:, f, c] += pontos_fora[:, k]
    mesmos_pontos = pontos[:, :, None] == pontos[:, None, :]
    pontos_direto = (direto * mesmos_pontos).sum(axis=2)    # pontos contra as equipas empatadas

    # 5. Ordenar: pontos > confronto direto > diferença de golos (jogos feitos) > sorteio.
    # Junta-se tudo num só número (os pesos garantem que cada critério só conta no empate do anterior)
    criterio = pontos * 1e6 + pontos_direto * 1e3 + (diferenca + 500) + gerador.random((simulacoes, n))
    ordem = np.argsort(-criterio, axis=1)
    posicoes = np.empty_like(ordem)
    np.put_along_axis(posicoes, ordem, np.arange(1, n + 1)[None, :].repeat(simulacoes, axis=0), axis=1)
    return equipas, pontos, posicoes


def resumir(equipas, pontos, posicoes, classificacao):
    """Uma linha por equipa: classificação atual, pontos esperados e probabilidades de cada zona."""
    resumo = pd.DataFrame({
        "Equipa": equipas,
        "PontosEsperados": pontos.mean(axis=0),
        "PontosP10": np.percentile(pontos, 10, axis=0),
        "PontosP90": np.percentile(pontos, 90, axis=0),
        "PosicaoMedia": posicoes.mean(axis=0),
    })
    for nome, (primeira, ultima) in cfg.ZONAS_CLASSIFICACAO.items():
        resumo[f"Prob{nome}"] = ((posicoes >= primeira) & (posicoes <= ultima)).mean(axis=0)
    resumo = classificacao.merge(resumo, on="Equipa", validate="one_to_one")
    resumo["Simulacoes"] = len(pontos)
    return resumo.sort_values("Posicao").reset_index(drop=True)


def probabilidades_por_posicao(equipas, posicoes):
    """Formato longo para o Power BI (mapa de calor): Equipa, Posicao, Probabilidade."""
    n = len(equipas)
    contagens = np.stack([(posicoes == p).mean(axis=0) for p in range(1, n + 1)], axis=1)   # equipas x posições
    return pd.DataFrame({"Equipa": np.repeat(equipas, n), "Posicao": np.tile(np.arange(1, n + 1), n),
                         "Probabilidade": contagens.ravel()})

def classificacao_por_jornada(jogos):
    partes = []
    for jornada in range(1, int(jogos.loc[jogos["Terminado"], "Jornada"].max()) + 1):
        ate_aqui = jogos.assign(Terminado=jogos["Terminado"] & (jogos["Jornada"] <= jornada))
        partes.append(classificacao_atual(ate_aqui).assign(Jornada=jornada))
    return pd.concat(partes, ignore_index=True)
