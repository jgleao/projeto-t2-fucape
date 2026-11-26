"""Pre-processamento de texto em portugues: normalizacao, tokenizacao, stopwords e
reducao leve de plural (inspirada na etapa de plural do stemmer RSLP)."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset("""
a ao aos aquela aquelas aquele aqueles aquilo as ate com como da das de dela delas dele deles depois
do dos e ela elas ele eles em entre era eram essa essas esse esses esta estas este estes eu foi foram
ha isso isto ja la lhe lhes mais mas me mesmo meu meus minha minhas na nas no nos nossa nosso num numa o os
ou para pela pelas pelo pelos por qual quando que quem se sem seu seus sua suas so tambem te tem tu
tua tuas um uma umas uns voce voces vos eh pra pro pq q vc vcs ai la ne tipo
""".split())


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def normalizar(texto: str) -> str:
    return remover_acentos(texto.lower())


def tokens_superficie(texto: str) -> list[str]:
    """Tokens normalizados, sem stopwords e sem reducao (usados na correcao ortografica)."""
    return [t for t in _TOKEN_RE.findall(normalizar(texto)) if len(t) > 1 and t not in STOPWORDS]


@lru_cache(maxsize=200_000)
def reduzir(token: str) -> str:
    """Reducao de plural: jogos->jogo, bons->bom, melhores->melhor, missoes->missao."""
    if len(token) <= 3 or token.isdigit():
        return token
    if token.endswith(("oes", "aes")) and len(token) > 4:
        return token[:-3] + "ao"
    if token.endswith("ais") and len(token) > 4:
        return token[:-3] + "al"
    if token.endswith("eis") and len(token) > 4:
        return token[:-3] + "el"
    if token.endswith("ois") and len(token) > 4:
        return token[:-3] + "ol"
    if token.endswith(("res", "zes")) and len(token) > 4:
        return token[:-2]
    if token.endswith("ns"):
        return token[:-2] + "m"
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def analisar(texto: str) -> list[str]:
    """Pipeline completo usado na indexacao e nas consultas."""
    return [reduzir(t) for t in tokens_superficie(texto)]
