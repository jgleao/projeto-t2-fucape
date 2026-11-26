"""Indice invertido para BM25 com os metadados que a poda dinamica exige.

Para cada termo t guardamos:
* lista de postagens ordenada por doc_id (docs) e frequencias (tfs);
* idf(t) do BM25 (variante sempre positiva do Lucene);
* limite superior global UB(t) = max_d score_BM25(t, d)            -> usado pelo WAND;
* limites por bloco de B postagens: ultimo doc_id do bloco e o maior
  score do bloco                                                     -> usado pelo Block-Max WAND.

Os limites sao calculados de forma EXATA na indexacao, o que garante que a
poda e segura: o Top-K podado e identico ao Top-K exaustivo.
"""

from __future__ import annotations

import heapq
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from src.search_engine.text import analisar

TAMANHO_BLOCO = 64
TAMANHO_CAMPEOES = 64


@dataclass
class ListaPostagens:
    docs: list[int]
    tfs: list[int]
    idf: float
    limite: float = 0.0                                  # UB(t) global
    bloco_ultimo: list[int] = field(default_factory=list)  # ultimo doc_id de cada bloco
    bloco_max: list[float] = field(default_factory=list)   # maior score de cada bloco
    # Champion list: os r documentos de maior impacto do termo (doc_id, score)
    campeoes: list[tuple[int, float]] = field(default_factory=list)


class IndiceInvertido:
    def __init__(self, k1: float = 1.2, b: float = 0.75, tamanho_bloco: int = TAMANHO_BLOCO,
                 tamanho_campeoes: int = TAMANHO_CAMPEOES):
        self.k1 = k1
        self.b = b
        self.tamanho_bloco = tamanho_bloco
        self.tamanho_campeoes = tamanho_campeoes
        self.postagens: dict[str, ListaPostagens] = {}
        self.tam_doc: list[int] = []
        self.norm: list[float] = []   # k1 * (1 - b + b * |d| / avgdl), pre-calculado por documento
        self.metadados: list[dict[str, Any]] = []
        self.n_docs = 0
        self.media_tam = 0.0

    # --------------------------------------------------------------- build
    @classmethod
    def construir(cls, textos: Iterable[str], metadados: Sequence[dict[str, Any]] | None = None,
                  **kwargs: Any) -> "IndiceInvertido":
        indice = cls(**kwargs)
        indice._construir(textos, metadados)
        return indice

    def _construir(self, textos: Iterable[str], metadados: Sequence[dict[str, Any]] | None) -> None:
        bruto: dict[str, tuple[list[int], list[int]]] = {}
        for doc_id, texto in enumerate(textos):
            contagem = Counter(analisar(texto))
            self.tam_doc.append(sum(contagem.values()))
            for termo, tf in contagem.items():
                par = bruto.get(termo)
                if par is None:
                    bruto[termo] = ([doc_id], [tf])
                else:
                    par[0].append(doc_id)
                    par[1].append(tf)
        self.n_docs = len(self.tam_doc)
        self.metadados = list(metadados) if metadados is not None else [{} for _ in range(self.n_docs)]
        self.media_tam = (sum(self.tam_doc) / self.n_docs) if self.n_docs else 0.0
        media = self.media_tam or 1.0
        self.norm = [self.k1 * (1 - self.b + self.b * tam / media) for tam in self.tam_doc]

        k1p = self.k1 + 1
        bloco = self.tamanho_bloco
        for termo, (docs, tfs) in bruto.items():
            df = len(docs)
            idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            lista = ListaPostagens(docs, tfs, idf)
            norm = self.norm
            scores = [idf * tf * k1p / (tf + norm[d]) for d, tf in zip(docs, tfs)]
            lista.limite = max(scores)
            for inicio in range(0, df, bloco):
                fim = min(inicio + bloco, df)
                lista.bloco_ultimo.append(docs[fim - 1])
                lista.bloco_max.append(max(scores[inicio:fim]))
            melhores = heapq.nlargest(self.tamanho_campeoes, range(df), key=scores.__getitem__)
            lista.campeoes = [(docs[i], scores[i]) for i in melhores]
            self.postagens[termo] = lista

    # -------------------------------------------------------------- query
    def termos_consulta(self, consulta: str) -> list[str]:
        """Termos unicos da consulta que existem no vocabulario."""
        vistos: list[str] = []
        for termo in analisar(consulta):
            if termo in self.postagens and termo not in vistos:
                vistos.append(termo)
        return vistos

    def score_documento(self, doc_id: int, termos: Sequence[str]) -> float:
        """Score BM25 de um documento (usado em testes e para explicar resultados)."""
        from bisect import bisect_left
        total, k1p = 0.0, self.k1 + 1
        for termo in termos:
            lista = self.postagens.get(termo)
            if not lista:
                continue
            pos = bisect_left(lista.docs, doc_id)
            if pos < len(lista.docs) and lista.docs[pos] == doc_id:
                tf = lista.tfs[pos]
                total += lista.idf * tf * k1p / (tf + self.norm[doc_id])
        return total

    # -------------------------------------------------------------- stats
    def estatisticas(self) -> dict[str, Any]:
        n_post = sum(len(p.docs) for p in self.postagens.values())
        n_blocos = sum(len(p.bloco_max) for p in self.postagens.values())
        # estimativa de memoria das estruturas de postagens (listas Python de int/float)
        ptr = 8
        bytes_post = sum(sys.getsizeof(p.docs) + sys.getsizeof(p.tfs) for p in self.postagens.values())
        bytes_blocos = n_blocos * 2 * ptr
        return {
            "documentos": self.n_docs,
            "vocabulario": len(self.postagens),
            "postagens": n_post,
            "blocos": n_blocos,
            "tamanho_medio_doc": round(self.media_tam, 1),
            "memoria_postagens_mb": round(bytes_post / 1024 ** 2, 2),
            "memoria_blocos_mb": round(bytes_blocos / 1024 ** 2, 2),
            "tamanho_bloco": self.tamanho_bloco,
        }
