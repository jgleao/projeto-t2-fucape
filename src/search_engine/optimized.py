"""Solucao otimizada (DEPOIS): Top-K com poda dinamica segura.

WAND (Weak AND - Broder et al., 2003)
-------------------------------------
Processamento documento-a-documento (DAAT). Cada termo tem um cursor sobre sua
lista de postagens e um limite superior UB(t) = maior contribuicao BM25 que ele
pode dar a qualquer documento. Um Min-Heap guarda os K melhores ate agora; o
limiar theta e o menor score do heap (o K-esimo melhor).

A cada passo:
1. ordena os cursores pelo doc_id atual;
2. soma os UB na ordem ate a soma passar de theta -> o cursor onde isso
   acontece e o PIVO, e seu doc_id e o primeiro documento que ainda pode
   entrar no Top-K;
3. se o primeiro cursor ja esta no pivo, pontua o documento por completo;
   senao, avanca os cursores anteriores direto ate o pivo com busca binaria,
   pulando as postagens intermediarias sem calcular score.
Documentos antes do pivo tem score <= soma dos UB anteriores <= theta, entao
nunca entrariam no heap: a poda e segura (mesmo Top-K do exaustivo).

Champion Lists para aquecer o heap
----------------------------------
O WAND classico comeca com theta = 0 e pontua quase tudo ate o heap encher.
Antes de varrer as listas, pontuamos exatamente os melhores candidatos das
Champion Lists (os r postings de maior impacto de cada termo). O heap ja nasce
com K documentos reais, entao theta comeca alto e a poda age desde o inicio.
Como theta vem de scores exatos de documentos reais, a seguranca continua
valendo.

Block-Max WAND (Ding & Suel, 2011)
----------------------------------
Refina o WAND com limites por bloco de 64 postagens. Depois de achar o pivo,
soma os maximos dos BLOCOS que contem o pivo; se essa soma nao passa de theta,
nenhum documento ate o fim desses blocos pode entrar no Top-K, e o algoritmo
pula o intervalo inteiro, mesmo quando o UB global ainda permitiria.
"""

from __future__ import annotations

import heapq
from bisect import bisect_left
from heapq import heappush, heapreplace
from operator import itemgetter
from typing import Any

from src.search_engine.baseline import ResultadoBusca
from src.search_engine.index import IndiceInvertido

# Campos do cursor (lista mutavel = acesso rapido em Python puro); IDX = posicao do termo na consulta
DOC, POS, DOCS, TFS, IDF, UB, LEN, BLK, BULT, BMAX, IDX = range(11)
# Folga numerica da poda: so descarta quando o limite superior fica ABAIXO de theta por
# mais que EPS. Assim um documento empatado com o K-esimo (que pode vencer pelo
# desempate por menor doc_id) nunca e podado, e arredondamentos de ponto flutuante
# na soma dos limites nao tornam a poda insegura.
EPS = 1e-9
_POR_DOC = itemgetter(DOC)
FATOR_CANDIDATOS = 3   # pontua exatamente FATOR * K candidatos vindos das champion lists


def _cursores(indice: IndiceInvertido, termos: list[str]) -> list[list]:
    cursores = []
    for idx, termo in enumerate(termos):
        p = indice.postagens[termo]
        cursores.append([p.docs[0], 0, p.docs, p.tfs, p.idf, p.limite, len(p.docs), 0,
                         p.bloco_ultimo, p.bloco_max, idx])
    return cursores


def _ordenar_top(heap: list[tuple[float, int]]) -> list[tuple[int, float]]:
    return [(-neg_doc, score) for score, neg_doc in sorted(heap, key=lambda x: (-x[0], -x[1]))]


def _empurrar(heap: list, k: int, score: float, doc: int, theta: float) -> float:
    """Insere no Min-Heap Top-K e devolve o novo limiar theta.

    A ordem e a mesma do baseline: score maior primeiro e, no empate, menor doc_id.
    O heap guarda (score, -doc); heap[0] e o pior documento do Top-K."""
    item = (score, -doc)
    if len(heap) < k:
        heappush(heap, item)
        return heap[0][0] if len(heap) == k else 0.0
    if item > heap[0]:
        heapreplace(heap, item)
        return heap[0][0]
    return theta


def _aquecer_com_campeoes(indice: IndiceInvertido, termos: list[str], k: int,
                          heap: list) -> tuple[float, set[int], int]:
    """Pontua exatamente os melhores candidatos das champion lists e enche o heap."""
    parcial: dict[int, float] = {}
    get = parcial.get
    for termo in termos:
        for d, s in indice.postagens[termo].campeoes:
            parcial[d] = get(d, 0.0) + s
    candidatos = heapq.nlargest(FATOR_CANDIDATOS * k, parcial, key=parcial.__getitem__)
    theta = 0.0
    listas = [indice.postagens[t] for t in termos]
    norm, k1p = indice.norm, indice.k1 + 1
    for d in candidatos:
        score = 0.0
        for lista in listas:                 # score exato: busca binaria em cada lista
            pos = bisect_left(lista.docs, d)
            if pos < len(lista.docs) and lista.docs[pos] == d:
                tf = lista.tfs[pos]
                score += lista.idf * tf * k1p / (tf + norm[d])
        theta = _empurrar(heap, k, score, d, theta)
    return theta, set(candidatos), len(candidatos)


def _wand(indice: IndiceInvertido, consulta: str, k: int, usar_blocos: bool, aquecer: bool,
          nome: str) -> ResultadoBusca:
    termos = indice.termos_consulta(consulta)
    if not termos or k <= 0:
        return ResultadoBusca(nome, termos, [], {"docs_pontuados": 0, "postagens_pontuadas": 0})
    fim = indice.n_docs                      # sentinela: cursor esgotado
    norm, k1p = indice.norm, indice.k1 + 1
    cursores = _cursores(indice, termos)
    n_cursores = len(cursores)
    total_postagens = sum(c[LEN] for c in cursores)
    heap: list[tuple[float, int]] = []
    theta, ja_pontuados, aquecidos = 0.0, set(), 0
    if aquecer:
        theta, ja_pontuados, aquecidos = _aquecer_com_campeoes(indice, termos, k, heap)
    avaliados = postagens = pivos = saltos = saltos_bloco = 0

    while True:
        cursores.sort(key=_POR_DOC)
        acumulado = 0.0
        pivo = -1
        for i in range(n_cursores):
            c = cursores[i]
            if c[DOC] >= fim:
                break
            acumulado += c[UB]
            if acumulado + EPS >= theta:
                pivo = i
                break
        if pivo < 0:
            break                            # nenhum documento restante supera theta
        pivos += 1
        doc_pivo = cursores[pivo][DOC]

        if usar_blocos and len(heap) == k:
            ultimo = pivo                    # inclui cursores empatados no pivo
            while ultimo + 1 < n_cursores and cursores[ultimo + 1][DOC] == doc_pivo:
                ultimo += 1
            soma_blocos = 0.0
            proximo = cursores[ultimo + 1][DOC] if ultimo + 1 < n_cursores else fim
            for c in cursores[:ultimo + 1]:  # "shallow move": so o ponteiro de bloco anda
                blk = bisect_left(c[BULT], doc_pivo, c[BLK])
                c[BLK] = blk
                if blk == len(c[BULT]):
                    continue                 # lista termina antes do pivo: contribui 0
                soma_blocos += c[BMAX][blk]
                if c[BULT][blk] + 1 < proximo:
                    proximo = c[BULT][blk] + 1
            if soma_blocos + EPS < theta:
                # nenhum documento em [doc_pivo, proximo) entra no Top-K: salta o intervalo
                saltos_bloco += 1
                for c in cursores[:ultimo + 1]:
                    if c[DOC] < proximo:
                        pos = bisect_left(c[DOCS], proximo, c[POS])
                        saltos += pos - c[POS]
                        c[POS] = pos
                        c[DOC] = c[DOCS][pos] if pos < c[LEN] else fim
                continue

        if cursores[0][DOC] == doc_pivo:
            repetido = doc_pivo in ja_pontuados
            partes = []
            for c in cursores:
                if c[DOC] != doc_pivo:
                    break
                if not repetido:
                    tf = c[TFS][c[POS]]
                    partes.append((c[IDX], c[IDF] * tf * k1p / (tf + norm[doc_pivo])))
                c[POS] += 1
                c[DOC] = c[DOCS][c[POS]] if c[POS] < c[LEN] else fim
            if not repetido:
                # soma na ORDEM DOS TERMOS, como o baseline: mesmo float, bit a bit
                if len(partes) > 1:
                    partes.sort()
                score = 0.0
                for _, contribuicao in partes:
                    score += contribuicao
                postagens += len(partes)
                avaliados += 1
                theta = _empurrar(heap, k, score, doc_pivo, theta)
        else:
            for c in cursores[:pivo]:
                if c[DOC] < doc_pivo:
                    pos = bisect_left(c[DOCS], doc_pivo, c[POS] + 1)
                    saltos += pos - c[POS]
                    c[POS] = pos
                    c[DOC] = c[DOCS][pos] if pos < c[LEN] else fim

    stats: dict[str, Any] = {
        "docs_pontuados": avaliados + aquecidos, "postagens_pontuadas": postagens,
        "postagens_total": total_postagens, "postagens_saltadas": saltos, "pivos": pivos,
        "saltos_de_bloco": saltos_bloco, "aquecidos_por_campeoes": aquecidos,
    }
    return ResultadoBusca(nome, termos, _ordenar_top(heap), stats)


def busca_wand(indice: IndiceInvertido, consulta: str, k: int = 10) -> ResultadoBusca:
    """WAND classico (theta comeca em zero)."""
    return _wand(indice, consulta, k, usar_blocos=False, aquecer=False, nome="WAND")


def busca_wand_campeoes(indice: IndiceInvertido, consulta: str, k: int = 10) -> ResultadoBusca:
    """WAND + Champion Lists + Min-Heap Top-K (solucao principal)."""
    return _wand(indice, consulta, k, usar_blocos=False, aquecer=True, nome="WAND + Champion Lists")


def busca_block_max_wand(indice: IndiceInvertido, consulta: str, k: int = 10) -> ResultadoBusca:
    """Block-Max WAND + Champion Lists."""
    return _wand(indice, consulta, k, usar_blocos=True, aquecer=True, nome="Block-Max WAND")


ALGORITMOS = {
    "wand": busca_wand,
    "wand_campeoes": busca_wand_campeoes,
    "bmw": busca_block_max_wand,
}
