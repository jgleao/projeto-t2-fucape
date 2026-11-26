"""Motor de busca textual (PLN & RI) sobre as reviews do Data Warehouse.

* index.py      - indice invertido BM25 com limites superiores por termo e por bloco
* baseline.py   - linha de base: BM25 exaustivo (pontua todos os documentos e ordena tudo)
* optimized.py  - WAND e Block-Max WAND com Min-Heap Top-K (poda dinamica segura)
* spelling.py   - correcao ortografica em 2 estagios (Trie + k-gramas/Jaccard + Levenshtein)
* benchmark.py  - cronometragem (perf_counter), memoria (tracemalloc) e taxa de poda
"""
