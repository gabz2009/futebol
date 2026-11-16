# Metodologia

Este documento explica com mais detalhe como os modelos foram construídos e avaliados, e porque se tomou cada decisão. O resumo está no [README](../README.md).

## 1. Dados

| Fonte | O que dá | Como entra |
| --- | --- | --- |
| football-data.co.uk | jogos desde 2017-18: resultado, remates, cantos, cartões e odds de várias casas | CSV por época (`P1_2017-18.csv`, ...) |
| football-data.org | calendário da época atual, resultados e jogos adiados | API REST com chave gratuita |
| ESPN (API não oficial) | onzes, formação, substituições, golos e cartões por jogador, posse de bola | uma ficha JSON por jogo |
| TheSportsDB | emblemas das equipas | API |

As duas fontes de resultados são cruzadas. O controlo C18 verifica que os golos são iguais nas duas, e o C19 avisa quando um jogo já acabou na API mas ainda não chegou ao CSV. Nesse caso, o jogo entra com os golos da API, para os modelos aprenderem com ele logo a seguir.

As equipas da ESPN não têm os mesmos nomes que as do CSV. O mapeamento é feito sem tabela à mão: emparelham-se os jogos pela data e pelo resultado, e cada equipa da ESPN fica com a equipa do CSV com que coincide mais vezes (um para um, das contagens maiores para as menores).

## 2. Divisão das épocas

A divisão é sempre feita por tempo. Num problema de previsão, misturar épocas ao acaso deixava o modelo aprender com jogos que aconteceram depois daqueles que está a prever.

| Época | Uso |
| --- | --- |
| 2017-18 | Aquecimento: os ratings começam todos iguais e ainda não são fiáveis |
| 2018-19 a 2020-21 | Treino |
| 2021-22 a 2024-25 | Validação: escolher modelos e parâmetros |
| 2025-26 | Teste: usado uma única vez, com o modelo já fechado |
| 2026-27 | Previsões reais |

A validação é feita em **walk-forward**: para prever cada época, o modelo é treinado só com as épocas anteriores, como se estivéssemos nessa altura.

## 3. Variáveis

Todas as variáveis de um jogo são calculadas só com os jogos anteriores a ele. O controlo V04 testa isto diretamente: altera o resultado de um jogo e confirma que as variáveis desse jogo não mudam, só as dos jogos seguintes.

- **Elo:** um rating por equipa que sobe quando ganha e desce quando perde (K = 20, vantagem de casa de 60 pontos). No início de cada época, cada rating aproxima-se 20% de 1500, porque os plantéis mudam.
- **Pi-ratings** (Constantinou e Fenton, 2013): um rating em casa e outro fora, atualizados pela diferença entre os golos esperados e os golos reais.
- **GAP ratings** (Wheatcroft, 2021): em vez de golos, usam estatísticas que dão mais informação e dependem menos da sorte. Há três conjuntos: remates falhados, remates à baliza e cantos. Os parâmetros foram afinados com as épocas de treino e validação (`afinar_gap.py`).

Uma lição da validação foi que **os remates e os cantos dizem mais do que os golos**: só com as variáveis GAP, a regressão deu log loss 0,918, contra 0,927 só com o Elo, e ganhou nas quatro épocas de validação. Outra foi que **mais variáveis pioram**: com as 37 variáveis juntas deu 0,938.

## 4. Modelos

| Modelo | Ideia | Detalhes |
| --- | --- | --- |
| Regressão ordinal | casa, empate e fora têm uma ordem; uma só escala de "força relativa" decide as três probabilidades | usa só as 3 diferenças GAP (`GapFalhadosDif`, `GapBalizaDif`, `GapCantosDif`) |
| Dixon-Coles (1997) | prevê os golos de cada equipa com uma distribuição de Poisson, com correção para resultados baixos (0-0, 1-0, 0-1, 1-1) | jogos antigos pesam menos (um jogo de há 2 anos pesa metade); penalização ridge que puxa o ataque e a defesa para a média; reajuste semanal |
| Gradient Boosting | árvores de decisão que corrigem os erros umas das outras | `HistGradientBoostingClassifier` do scikit-learn; os parâmetros são escolhidos de novo em cada ronda do walk-forward, só com as épocas de treino dessa ronda |

**O modelo final é a média geométrica dos três** (normalizada para as probabilidades somarem 1). Cada modelo erra de forma diferente, e a média corta parte desses erros. No teste, cada modelo sozinho ficou entre 0,919 e 0,920 de log loss, e a média ficou em 0,913.

Na época atual, a regressão ordinal e o boosting voltam a ser treinados todas as semanas com os jogos já jogados. A validação mostrou que isto ajuda um pouco (−0,0013 no log loss).

## 5. Como se mede o erro

- **Log loss:** castiga as previsões confiantes que falham. É a métrica principal: menor é melhor.
- **RPS (Ranked Probability Score):** tem em conta a ordem dos resultados. Prever vitória da casa quando acaba empatado é um erro menor do que quando ganha a equipa de fora.
- **ECE (erro de calibração):** quando o modelo diz 60%, acontece mesmo cerca de 60% das vezes? Calcula-se por faixas de 10% (só faixas com pelo menos 20 jogos).
- **Acerto:** percentagem de jogos em que o resultado mais provável aconteceu. É fácil de perceber mas diz pouco, por isso não é usada para escolher modelos.

**A referência são as odds.** As odds de abertura (cerca de uma semana antes do jogo) e de fecho (no dia do jogo) são convertidas em probabilidades, retirando a margem da casa de apostas. As odds de fecho já incluem lesões, onzes e notícias de última hora, por isso são muito difíceis de bater.

**Bootstrap:** para saber se uma diferença é real ou sorte, os jogos do teste são reamostrados 2 000 vezes e a diferença de log loss é calculada em cada amostra. Se o intervalo de 95% incluir o 0, a diferença pode ser sorte.

## 6. Resultado no teste (2025-26, 306 jogos)

As decisões ficaram escritas no topo do notebook `03_teste.ipynb` antes de o correr: o modelo final, as referências e os parâmetros.

| Modelo | Acerto | Log loss | RPS | ECE |
| --- | ---: | ---: | ---: | ---: |
| Odds de fecho | 57,5% | 0,9011 | 0,1702 | 0,061 |
| Odds de abertura | 56,5% | 0,9110 | 0,1733 | 0,070 |
| **Modelo final** | **55,6%** | **0,9131** | **0,1734** | **0,053** |
| Ordinal GAP | 55,2% | 0,9192 | 0,1755 | 0,047 |
| Dixon-Coles | 55,6% | 0,9198 | 0,1742 | 0,058 |
| Boosting | 54,6% | 0,9201 | 0,1754 | 0,055 |
| Frequências | 41,2% | 1,0861 | 0,2297 | 0,021 |

Diferença de log loss do modelo final (bootstrap, intervalo de 95%):

| Contra | Diferença | Intervalo | Pode ser sorte? |
| --- | ---: | --- | --- |
| Ordinal GAP | −0,0061 | −0,017 a +0,005 | Sim |
| Odds de abertura | +0,0021 | −0,013 a +0,017 | Sim |
| Odds de fecho | +0,0120 | −0,005 a +0,029 | Sim |

**Leitura:** o modelo está ao nível das odds de abertura. No RPS a diferença é praticamente zero (0,1734 contra 0,1733) e o bootstrap não os consegue distinguir. Fica atrás das odds de fecho, o que é esperado, porque estas sabem os onzes. E é o mais bem calibrado dos três (ECE 0,053).

## 7. Teste em tempo real (2026-27)

Desde 30 de outubro de 2026, o modelo está fechado e cada previsão oficial é guardada **antes** da jornada em `dados/historico.db`. Esta base de dados só cresce e está no Git, por isso o histórico de commits prova quando cada previsão foi feita. Depois dos jogos, o `prever.py` junta o resultado real e mede o acerto. É o teste mais honesto de todos, porque ninguém (nem o autor) podia ter visto os resultados.

As previsões dos jogos já jogados antes dessa data também existem, mas foram feitas com o modelo já treinado. Contam como avaliação, não como previsões oficiais.

## 8. Simulação da época

Para cada jogo por jogar, o modelo dá as probabilidades de casa, empate e fora. A simulação sorteia cada jogo com essas probabilidades, soma os pontos à classificação atual e repete isto **10 000 vezes**. Daqui saem:

- os pontos esperados de cada equipa;
- a probabilidade de ser campeã, ficar no top 3, ir à Europa (1.º ao 5.º), ir ao play-off de descida (16.º) ou descer (17.º e 18.º);
- a distribuição das posições finais.

Com 10 000 simulações, o erro de uma probabilidade de 50% é de cerca de 0,5 pontos percentuais. A semente é fixa (42), por isso correr duas vezes com os mesmos dados dá o mesmo resultado.

## 9. Qualidade dos dados

Cada passo grava os seus controlos numa tabela de QA, com o código, o valor esperado, o valor obtido e se é crítico. Um controlo crítico que falhe pára o pipeline.

| Grupo | Onde | Exemplos |
| --- | --- | --- |
| C01 a C20 | ETL | um ficheiro por época, 306 jogos por época completa, sem jogos repetidos, odds acima de 1 com margem plausível, golos iguais nas duas fontes |
| V01 a V08 | variáveis | um JogoID único por jogo, sem vazios fora do aquecimento, anti-fuga (V04), médias do Elo e dos pi-ratings estáveis |
| P01 a P04, S01 a S02, H01 | previsões | uma previsão por jogo do calendário, probabilidades entre 0 e 1 a somar 1, pontos simulados entre os atuais e o máximo possível |
| W01 | warehouse | linhas carregadas = linhas preparadas, tabela a tabela |

Outras proteções:

- **Escritas atómicas:** os ficheiros são escritos primeiro como `.tmp` e só depois substituem os antigos (`os.replace`). Uma falha a meio não deixa ficheiros cortados.
- **Carga numa transação:** o warehouse é carregado numa só transação. Se o W01 falhar (ou qualquer chave ou tipo), faz rollback e o Power BI continua com os dados da semana anterior.

## 10. Data warehouse

O schema `gold` no PostgreSQL segue um modelo em estrela: dimensões com prefixo `d` e factos com prefixo `f`.

- **Dimensões:** `dEquipa`, `dJornada`, `dJogo`, `dJogador`, `dFase`, `dModelo`
- **Factos:** `fPrevisoes`, `fSimulacao`, `fPosicoes`, `fClassificacao_jornada`, `fHistorico`, `fAvaliacao_oficial`, `fEstatisticas_jogo`, `fEpocas_equipa`, `fEquipa_jogo`, `fJogador_epoca`, `fJogador_jogo`, `fAvaliacao_modelos`, `fAvaliacao_epocas`, `fCalibracao`
- **Outra:** `Atualizacao` (data da última carga, mostrada no relatório)

O SQLite é a base de trabalho: não precisa de servidor e é recriado de raiz em cada execução. O PostgreSQL é a camada que serve o Power BI, com tipos, chaves e restrições `CHECK` definidas à mão.

## 11. Dados dos jogadores

As fichas da ESPN dão, por jogador e por jogo: minutos (a partir das substituições), golos, assistências, remates, faltas, cartões e defesas. Com isto calcula-se:

- **Função no plantel:** a percentagem dos minutos da equipa que o jogador jogou. Com 70% ou mais é titular habitual, entre 30% e 70% é rotação, abaixo disso é pouco utilizado.
- **Impacto (on/off):** a diferença de golos por 90 minutos da equipa com o jogador em campo e sem ele. Só é calculado com pelo menos 450 minutos em cada lado, porque com menos o número salta ao acaso.
- **Posição no campo:** a ESPN dá a posição de cada titular de acordo com a formação (4-2-3-1, 4-3-3, ...). Isso é convertido em coordenadas para desenhar o onze no relatório.

## 12. Decisões e alternativas

| Decisão | Alternativa | Porquê |
| --- | --- | --- |
| Agendador do Windows com um `.bat` | Airflow, Prefect | uma execução por semana num só computador; um orquestrador seria mais infraestrutura do que pipeline |
| SQLite + PostgreSQL | só PostgreSQL | o SQLite facilita recriar tudo de raiz e testar; o PostgreSQL fica só para servir |
| Modelo fechado depois do teste | continuar a afinar | qualquer afinação depois de ver o teste tornava a avaliação otimista |
| API não oficial da ESPN para jogadores | Transfermarkt, API-Football | o Transfermarkt (Kaggle) parou em julho de 2026 e a API-Football gratuita não tem a época atual |
| `requirements.txt` só com as dependências diretas | `pip freeze` | o `freeze` trazia pacotes só do Windows que partiam o CI em Linux |

## Referências

- Dixon, M. & Coles, S. (1997). Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society: Series C (Applied Statistics)*, 46(2).
- Constantinou, A. & Fenton, N. (2013). Determining the level of ability of football teams by dynamic ratings based on the relative discrepancies in scores between adversaries. *Journal of Quantitative Analysis in Sports*, 9(1).
- Wheatcroft, E. (2021). Forecasting football matches by predicting match statistics. *Journal of Sports Analytics*, 7(2).
