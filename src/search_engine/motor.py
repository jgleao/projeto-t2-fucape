"""Fachada do motor de busca usada pelo painel: indexa o corpus do DW uma vez e
responde consultas com cronometragem do baseline e das versoes otimizadas."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.search_engine.baseline import ResultadoBusca, busca_exaustiva
from src.search_engine.benchmark import delta_pct, speedup
from src.search_engine.index import IndiceInvertido
from src.search_engine.optimized import ALGORITMOS as OTIMIZADOS
from src.search_engine.spelling import CorretorOrtografico
from src.search_engine.text import reduzir


@dataclass
class RespostaBusca:
    consulta_original: str
    consulta_usada: str
    correcoes: list[tuple[str, str]]
    resultado: ResultadoBusca
    baseline: ResultadoBusca
    tempo_baseline_ms: float
    tempo_otimizado_ms: float
    tempo_correcao_ms: float
    docs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def delta_pct(self) -> float:
        return delta_pct(self.tempo_baseline_ms, self.tempo_otimizado_ms)

    @property
    def speedup(self) -> float:
        return speedup(self.tempo_baseline_ms, self.tempo_otimizado_ms)


class MotorBusca:
    def __init__(self, textos: list[str], metadados: list[dict[str, Any]]):
        t0 = time.perf_counter()
        self.textos = textos
        self.indice = IndiceInvertido.construir(textos, metadados)
        t1 = time.perf_counter()
        self.corretor = CorretorOrtografico.de_textos(textos)
        t2 = time.perf_counter()
        self.tempo_indexacao_s = t1 - t0
        self.tempo_corretor_s = t2 - t1

    def buscar(self, consulta: str, k: int = 10, algoritmo: str = "wand_campeoes",
               corrigir: bool = True, repeticoes: int = 3) -> RespostaBusca:
        t0 = time.perf_counter()
        no_indice = lambda t: reduzir(t) in self.indice.postagens  # noqa: E731
        usada, correcoes = (self.corretor.corrigir_consulta(consulta, no_indice) if corrigir else (consulta, []))
        t_corr = (time.perf_counter() - t0) * 1000
        if not correcoes:
            usada = consulta

        fn = OTIMIZADOS[algoritmo]
        tempos_base, tempos_opt = [], []
        base = otimo = None
        for _ in range(repeticoes):   # alterna as execucoes para medir nas mesmas condicoes
            t = time.perf_counter()
            base = busca_exaustiva(self.indice, usada, k)
            tempos_base.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            otimo = fn(self.indice, usada, k)
            tempos_opt.append((time.perf_counter() - t) * 1000)

        docs = []
        for doc_id, score in otimo.top:
            meta = dict(self.indice.metadados[doc_id])
            meta.update({"doc_id": doc_id, "score": score, "texto": self.textos[doc_id]})
            docs.append(meta)
        return RespostaBusca(consulta, usada, correcoes, otimo, base,
                             min(tempos_base), min(tempos_opt), t_corr, docs)
