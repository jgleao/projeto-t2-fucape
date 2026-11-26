# Resultados do Benchmark (gerado por `python -m scripts.benchmark --fonte sintetico`)

* **Corpus:** Corpus sintetico Zipf (80000 documentos, semente 42)
* **Indice:** 80000 documentos, 20000 termos, 2286101 postagens (indexado em 4.4s)
* **Ambiente:** Python 3.13.14 - Windows-11-10.0.26300-SP0 - 2026-11-26T12:56:19
* **Metodo:** media de 5 execucoes com `time.perf_counter()`, 1 aquecimento, GC desligado durante a medicao, K = 10.

## 1. Ranqueamento Top-K (BM25)

| Consulta | Candidatos | Exaustivo (ms) | TAAT+heap (ms) | WAND (ms) | WAND+CL (ms) | BMW (ms) | Delta % (WAND+CL) | Speedup | Poda docs % | Top-K identico |
|---|---|---|---|---|---|---|---|---|---|---|
| jogo travando muito | 74352 | 25.212 | 16.247 | 5.58 | 0.254 | 0.395 | 99.0 | 99.08x | 99.9 | sim |
| otimizacao ruim fps baixo | 17187 | 9.338 | 4.631 | 5.057 | 4.385 | 3.197 | 53.0 | 2.13x | 91.4 | sim |
| historia emocionante personagens | 944 | 2.603 | 0.179 | 0.451 | 0.494 | 0.743 | 81.0 | 5.26x | 45.4 | sim |
| servidor lag multiplayer | 714 | 3.159 | 0.202 | 0.346 | 0.241 | 0.33 | 92.4 | 13.13x | 76.3 | sim |
| vale a pena comprar | 14530 | 7.767 | 3.55 | 1.184 | 1.095 | 2.136 | 85.9 | 7.09x | 97.7 | sim |
| bugs crash fechando sozinho | 4090 | 5.357 | 0.825 | 2.079 | 1.818 | 3.454 | 66.1 | 2.95x | 93.9 | sim |
| graficos lindos mundo aberto | 710 | 2.773 | 0.128 | 0.433 | 0.368 | 0.577 | 86.7 | 7.54x | 71.4 | sim |
| preco caro promocao | 2395 | 6.416 | 0.522 | 0.435 | 0.767 | 1.079 | 88.0 | 8.36x | 84.6 | sim |
| jogar com amigos | 30838 | 17.62 | 10.047 | 3.713 | 0.14 | 0.284 | 99.2 | 125.64x | 99.8 | sim |
| melhor jogo que ja joguei | 72497 | 22.193 | 13.662 | 6.48 | 0.311 | 0.433 | 98.6 | 71.42x | 99.9 | sim |
| cheater hacker banido | 306 | 2.119 | 0.111 | 0.268 | 0.306 | 0.583 | 85.6 | 6.92x | 0.0 | sim |
| musica trilha sonora incrivel | 657 | 2.683 | 0.141 | 0.329 | 0.469 | 0.667 | 82.5 | 5.72x | 64.7 | sim |

**Resumo**

| Algoritmo | Tempo medio (ms) | Delta % | Speedup | Poda docs % | Memoria/consulta (KB) |
|---|---|---|---|---|---|
| BM25 exaustivo (baseline) | 8.937 | - | 1.0x | 0 | 4936.3 |
| TAAT + heap (ablacao) | 4.187 | 53.1 | 2.13x | 0 | - |
| WAND | 2.196 | 75.4 | 4.07x | 91.6 | 2.1 |
| **WAND + Champion Lists** | **0.887** | **90.1** | **10.07x** | 98.1 | 15.9 |
| Block-Max WAND | 1.157 | 87.1 | 7.73x | 98.8 | 15.9 |

Top-K identico ao exaustivo em todas as consultas: WAND+CL = True, BMW = True.

## 2. Correcao ortografica (2 estagios vs. forca bruta)

| Digitado | Forca bruta (ms) | 2 estagios (ms) | Delta % | Speedup | Candidatos Levenshtein | Reducao % | Sugestao | Mesma sugestao |
|---|---|---|---|---|---|---|---|---|
| trvando | 146.556 | 0.035 | 100.0 | 4223.5x | 3 / 19999 | 99.98 | travando | sim |
| otimizaçao | 192.048 | 0.041 | 100.0 | 4646.3x | 2 / 19999 | 99.99 | otimizacao | sim |
| grafcos | 134.782 | 0.026 | 100.0 | 5224.1x | 2 / 19999 | 99.99 | graficos | sim |
| multiplayr | 220.844 | 0.039 | 100.0 | 5600.4x | 1 / 19999 | 99.99 | multiplayer | sim |
| servdor | 149.073 | 0.018 | 100.0 | 8205.9x | 1 / 19999 | 99.99 | servidor | sim |
| histporia | 175.574 | 0.018 | 100.0 | 9664.6x | 1 / 19999 | 99.99 | historia | sim |
| personagen | 181.359 | 3.438 | 98.1 | 52.8x | 1 / 19999 | 99.99 | personagens | sim |
| dificuldad | 189.347 | 0.021 | 100.0 | 8988.0x | 1 / 19999 | 99.99 | dificuldade | sim |
| jogablidade | 219.05 | 0.029 | 100.0 | 7668.0x | 1 / 19999 | 99.99 | jogabilidade | sim |
| travamneto | 192.631 | 0.039 | 100.0 | 4914.1x | 2 / 19999 | 99.99 | travamento | sim |
| lagando | 148.939 | 0.039 | 100.0 | 3851.9x | 3 / 19999 | 99.98 | lagando | sim |
| emocionnte | 178.343 | 0.03 | 100.0 | 6038.7x | 1 / 19999 | 99.99 | emocionante | sim |

**Resumo:** forca bruta 177.379 ms vs. 2 estagios 0.314 ms -> Delta 99.8% (564.2x), concordancia 100.0%, autocompletar (Trie) 0.0003 ms.

## 3. Escalabilidade (o ganho cresce com o tamanho da base)

| Documentos | Exaustivo (ms) | WAND+CL (ms) | BMW (ms) | Speedup WAND+CL | Poda % |
|---|---|---|---|---|---|
| 5000 | 0.362 | 0.533 | 0.444 | 0.68x | 49.1 |
| 10000 | 0.83 | 0.601 | 0.345 | 1.38x | 71.7 |
| 20000 | 1.488 | 0.204 | 0.328 | 7.29x | 97.7 |
| 40000 | 3.106 | 0.384 | 0.596 | 8.1x | 98.0 |
| 80000 | 7.044 | 0.876 | 0.962 | 8.04x | 98.1 |
