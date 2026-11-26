# Resultados do Benchmark (gerado por `python -m scripts.benchmark --fonte sintetico`)

* **Corpus:** Corpus sintetico Zipf (80000 documentos, semente 42)
* **Indice:** 80000 documentos, 20000 termos, 2286101 postagens (indexado em 4.9s)
* **Ambiente:** Python 3.13.14 - Windows-11-10.0.26300-SP0 - 2026-11-26T13:31:14
* **Metodo:** media de 5 execucoes com `time.perf_counter()`, 1 aquecimento, GC desligado durante a medicao, K = 10.

## 1. Ranqueamento Top-K (BM25)

| Consulta | Candidatos | Exaustivo (ms) | TAAT+heap (ms) | WAND (ms) | WAND+CL (ms) | BMW (ms) | Delta % (WAND+CL) | Speedup | Poda docs % | Top-K identico |
|---|---|---|---|---|---|---|---|---|---|---|
| jogo travando muito | 74352 | 28.283 | 26.886 | 9.506 | 0.577 | 0.631 | 98.0 | 48.99x | 99.9 | sim |
| otimizacao ruim fps baixo | 17187 | 12.052 | 4.92 | 7.549 | 6.282 | 3.743 | 47.9 | 1.92x | 91.3 | sim |
| historia emocionante personagens | 944 | 3.812 | 0.436 | 0.907 | 0.833 | 1.189 | 78.1 | 4.57x | 45.4 | sim |
| servidor lag multiplayer | 714 | 3.135 | 0.141 | 0.454 | 0.511 | 0.337 | 83.7 | 6.13x | 76.3 | sim |
| vale a pena comprar | 14530 | 9.943 | 4.413 | 2.201 | 1.927 | 3.337 | 80.6 | 5.16x | 97.7 | sim |
| bugs crash fechando sozinho | 4090 | 6.931 | 1.498 | 2.672 | 3.252 | 5.874 | 53.1 | 2.13x | 93.9 | sim |
| graficos lindos mundo aberto | 710 | 5.003 | 0.511 | 0.998 | 0.614 | 0.584 | 87.7 | 8.15x | 39.3 | sim |
| preco caro promocao | 2395 | 5.678 | 0.956 | 1.067 | 0.506 | 0.664 | 91.1 | 11.22x | 84.6 | sim |
| jogar com amigos | 30838 | 14.651 | 10.592 | 3.742 | 0.211 | 0.345 | 98.6 | 69.42x | 99.8 | sim |
| melhor jogo que ja joguei | 72497 | 26.766 | 24.167 | 9.193 | 0.371 | 0.454 | 98.6 | 72.08x | 99.9 | sim |
| cheater hacker banido | 306 | 3.02 | 0.183 | 0.394 | 0.557 | 0.67 | 81.5 | 5.42x | 0.0 | sim |
| musica trilha sonora incrivel | 657 | 5.098 | 0.317 | 0.702 | 0.541 | 1.158 | 89.4 | 9.42x | 64.7 | sim |

**Resumo**

| Algoritmo | Tempo medio (ms) | Delta % | Speedup | Poda docs % | Memoria/consulta (KB) |
|---|---|---|---|---|---|
| BM25 exaustivo (baseline) | 10.364 | - | 1.0x | 0 | 4936.3 |
| TAAT + heap (ablacao) | 6.252 | 39.7 | 1.66x | 0 | - |
| WAND | 3.282 | 68.3 | 3.16x | 91.6 | 2.1 |
| **WAND + Champion Lists** | **1.348** | **87.0** | **7.69x** | 98.0 | 16.0 |
| Block-Max WAND | 1.582 | 84.7 | 6.55x | 98.7 | 15.9 |

Top-K identico ao exaustivo em todas as consultas: WAND+CL = True, BMW = True.

## 2. Correcao ortografica (2 estagios vs. forca bruta)

| Digitado | Forca bruta (ms) | 2 estagios (ms) | Delta % | Speedup | Candidatos Levenshtein | Reducao % | Sugestao | Mesma sugestao |
|---|---|---|---|---|---|---|---|---|
| trvando | 185.415 | 0.043 | 100.0 | 4332.1x | 3 / 19999 | 99.98 | travando | sim |
| otimizaçao | 244.399 | 0.044 | 100.0 | 5500.3x | 2 / 19999 | 99.99 | otimizacao | sim |
| grafcos | 183.115 | 0.023 | 100.0 | 8019.6x | 2 / 19999 | 99.99 | graficos | sim |
| multiplayr | 262.138 | 0.023 | 100.0 | 11186.5x | 1 / 19999 | 99.99 | multiplayer | sim |
| servdor | 172.835 | 0.021 | 100.0 | 8063.9x | 1 / 19999 | 99.99 | servidor | sim |
| histporia | 217.377 | 0.029 | 100.0 | 7487.2x | 1 / 19999 | 99.99 | historia | sim |
| personagen | 250.586 | 3.961 | 98.4 | 63.3x | 1 / 19999 | 99.99 | personagens | sim |
| dificuldad | 249.837 | 0.035 | 100.0 | 7077.5x | 1 / 19999 | 99.99 | dificuldade | sim |
| jogablidade | 270.708 | 0.031 | 100.0 | 8741.9x | 1 / 19999 | 99.99 | jogabilidade | sim |
| travamneto | 249.828 | 0.056 | 100.0 | 4450.6x | 2 / 19999 | 99.99 | travamento | sim |
| lagando | 186.123 | 0.039 | 100.0 | 4817.7x | 3 / 19999 | 99.98 | lagando | sim |
| emocionnte | 235.174 | 0.036 | 100.0 | 6556.9x | 1 / 19999 | 99.99 | emocionante | sim |

**Resumo:** forca bruta 225.628 ms vs. 2 estagios 0.362 ms -> Delta 99.8% (623.7x), concordancia 100.0%, autocompletar (Trie) 0.0004 ms.

## 3. Escalabilidade (o ganho cresce com o tamanho da base)

| Documentos | Exaustivo (ms) | WAND+CL (ms) | BMW (ms) | Speedup WAND+CL | Poda % |
|---|---|---|---|---|---|
| 5000 | 0.537 | 1.145 | 0.916 | 0.47x | 49.1 |
| 10000 | 1.255 | 1.295 | 0.558 | 0.97x | 71.7 |
| 20000 | 2.22 | 0.369 | 0.481 | 6.01x | 97.5 |
| 40000 | 5.024 | 0.708 | 0.972 | 7.1x | 97.9 |
| 80000 | 10.524 | 1.349 | 1.532 | 7.8x | 98.0 |
