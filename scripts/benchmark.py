"""Benchmark completo ANTES vs. DEPOIS, com saida em Markdown e JSON.

Uso (na raiz do projeto, com o DW de pe):
    python -m scripts.benchmark                    # corpus real do Data Warehouse
    python -m scripts.benchmark --fonte sintetico  # sem banco (corpus Zipf deterministico)

Gera docs/resultados_benchmark.md e docs/resultados_benchmark.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

from src.search_engine.benchmark import (CONSULTAS_PADRAO, ERROS_PADRAO, benchmark_ortografia,
                                         benchmark_ranking)
from src.search_engine.index import IndiceInvertido
from src.search_engine.spelling import CorretorOrtografico

RAIZ = Path(__file__).resolve().parents[1]


def carregar(fonte: str, n_docs: int) -> tuple[list[str], str]:
    if fonte == "dw":
        from src.search_engine.corpus import carregar_corpus
        textos, _ = carregar_corpus()
        return textos, "Data Warehouse (dw.dim_review, reviews reais da Steam)"
    from src.search_engine.sintetico import gerar_corpus
    return gerar_corpus(n_docs), f"Corpus sintetico Zipf ({n_docs} documentos, semente 42)"


def experimento_escala(textos: list[str], repeticoes: int, k: int) -> list[dict]:
    linhas = []
    n_total = len(textos)
    tamanhos = sorted({n for n in (5_000, 10_000, 20_000, 40_000, 80_000) if n < n_total} | {n_total})
    for n in tamanhos:
        indice = IndiceInvertido.construir(textos[:n])
        _, resumo = benchmark_ranking(indice, CONSULTAS_PADRAO, k, repeticoes)
        linhas.append({"documentos": n, **resumo})
        print(f"  escala N={n}: exaustivo {resumo['exaustivo_ms_medio']} ms | "
              f"WAND+CL {resumo['wand_campeoes_ms_medio']} ms ({resumo['wand_campeoes_speedup']}x)")
    return linhas


def tabela_md(cabecalho: list[str], linhas: list[list]) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join(["---"] * len(cabecalho)) + "|"]
    saida += ["| " + " | ".join(str(c) for c in ln) + " |" for ln in linhas]
    return "\n".join(saida)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fonte", choices=["dw", "sintetico"], default="dw")
    parser.add_argument("--n-docs", type=int, default=40_000, help="tamanho do corpus sintetico")
    parser.add_argument("--repeticoes", type=int, default=7)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--sem-escala", action="store_true", help="pula o experimento de escalabilidade")
    args = parser.parse_args()

    textos, descricao = carregar(args.fonte, args.n_docs)
    print(f"Corpus: {descricao} -> {len(textos)} documentos")
    t0 = time.perf_counter()
    indice = IndiceInvertido.construir(textos)
    t_idx = time.perf_counter() - t0
    t0 = time.perf_counter()
    corretor = CorretorOrtografico.de_textos(textos)
    t_corr = time.perf_counter() - t0
    stats = indice.estatisticas()
    print(f"Indice: {stats} em {t_idx:.1f}s | vocabulario ortografico {len(corretor.vocabulario)}")

    linhas, resumo = benchmark_ranking(indice, CONSULTAS_PADRAO, args.k, args.repeticoes)
    linhas_ort, resumo_ort = benchmark_ortografia(corretor, ERROS_PADRAO, max(3, args.repeticoes // 2))
    escala = [] if args.sem_escala else experimento_escala(textos, max(3, args.repeticoes // 2), args.k)

    ambiente = {"python": sys.version.split()[0], "so": platform.platform(), "cpu": platform.processor(),
                "gerado_em": datetime.now().isoformat(timespec="seconds")}
    saida_json = {"corpus": descricao, "ambiente": ambiente, "indice": stats,
                  "tempo_indexacao_s": round(t_idx, 2), "tempo_corretor_s": round(t_corr, 2),
                  "ranking": {"resumo": resumo, "consultas": linhas},
                  "ortografia": {"resumo": resumo_ort, "palavras": linhas_ort}, "escala": escala}
    (RAIZ / "docs").mkdir(exist_ok=True)
    (RAIZ / "docs" / "resultados_benchmark.json").write_text(
        json.dumps(saida_json, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    md = [f"# Resultados do Benchmark (gerado por `python -m scripts.benchmark --fonte {args.fonte}`)", "",
          f"* **Corpus:** {descricao}",
          f"* **Indice:** {stats['documentos']} documentos, {stats['vocabulario']} termos, "
          f"{stats['postagens']} postagens (indexado em {t_idx:.1f}s)",
          f"* **Ambiente:** Python {ambiente['python']} - {ambiente['so']} - {ambiente['gerado_em']}",
          f"* **Metodo:** media de {args.repeticoes} execucoes com `time.perf_counter()`, 1 aquecimento, "
          f"GC desligado durante a medicao, K = {args.k}.", "",
          "## 1. Ranqueamento Top-K (BM25)", "",
          tabela_md(["Consulta", "Candidatos", "Exaustivo (ms)", "TAAT+heap (ms)", "WAND (ms)",
                     "WAND+CL (ms)", "BMW (ms)", "Delta % (WAND+CL)", "Speedup", "Poda docs %",
                     "Top-K identico"],
                    [[ln["consulta"], ln["candidatos"], ln["exaustivo_ms"], ln["taat_heap_ms"], ln["wand_ms"],
                      ln["wand_campeoes_ms"], ln["bmw_ms"], ln["wand_campeoes_delta_pct"],
                      f"{ln['wand_campeoes_speedup']}x", ln["wand_campeoes_poda_docs_pct"],
                      "sim" if ln["wand_campeoes_mesmo_topk"] and ln["bmw_mesmo_topk"] else "NAO"]
                     for ln in linhas]), "",
          "**Resumo**", "",
          tabela_md(["Algoritmo", "Tempo medio (ms)", "Delta %", "Speedup", "Poda docs %", "Memoria/consulta (KB)"], [
              ["BM25 exaustivo (baseline)", resumo["exaustivo_ms_medio"], "-", "1.0x", "0", resumo.get("exaustivo_mem_kb_medio")],
              ["TAAT + heap (ablacao)", resumo["taat_heap_ms_medio"], resumo["taat_heap_delta_pct"],
               f"{resumo['taat_heap_speedup']}x", "0", "-"],
              ["WAND", resumo["wand_ms_medio"], resumo["wand_delta_pct"], f"{resumo['wand_speedup']}x",
               resumo["wand_poda_docs_pct"], resumo.get("wand_mem_kb_medio")],
              ["**WAND + Champion Lists**", f"**{resumo['wand_campeoes_ms_medio']}**",
               f"**{resumo['wand_campeoes_delta_pct']}**", f"**{resumo['wand_campeoes_speedup']}x**",
               resumo["wand_campeoes_poda_docs_pct"], resumo.get("wand_campeoes_mem_kb_medio")],
              ["Block-Max WAND", resumo["bmw_ms_medio"], resumo["bmw_delta_pct"], f"{resumo['bmw_speedup']}x",
               resumo["bmw_poda_docs_pct"], resumo.get("bmw_mem_kb_medio")],
          ]), "",
          f"Top-K identico ao exaustivo em todas as consultas: WAND+CL = {resumo['wand_campeoes_topk_identico']}, "
          f"BMW = {resumo['bmw_topk_identico']}.", "",
          "## 2. Correcao ortografica (2 estagios vs. forca bruta)", "",
          tabela_md(["Digitado", "Forca bruta (ms)", "2 estagios (ms)", "Delta %", "Speedup",
                     "Candidatos Levenshtein", "Reducao %", "Sugestao", "Mesma sugestao"],
                    [[ln["digitado"], ln["forca_bruta_ms"], ln["dois_estagios_ms"], ln["delta_pct"],
                      f"{ln['speedup']}x", f"{ln['candidatos_levenshtein']} / {ln['vocabulario']}",
                      ln["reducao_candidatos_pct"], ln["sugestao_dois_estagios"],
                      "sim" if ln["mesma_sugestao"] else "nao"] for ln in linhas_ort]), "",
          f"**Resumo:** forca bruta {resumo_ort['forca_bruta_ms_medio']} ms vs. 2 estagios "
          f"{resumo_ort['dois_estagios_ms_medio']} ms -> Delta {resumo_ort['delta_pct']}% "
          f"({resumo_ort['speedup']}x), concordancia {resumo_ort['concordancia_pct']}%, "
          f"autocompletar (Trie) {resumo_ort['autocompletar_ms_medio']} ms.", ""]
    if escala:
        md += ["## 3. Escalabilidade (o ganho cresce com o tamanho da base)", "",
               tabela_md(["Documentos", "Exaustivo (ms)", "WAND+CL (ms)", "BMW (ms)", "Speedup WAND+CL",
                          "Poda %"],
                         [[e["documentos"], e["exaustivo_ms_medio"], e["wand_campeoes_ms_medio"], e["bmw_ms_medio"],
                           f"{e['wand_campeoes_speedup']}x", e["wand_campeoes_poda_docs_pct"]] for e in escala]), ""]
    (RAIZ / "docs" / "resultados_benchmark.md").write_text("\n".join(md), encoding="utf-8")
    print("\nResumo ranking:", json.dumps(resumo, ensure_ascii=False))
    print("Resumo ortografia:", json.dumps(resumo_ort, ensure_ascii=False))
    print("Arquivos: docs/resultados_benchmark.md e docs/resultados_benchmark.json")


if __name__ == "__main__":
    main()
