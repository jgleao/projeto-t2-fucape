# Resultados do Benchmark (gerado por `python -m scripts.benchmark --fonte dw`)

* **Corpus:** Data Warehouse (dw.dim_review, reviews reais da Steam)
* **Indice:** 105957 documentos, 54500 termos, 1821516 postagens (indexado em 4.2s)
* **Ambiente:** Python 3.12.16 - Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.41 - 2026-11-27T02:14:16
* **Metodo:** media de 7 execucoes com `time.perf_counter()`, 1 aquecimento, GC desligado durante a medicao, K = 10.

## 1. Ranqueamento Top-K (BM25)

| Consulta | Candidatos | Exaustivo (ms) | TAAT+heap (ms) | WAND (ms) | WAND+CL (ms) | BMW (ms) | Delta % (WAND+CL) | Speedup | Poda docs % | Top-K identico |
|---|---|---|---|---|---|---|---|---|---|---|
| jogo travando muito | 69763 | 21.355 | 19.707 | 5.611 | 0.228 | 0.336 | 98.9 | 93.72x | 99.9 | sim |
| otimizacao ruim fps baixo | 3525 | 5.3 | 1.068 | 1.463 | 1.728 | 2.473 | 67.4 | 3.07x | 90.6 | sim |
| historia emocionante personagens | 14218 | 9.228 | 4.255 | 4.603 | 3.879 | 1.522 | 58.0 | 2.38x | 89.5 | sim |
| servidor lag multiplayer | 1027 | 3.585 | 0.305 | 0.414 | 0.315 | 0.517 | 91.2 | 11.38x | 90.5 | sim |
| vale a pena comprar | 7564 | 7.13 | 2.345 | 3.297 | 3.792 | 4.731 | 46.8 | 1.88x | 88.9 | sim |
| bugs crash fechando sozinho | 3212 | 4.877 | 0.934 | 1.074 | 1.027 | 1.961 | 78.9 | 4.75x | 95.6 | sim |
| graficos lindos mundo aberto | 11513 | 8.121 | 3.098 | 5.942 | 5.987 | 9.527 | 26.3 | 1.36x | 86.9 | sim |
| preco caro promocao | 2161 | 4.614 | 0.787 | 1.729 | 1.954 | 2.237 | 57.7 | 2.36x | 73.2 | sim |
| jogar com amigos | 14537 | 8.427 | 3.776 | 5.647 | 5.46 | 8.348 | 35.2 | 1.54x | 85.3 | sim |
| melhor jogo que ja joguei | 65990 | 22.883 | 17.383 | 16.535 | 16.652 | 27.729 | 27.2 | 1.37x | 92.4 | sim |
| cheater hacker banido | 984 | 3.724 | 0.323 | 0.565 | 0.574 | 0.674 | 84.6 | 6.49x | 47.8 | sim |
| musica trilha sonora incrivel | 9472 | 9.334 | 2.93 | 5.09 | 4.786 | 7.459 | 48.7 | 1.95x | 86.7 | sim |

**Resumo**

| Algoritmo | Tempo medio (ms) | Delta % | Speedup | Poda docs % | Memoria/consulta (KB) |
|---|---|---|---|---|---|
| BM25 exaustivo (baseline) | 9.048 | - | 1.0x | 0 | 6316.4 |
| TAAT + heap (ablacao) | 4.743 | 47.6 | 1.91x | 0 | - |
| WAND | 4.331 | 52.1 | 2.09x | 90.8 | 2.2 |
| **WAND + Champion Lists** | **3.865** | **57.3** | **2.34x** | 93.2 | 15.4 |
| Block-Max WAND | 5.626 | 37.8 | 1.61x | 94.7 | 15.4 |

Top-K identico ao exaustivo em todas as consultas: WAND+CL = True, BMW = True.

## 2. Correcao ortografica (2 estagios vs. forca bruta)

| Digitado | Forca bruta (ms) | 2 estagios (ms) | Delta % | Speedup | Candidatos Levenshtein | Reducao % | Sugestao | Mesma sugestao |
|---|---|---|---|---|---|---|---|---|
| trvando | 339.555 | 7.631 | 97.8 | 44.5x | 318 / 31276 | 98.98 | travando | sim |
| otimizaçao | 460.339 | 4.214 | 99.1 | 109.2x | 65 / 31276 | 99.79 | otimizacao | sim |
| grafcos | 406.902 | 3.78 | 99.1 | 107.7x | 43 / 31276 | 99.86 | graficos | sim |
| multiplayr | 460.729 | 2.521 | 99.5 | 182.8x | 19 / 31276 | 99.94 | multiplayer | sim |
| servdor | 338.42 | 4.259 | 98.7 | 79.5x | 41 / 31276 | 99.87 | servidor | sim |
| histporia | 421.043 | 3.855 | 99.1 | 109.2x | 30 / 31276 | 99.9 | historia | sim |
| personagen | 615.067 | 6.721 | 98.9 | 91.5x | 19 / 31276 | 99.94 | personagen | sim |
| dificuldad | 577.08 | 5.174 | 99.1 | 111.5x | 27 / 31276 | 99.91 | dificuldade | sim |
| jogablidade | 648.548 | 5.387 | 99.2 | 120.4x | 86 / 31276 | 99.73 | jogablidade | sim |
| travamneto | 562.101 | 4.103 | 99.3 | 137.0x | 15 / 31276 | 99.95 | travamento | sim |
| lagando | 336.022 | 7.255 | 97.8 | 46.3x | 341 / 31276 | 98.91 | lagando | sim |
| emocionnte | 484.709 | 3.886 | 99.2 | 124.7x | 24 / 31276 | 99.92 | emocionante | sim |

**Resumo:** forca bruta 470.876 ms vs. 2 estagios 4.899 ms -> Delta 99.0% (96.1x), concordancia 100.0%, autocompletar (Trie) 0.0005 ms.

## 3. Escalabilidade (o ganho cresce com o tamanho da base)

| Documentos | Exaustivo (ms) | WAND+CL (ms) | BMW (ms) | Speedup WAND+CL | Poda % |
|---|---|---|---|---|---|
| 5000 | 0.377 | 0.43 | 0.697 | 0.88x | 74.6 |
| 10000 | 0.737 | 0.808 | 1.136 | 0.91x | 78.0 |
| 20000 | 1.526 | 0.913 | 1.259 | 1.67x | 89.5 |
| 40000 | 2.917 | 1.533 | 2.016 | 1.9x | 91.6 |
| 80000 | 6.813 | 3.218 | 4.06 | 2.12x | 93.0 |
| 105957 | 10.134 | 4.311 | 6.593 | 2.35x | 93.2 |
