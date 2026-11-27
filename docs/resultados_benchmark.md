# Resultados do Benchmark (gerado por `python -m scripts.benchmark --fonte dw`)

* **Corpus:** Data Warehouse (dw.dim_review, reviews reais da Steam)
* **Indice:** 26699 documentos, 26832 termos, 464284 postagens (indexado em 1.2s)
* **Ambiente:** Python 3.12.16 - Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.41 - 2026-11-27T01:52:20
* **Metodo:** media de 7 execucoes com `time.perf_counter()`, 1 aquecimento, GC desligado durante a medicao, K = 10.

## 1. Ranqueamento Top-K (BM25)

| Consulta | Candidatos | Exaustivo (ms) | TAAT+heap (ms) | WAND (ms) | WAND+CL (ms) | BMW (ms) | Delta % (WAND+CL) | Speedup | Poda docs % | Top-K identico |
|---|---|---|---|---|---|---|---|---|---|---|
| jogo travando muito | 17642 | 5.785 | 5.002 | 5.72 | 0.113 | 0.119 | 98.1 | 51.29x | 99.8 | sim |
| otimizacao ruim fps baixo | 861 | 1.371 | 0.217 | 0.469 | 0.459 | 0.683 | 66.5 | 2.98x | 82.8 | sim |
| historia emocionante personagens | 3614 | 2.228 | 1.138 | 2.542 | 2.32 | 0.782 | -4.1 | 0.96x | 71.4 | sim |
| servidor lag multiplayer | 257 | 1.274 | 0.074 | 0.19 | 0.144 | 0.184 | 88.7 | 8.83x | 84.0 | sim |
| vale a pena comprar | 1820 | 1.863 | 0.754 | 1.211 | 1.245 | 1.553 | 33.2 | 1.5x | 69.6 | sim |
| bugs crash fechando sozinho | 719 | 1.191 | 0.185 | 0.326 | 0.471 | 0.505 | 60.5 | 2.53x | 91.8 | sim |
| graficos lindos mundo aberto | 2861 | 2.065 | 0.955 | 1.607 | 1.711 | 2.377 | 17.1 | 1.21x | 80.9 | sim |
| preco caro promocao | 471 | 1.294 | 0.228 | 0.481 | 0.378 | 0.612 | 70.8 | 3.43x | 72.2 | sim |
| jogar com amigos | 3701 | 2.246 | 1.103 | 1.761 | 1.328 | 2.02 | 40.9 | 1.69x | 86.5 | sim |
| melhor jogo que ja joguei | 16737 | 5.634 | 4.753 | 4.302 | 4.14 | 7.049 | 26.5 | 1.36x | 92.8 | sim |
| cheater hacker banido | 232 | 1.002 | 0.113 | 0.323 | 0.206 | 0.273 | 79.4 | 4.86x | 36.6 | sim |
| musica trilha sonora incrivel | 2343 | 2.201 | 0.885 | 1.488 | 1.444 | 2.912 | 34.4 | 1.52x | 81.6 | sim |

**Resumo**

| Algoritmo | Tempo medio (ms) | Delta % | Speedup | Poda docs % | Memoria/consulta (KB) |
|---|---|---|---|---|---|
| BM25 exaustivo (baseline) | 2.346 | - | 1.0x | 0 | 1583.6 |
| TAAT + heap (ablacao) | 1.284 | 45.3 | 1.83x | 0 | - |
| WAND | 1.702 | 27.5 | 1.38x | 83.3 | 2.1 |
| **WAND + Champion Lists** | **1.163** | **50.4** | **2.02x** | 90.6 | 13.8 |
| Block-Max WAND | 1.589 | 32.3 | 1.48x | 93.6 | 13.8 |

Top-K identico ao exaustivo em todas as consultas: WAND+CL = True, BMW = True.

## 2. Correcao ortografica (2 estagios vs. forca bruta)

| Digitado | Forca bruta (ms) | 2 estagios (ms) | Delta % | Speedup | Candidatos Levenshtein | Reducao % | Sugestao | Mesma sugestao |
|---|---|---|---|---|---|---|---|---|
| trvando | 185.744 | 4.976 | 97.3 | 37.3x | 184 / 15617 | 98.82 | travando | sim |
| otimizaçao | 263.433 | 2.673 | 99.0 | 98.5x | 34 / 15617 | 99.78 | otimizacao | sim |
| grafcos | 186.884 | 2.842 | 98.5 | 65.8x | 25 / 15617 | 99.84 | graficos | sim |
| multiplayr | 242.589 | 1.277 | 99.5 | 190.0x | 12 / 15617 | 99.92 | multiplayer | sim |
| servdor | 163.608 | 1.688 | 99.0 | 96.9x | 30 / 15617 | 99.81 | servidor | sim |
| histporia | 196.562 | 2.401 | 98.8 | 81.9x | 17 / 15617 | 99.89 | historia | sim |
| personagen | 230.051 | 2.438 | 98.9 | 94.4x | 8 / 15617 | 99.95 | personagens | sim |
| dificuldad | 297.779 | 1.84 | 99.4 | 161.8x | 11 / 15617 | 99.93 | dificuldade | sim |
| jogablidade | 331.257 | 4.903 | 98.5 | 67.6x | 45 / 15617 | 99.71 | jogabilidade | sim |
| travamneto | 228.489 | 3.004 | 98.7 | 76.1x | 8 / 15617 | 99.95 | travamento | sim |
| lagando | 159.782 | 3.436 | 97.8 | 46.5x | 194 / 15617 | 98.76 | lagando | sim |
| emocionnte | 226.077 | 2.091 | 99.1 | 108.1x | 13 / 15617 | 99.92 | emocionante | sim |

**Resumo:** forca bruta 226.021 ms vs. 2 estagios 2.797 ms -> Delta 98.8% (80.8x), concordancia 100.0%, autocompletar (Trie) 0.0006 ms.

## 3. Escalabilidade (o ganho cresce com o tamanho da base)

| Documentos | Exaustivo (ms) | WAND+CL (ms) | BMW (ms) | Speedup WAND+CL | Poda % |
|---|---|---|---|---|---|
| 5000 | 0.329 | 0.473 | 0.618 | 0.7x | 74.6 |
| 10000 | 0.694 | 0.889 | 1.134 | 0.78x | 78.0 |
| 20000 | 1.474 | 0.86 | 0.987 | 1.72x | 89.5 |
| 26699 | 2.48 | 1.405 | 1.46 | 1.76x | 90.6 |
