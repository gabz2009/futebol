"""
=====================================================================
 MODELO DIXON-COLES (Dixon e Coles, 1997)
=====================================================================
 A IDEIA
   Em vez de prever logo casa / empate / fora, prevê-se quantos golos
   marca cada equipa. Cada equipa tem dois números:
     - ataque: alto = marca muito
     - defesa: alto = sofre muito (defesa fraca)
   Golos esperados (casa i contra fora j):
     casa = exp(base + casa_vantagem + ataque_i + defesa_j)
     fora = exp(base + ataque_j + defesa_i)
   'base' é o nível médio de golos da liga. Ataques e defesas estão
   centrados em 0 (0 = equipa média).

 DA TABELA DE RESULTADOS AO 1X2
   Com os golos esperados, a distribuição de Poisson dá a probabilidade
   de cada resultado exato (0-0, 1-0, 2-1, ...). Soma-se:
     abaixo da diagonal = vitória da casa, diagonal = empate,
     acima da diagonal = vitória de fora.

 A CORREÇÃO RHO (o que distingue o Dixon-Coles de um Poisson simples)
   Só mexe nos resultados 0-0, 1-0, 0-1 e 1-1:
     0-0 x (1 - casa*fora*rho)   0-1 x (1 + casa*rho)
     1-0 x (1 + fora*rho)        1-1 x (1 - rho)
   Rho negativo = mais 0-0 e 1-1 do que o Poisson diz; positivo = menos.

 PENALIZAÇÃO (RIDGE)
   Uma equipa com 1 jogo fica com números extremos (ex.: um 0-0 faz o
   modelo achar que ela nunca marca nem sofre). A penalização puxa o
   ataque e a defesa para 0 (equipa média) enquanto há poucos jogos.
   A base, a vantagem de casa e o rho não são penalizados.

 PESO DO TEMPO (XI)
   Cada jogo pesa exp(-XI x dias desde o jogo). XI = 0: todos pesam igual.

 SEM FUGA DE INFORMAÇÃO
   O modelo é ajustado só com jogos de datas ANTERIORES e volta a ser
   ajustado de cfg.DC_DIAS_REAJUSTE em cfg.DC_DIAS_REAJUSTE dias.
=====================================================================
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import poisson

import configuracao as cfg


def criar_custo(jogos_passados, data, xi, ridge):
    """Prepara a função que o otimizador minimiza.
    Devolve (custo_e_gradiente, separar, posicao, numero_de_parametros)."""
    dias = (data - jogos_passados["Data"]).dt.days.to_numpy()
    peso = np.exp(-xi * dias)

    equipas = sorted(set(jogos_passados["EquipaCasa"]) | set(jogos_passados["EquipaFora"]))
    posicao = {equipa: i for i, equipa in enumerate(equipas)}
    n = len(equipas)
    casa = jogos_passados["EquipaCasa"].map(posicao).to_numpy()
    fora = jogos_passados["EquipaFora"].map(posicao).to_numpy()
    x = jogos_passados["GolosCasa"].to_numpy(dtype=int)
    y = jogos_passados["GolosFora"].to_numpy(dtype=int)

    # Quais jogos acabaram 0-0, 0-1, 1-0 e 1-1 (os únicos que o rho corrige)
    r00, r01, r10, r11 = (x == 0) & (y == 0), (x == 0) & (y == 1), (x == 1) & (y == 0), (x == 1) & (y == 1)
    log_fatoriais = gammaln(x + 1) + gammaln(y + 1)

    def separar(t):
        ataque = t[:n] - t[:n].mean()
        defesa = t[n:2 * n] - t[n:2 * n].mean()
        return ataque, defesa, t[2 * n], t[2 * n + 1], t[2 * n + 2]

    def custo_e_gradiente(t):
        """Custo = menos a verosimilhança (quanto menor, melhor o modelo explica os
        jogos passados) + penalização. Gradiente = quanto o custo muda quando
        cada número muda um bocadinho (diz ao otimizador para onde ir)."""
        ataque, defesa, base, vantagem, rho = separar(t)
        esperado_casa = np.exp(base + vantagem + ataque[casa] + defesa[fora])
        esperado_fora = np.exp(base + ataque[fora] + defesa[casa])

        # Correção rho e as suas derivadas (só nos jogos 0-0, 0-1, 1-0 e 1-1)
        tau = np.ones(len(x))
        tau[r00] = 1 - esperado_casa[r00] * esperado_fora[r00] * rho
        tau[r01] = 1 + esperado_casa[r01] * rho
        tau[r10] = 1 + esperado_fora[r10] * rho
        tau[r11] = 1 - rho
        tau = np.clip(tau, 1e-10, None)
        d_casa, d_fora, d_rho = np.zeros(len(x)), np.zeros(len(x)), np.zeros(len(x))
        d_casa[r00] = d_fora[r00] = -esperado_casa[r00] * esperado_fora[r00] * rho / tau[r00]
        d_rho[r00] = -esperado_casa[r00] * esperado_fora[r00] / tau[r00]
        d_casa[r01] = esperado_casa[r01] * rho / tau[r01]
        d_rho[r01] = esperado_casa[r01] / tau[r01]
        d_fora[r10] = esperado_fora[r10] * rho / tau[r10]
        d_rho[r10] = esperado_fora[r10] / tau[r10]
        d_rho[r11] = -1 / tau[r11]

        log_prob = (x * np.log(esperado_casa) - esperado_casa + y * np.log(esperado_fora) - esperado_fora
                    - log_fatoriais + np.log(tau))
        custo = -(peso * log_prob).sum() + ridge * ((ataque ** 2).sum() + (defesa ** 2).sum())

        # Gradiente: cada jogo "empurra" o ataque e a defesa das duas equipas
        g_casa = peso * (x - esperado_casa + d_casa)
        g_fora = peso * (y - esperado_fora + d_fora)
        g_ataque = -(np.bincount(casa, g_casa, n) + np.bincount(fora, g_fora, n)) + 2 * ridge * ataque
        g_defesa = -(np.bincount(fora, g_casa, n) + np.bincount(casa, g_fora, n)) + 2 * ridge * defesa
        gradiente = np.concatenate([g_ataque - g_ataque.mean(), g_defesa - g_defesa.mean(),
                                    [-(g_casa + g_fora).sum(), -g_casa.sum(), -(peso * d_rho).sum()]])
        return custo, gradiente

    return custo_e_gradiente, separar, posicao, 2 * n + 3


def ajustar(jogos_passados, data, xi=cfg.DC_XI, ridge=cfg.DC_RIDGE):
    """Ajusta o modelo com os jogos de 'jogos_passados' (todos anteriores a 'data').
    Devolve um dicionário com os números de cada equipa e os gerais."""
    custo_e_gradiente, separar, posicao, numero = criar_custo(jogos_passados, data, xi, ridge)
    inicio = np.concatenate([np.zeros(numero - 3), [0.2, 0.2, 0.0]])
    limites = [(None, None)] * (numero - 1) + [(-0.3, 0.3)]          # rho fica entre -0.3 e 0.3
    # jac=True: a função devolve também o gradiente. Sem ele, o otimizador
    # tinha de o estimar mexendo em cada número à vez (cerca de 12x mais lento).
    otimo = minimize(custo_e_gradiente, inicio, jac=True, method="L-BFGS-B", bounds=limites)
    ataque, defesa, base, vantagem, rho = separar(otimo.x)
    return {"posicao": posicao, "ataque": ataque, "defesa": defesa,
            "base": base, "vantagem": vantagem, "rho": rho}


def tabela_resultados(esperado_casa, esperado_fora, rho, max_golos=cfg.DC_MAX_GOLOS):
    """Probabilidade de cada resultado exato. Linha = golos da casa, coluna = golos de fora."""
    golos = np.arange(max_golos + 1)
    tabela = np.outer(poisson.pmf(golos, esperado_casa), poisson.pmf(golos, esperado_fora))
    tabela[0, 0] *= 1 - esperado_casa * esperado_fora * rho
    tabela[0, 1] *= 1 + esperado_casa * rho
    tabela[1, 0] *= 1 + esperado_fora * rho
    tabela[1, 1] *= 1 - rho
    return tabela / tabela.sum()         # cortar em max_golos deixa de fora um bocadinho: volta a somar 1


def probabilidades_1x2(tabela):
    """Casa (abaixo da diagonal), empate (diagonal), fora (acima da diagonal)."""
    return [np.tril(tabela, -1).sum(), np.trace(tabela), np.triu(tabela, 1).sum()]


def numeros_promovida(modelo, jogos, epoca):
    """Ataque e defesa de uma equipa sem jogos: a média das que desceram na época anterior."""
    epocas = sorted(jogos["Epoca"].unique())
    anterior = epocas[epocas.index(epoca) - 1]
    equipas_anterior = set(jogos.loc[jogos["Epoca"] == anterior, "EquipaCasa"])
    equipas_agora = set(jogos.loc[jogos["Epoca"] == epoca, "EquipaCasa"])
    desceram = [modelo["posicao"][e] for e in equipas_anterior - equipas_agora]
    return modelo["ataque"][desceram].mean(), modelo["defesa"][desceram].mean()


def criar_previsor(jogos, xi=cfg.DC_XI, ridge=cfg.DC_RIDGE):
    """Devolve um previsor(treino, teste) para o avaliacao.walk_forward.
    'jogos' é a tabela jogos (com os golos), de onde o modelo aprende.
    O 'treino' do walk_forward não é usado: o modelo usa todos os jogos
    anteriores a cada data, incluindo os da própria época."""
    jogos = jogos.assign(Data=pd.to_datetime(jogos["Data"]))

    def previsor(treino, teste):
        # Por ordem de data, para nunca usar um modelo ajustado depois do jogo
        por_data = teste.assign(Data=pd.to_datetime(teste["Data"])).sort_values(["Data", "JogoID"])
        probabilidades = {}
        data_ajuste = None
        for jogo in por_data.itertuples():
            if data_ajuste is None or (jogo.Data - data_ajuste).days >= cfg.DC_DIAS_REAJUSTE:
                data_ajuste = jogo.Data
                modelo = ajustar(jogos[jogos["Data"] < data_ajuste], data_ajuste, xi, ridge)
                promovida = numeros_promovida(modelo, jogos, jogo.Epoca)

            def numeros(equipa):
                i = modelo["posicao"].get(equipa)
                return promovida if i is None else (modelo["ataque"][i], modelo["defesa"][i])

            ataque_casa, defesa_casa = numeros(jogo.EquipaCasa)
            ataque_fora, defesa_fora = numeros(jogo.EquipaFora)
            esperado_casa = np.exp(modelo["base"] + modelo["vantagem"] + ataque_casa + defesa_fora)
            esperado_fora = np.exp(modelo["base"] + ataque_fora + defesa_casa)
            tabela = tabela_resultados(esperado_casa, esperado_fora, modelo["rho"])
            probabilidades[jogo.JogoID] = probabilidades_1x2(tabela)

        # Devolve pela ordem em que 'teste' chegou (é essa que o walk_forward espera)
        return np.array([probabilidades[j] for j in teste["JogoID"]])

    return previsor