"""Benchmark cronometrado ANTES vs. DEPOIS.

* Tempo: time.perf_counter() (alta resolucao), com aquecimento e N repeticoes;
  reporta media e mediana em milissegundos.
* Ganho: delta% = (T_baseline - T_otimizado) / T_baseline * 100 e speedup = T_baseline / T_otimizado.
* Poda: % de documentos candidatos (que contem ao menos um termo) que NAO
  precisaram ser pontuados e % de postagens nunca pontuadas.
* Memoria: pico alocado durante a consulta (tracemalloc), medido numa execucao
  separada para nao contaminar o tempo.
* Integridade: confere se o Top-K podado e identico ao exaustivo (poda segura).
"""

from __future__ import annotations

import gc
import statistics
import time
import tracemalloc
from typing import Any, Callable, Sequence

from src.search_engine.baseline import ResultadoBusca, busca_exaustiva, busca_taat_heap
from src.search_engine.index import IndiceInvertido
from src.search_engine.optimized import busca_block_max_wand, busca_wand, busca_wand_campeoes
from src.search_engine.spelling import CorretorOrtografico

CONSULTAS_PADRAO = [
    "jogo travando muito",
    "otimizacao ruim fps baixo",
    "historia emocionante personagens",
    "servidor lag multiplayer",
    "vale a pena comprar",
    "bugs crash fechando sozinho",
    "graficos lindos mundo aberto",
    "preco caro promocao",
    "jogar com amigos",
    "melhor jogo que ja joguei",
    "cheater hacker banido",
    "musica trilha sonora incrivel",
]

ERROS_PADRAO = [
    "trvando", "otimizaçao", "grafcos", "multiplayr", "servdor", "histporia",
    "personagen", "dificuldad", "jogablidade", "travamneto", "lagando", "emocionnte",
]

ALGORITMOS: dict[str, Callable[..., ResultadoBusca]] = {
    "exaustivo": busca_exaustiva,
    "taat_heap": busca_taat_heap,
    "wand": busca_wand,
    "wand_campeoes": busca_wand_campeoes,
    "bmw": busca_block_max_wand,
}

OTIMIZADOS = ("wand", "wand_campeoes", "bmw")
PRINCIPAL = "wand_campeoes"   # tecnica principal apresentada no painel


def cronometrar(fn: Callable[[], Any], repeticoes: int = 7, aquecimento: int = 1) -> list[float]:
    for _ in range(aquecimento):
        fn()
    tempos = []
    gc_estava = gc.isenabled()
    gc.disable()  # evita que uma coleta de lixo caia no meio de uma medicao
    try:
        for _ in range(repeticoes):
            t0 = time.perf_counter()
            fn()
            tempos.append((time.perf_counter() - t0) * 1000.0)
    finally:
        if gc_estava:
            gc.enable()
    return tempos


def pico_memoria_kb(fn: Callable[[], Any]) -> float:
    tracemalloc.start()
    try:
        fn()
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return pico / 1024


def delta_pct(base: float, otimizado: float) -> float:
    return (base - otimizado) / base * 100 if base > 0 else 0.0


def speedup(base: float, otimizado: float) -> float:
    return base / otimizado if otimizado > 0 else float("inf")


def mesmo_top(a: ResultadoBusca, b: ResultadoBusca, tol: float = 1e-12) -> bool:
    """Mesmos documentos, na mesma ordem, com os mesmos scores."""
    return len(a.top) == len(b.top) and all(
        da == db and abs(sa - sb) <= tol for (da, sa), (db, sb) in zip(a.top, b.top))


def benchmark_consulta(indice: IndiceInvertido, consulta: str, k: int = 10, repeticoes: int = 7,
                       medir_memoria: bool = True) -> dict[str, Any]:
    resultados = {nome: fn(indice, consulta, k) for nome, fn in ALGORITMOS.items()}
    tempos = {nome: cronometrar(lambda f=fn: f(indice, consulta, k), repeticoes)
              for nome, fn in ALGORITMOS.items()}
    media = {nome: statistics.fmean(t) for nome, t in tempos.items()}
    mediana = {nome: statistics.median(t) for nome, t in tempos.items()}
    candidatos = resultados["taat_heap"].stats["candidatos"]
    postagens = resultados["exaustivo"].stats["postagens_total"]

    linha: dict[str, Any] = {
        "consulta": consulta,
        "termos": len(resultados["exaustivo"].termos),
        "postagens_total": postagens,
        "candidatos": candidatos,
    }
    for nome in ALGORITMOS:
        linha[f"{nome}_ms"] = round(media[nome], 3)
        linha[f"{nome}_mediana_ms"] = round(mediana[nome], 3)
    for nome in ("taat_heap", *OTIMIZADOS):
        linha[f"{nome}_delta_pct"] = round(delta_pct(media["exaustivo"], media[nome]), 1)
        linha[f"{nome}_speedup"] = round(speedup(media["exaustivo"], media[nome]), 2)
    for nome in OTIMIZADOS:
        st = resultados[nome].stats
        linha[f"{nome}_docs_pontuados"] = st["docs_pontuados"]
        linha[f"{nome}_poda_docs_pct"] = round(
            (1 - st["docs_pontuados"] / candidatos) * 100 if candidatos else 0.0, 1)
        linha[f"{nome}_poda_postagens_pct"] = round(
            (1 - st["postagens_pontuadas"] / postagens) * 100 if postagens else 0.0, 1)
        linha[f"{nome}_mesmo_topk"] = mesmo_top(resultados["exaustivo"], resultados[nome])
    if medir_memoria:
        linha["exaustivo_mem_kb"] = round(pico_memoria_kb(lambda: busca_exaustiva(indice, consulta, k)), 1)
        for nome in OTIMIZADOS:
            fn = ALGORITMOS[nome]
            linha[f"{nome}_mem_kb"] = round(pico_memoria_kb(lambda f=fn: f(indice, consulta, k)), 1)
    return linha


def benchmark_ranking(indice: IndiceInvertido, consultas: Sequence[str] = CONSULTAS_PADRAO, k: int = 10,
                      repeticoes: int = 7) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    linhas = [benchmark_consulta(indice, q, k, repeticoes) for q in consultas]
    linhas = [ln for ln in linhas if ln["termos"] > 0]
    return linhas, resumir_ranking(linhas, k)


def resumir_ranking(linhas: list[dict[str, Any]], k: int) -> dict[str, Any]:
    if not linhas:
        return {}
    def soma(campo: str) -> float:
        return sum(ln[campo] for ln in linhas)
    resumo: dict[str, Any] = {"consultas": len(linhas), "k": k}
    for nome in ALGORITMOS:
        resumo[f"{nome}_ms_medio"] = round(soma(f"{nome}_ms") / len(linhas), 3)
    for nome in ("taat_heap", *OTIMIZADOS):
        resumo[f"{nome}_delta_pct"] = round(delta_pct(soma("exaustivo_ms"), soma(f"{nome}_ms")), 1)
        resumo[f"{nome}_speedup"] = round(speedup(soma("exaustivo_ms"), soma(f"{nome}_ms")), 2)
    for nome in OTIMIZADOS:
        resumo[f"{nome}_poda_docs_pct"] = round(
            (1 - soma(f"{nome}_docs_pontuados") / soma("candidatos")) * 100, 1)
        resumo[f"{nome}_topk_identico"] = all(ln[f"{nome}_mesmo_topk"] for ln in linhas)
    if "exaustivo_mem_kb" in linhas[0]:
        resumo["exaustivo_mem_kb_medio"] = round(soma("exaustivo_mem_kb") / len(linhas), 1)
        for nome in OTIMIZADOS:
            resumo[f"{nome}_mem_kb_medio"] = round(soma(f"{nome}_mem_kb") / len(linhas), 1)
    return resumo


def benchmark_ortografia(corretor: CorretorOrtografico, palavras: Sequence[str] = ERROS_PADRAO,
                         repeticoes: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from src.search_engine.text import normalizar
    linhas = []
    for bruta in palavras:
        palavra = normalizar(bruta)
        sug_bf, n_bf = corretor.corrigir_forca_bruta(palavra, 3)
        sug_2e, n_2e = corretor.corrigir(palavra, 3)
        t_bf = statistics.fmean(cronometrar(lambda: corretor.corrigir_forca_bruta(palavra, 3), repeticoes, 0))
        t_2e = statistics.fmean(cronometrar(lambda: corretor.corrigir(palavra, 3), repeticoes, 1))
        t_trie = statistics.fmean(cronometrar(lambda: corretor.autocompletar(palavra[:4]), 50, 5))
        top_bf = sug_bf[0].palavra if sug_bf else None
        top_2e = sug_2e[0].palavra if sug_2e else None
        linhas.append({
            "digitado": bruta,
            "forca_bruta_ms": round(t_bf, 3),
            "dois_estagios_ms": round(t_2e, 3),
            "delta_pct": round(delta_pct(t_bf, t_2e), 1),
            "speedup": round(speedup(t_bf, t_2e), 1),
            "vocabulario": n_bf,
            "candidatos_levenshtein": n_2e,
            "reducao_candidatos_pct": round((1 - n_2e / n_bf) * 100, 2) if n_bf else 0.0,
            "sugestao_forca_bruta": top_bf,
            "sugestao_dois_estagios": top_2e,
            "mesma_sugestao": top_bf == top_2e,
            "autocompletar_ms": round(t_trie, 4),
        })
    soma_bf = sum(ln["forca_bruta_ms"] for ln in linhas)
    soma_2e = sum(ln["dois_estagios_ms"] for ln in linhas)
    resumo = {
        "palavras": len(linhas),
        "forca_bruta_ms_medio": round(soma_bf / len(linhas), 3) if linhas else 0,
        "dois_estagios_ms_medio": round(soma_2e / len(linhas), 3) if linhas else 0,
        "delta_pct": round(delta_pct(soma_bf, soma_2e), 1),
        "speedup": round(speedup(soma_bf, soma_2e), 1),
        "concordancia_pct": round(100 * sum(ln["mesma_sugestao"] for ln in linhas) / len(linhas), 1)
        if linhas else 0,
        "autocompletar_ms_medio": round(sum(ln["autocompletar_ms"] for ln in linhas) / len(linhas), 4)
        if linhas else 0,
    }
    return linhas, resumo
