"""Linha de base (ANTES): ranqueamento BM25 exaustivo.

busca_exaustiva  - o baseline exigido: calcula o score BM25 de TODOS os N documentos
                   da base (acumuladores densos), ordena os N e so entao corta o Top-K.
                   Custo: O(postagens) + O(N log N) e memoria O(N) por consulta.
busca_taat_heap  - variante intermediaria (ablacao): pontua todas as postagens
                   (term-at-a-time), mas extrai o Top-K com heap. Isola quanto do
                   ganho vem do heap e quanto vem da poda do WAND.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from src.search_engine.index import IndiceInvertido


@dataclass
class ResultadoBusca:
    algoritmo: str
    termos: list[str]
    top: list[tuple[int, float]]                 # (doc_id, score), score decrescente
    stats: dict[str, Any] = field(default_factory=dict)


def busca_exaustiva(indice: IndiceInvertido, consulta: str, k: int = 10) -> ResultadoBusca:
    termos = indice.termos_consulta(consulta)
    n = indice.n_docs
    scores = [0.0] * n                     # um acumulador para cada documento da base
    norm, k1p = indice.norm, indice.k1 + 1
    postagens = 0
    for termo in termos:
        lista = indice.postagens[termo]
        idf = lista.idf
        for d, tf in zip(lista.docs, lista.tfs):
            scores[d] += idf * tf * k1p / (tf + norm[d])
        postagens += len(lista.docs)
    ordem = sorted(range(n), key=scores.__getitem__, reverse=True)   # ordena a base inteira
    top = [(d, scores[d]) for d in ordem[:k] if scores[d] > 0]
    return ResultadoBusca("BM25 exaustivo", termos, top, {
        "docs_pontuados": n, "postagens_pontuadas": postagens, "postagens_total": postagens,
        "docs_ordenados": n,
    })


def busca_taat_heap(indice: IndiceInvertido, consulta: str, k: int = 10) -> ResultadoBusca:
    termos = indice.termos_consulta(consulta)
    acumuladores: dict[int, float] = {}
    norm, k1p = indice.norm, indice.k1 + 1
    get = acumuladores.get
    postagens = 0
    for termo in termos:
        lista = indice.postagens[termo]
        idf = lista.idf
        for d, tf in zip(lista.docs, lista.tfs):
            acumuladores[d] = get(d, 0.0) + idf * tf * k1p / (tf + norm[d])
        postagens += len(lista.docs)
    # mesmo desempate do exaustivo: score maior e, no empate, menor doc_id
    top = heapq.nlargest(k, acumuladores.items(), key=lambda par: (par[1], -par[0]))
    return ResultadoBusca("TAAT + heap", termos, top, {
        "docs_pontuados": len(acumuladores), "postagens_pontuadas": postagens, "postagens_total": postagens,
        "candidatos": len(acumuladores),
    })
