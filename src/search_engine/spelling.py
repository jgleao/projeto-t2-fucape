"""Busca tolerante a erros de digitacao, em 2 estagios.

Estagio 1 (triagem rapida)
* Trie do vocabulario: autocompletar de prefixos em O(|P|). Cada no guarda,
  pre-calculadas na construcao, as palavras mais frequentes abaixo dele, entao
  a sugestao sai em O(|P|) sem percorrer a subarvore.
* Indice secundario de k-gramas de caracteres (bigramas com marcadores de
  borda "$"): seleciona candidatos que compartilham k-gramas com a palavra
  digitada e os filtra pelo coeficiente de Jaccard.

Estagio 2 (refinamento)
* Distancia de edicao de Levenshtein por Programacao Dinamica (matriz completa)
  apenas sobre os candidatos pre-selecionados.

Linha de base: a mesma matriz de Levenshtein aplicada a TODO o vocabulario.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable

from src.search_engine.text import _TOKEN_RE, STOPWORDS, normalizar, tokens_superficie


def levenshtein(a: str, b: str) -> int:
    """Distancia de edicao (insercao, remocao, substituicao = custo 1) via matriz DP."""
    m, n = len(a), len(b)
    matriz = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        matriz[i][0] = i
    for j in range(n + 1):
        matriz[0][j] = j
    for i in range(1, m + 1):
        ai = a[i - 1]
        linha, anterior = matriz[i], matriz[i - 1]
        for j in range(1, n + 1):
            custo = 0 if ai == b[j - 1] else 1
            linha[j] = min(anterior[j] + 1, linha[j - 1] + 1, anterior[j - 1] + custo)
    return matriz[m][n]


def kgramas(palavra: str, k: int = 2) -> set[str]:
    marcada = f"${palavra}$"
    return {marcada[i:i + k] for i in range(len(marcada) - k + 1)}


class NoTrie:
    __slots__ = ("filhos", "fim", "melhores")

    def __init__(self) -> None:
        self.filhos: dict[str, NoTrie] = {}
        self.fim = False
        self.melhores: list[str] = []


@dataclass
class Sugestao:
    palavra: str
    distancia: int
    frequencia: int


class CorretorOrtografico:
    def __init__(self, frequencias: Counter, k: int = 2, n_autocompletar: int = 8,
                 jaccard_min: float = 0.3, max_distancia: int = 2):
        self.freq = frequencias
        self.vocabulario = sorted(frequencias, key=lambda w: (-frequencias[w], w))
        self.k = k
        self.jaccard_min = jaccard_min
        self.max_distancia = max_distancia
        self.n_autocompletar = n_autocompletar
        self.raiz = NoTrie()
        self.indice_kgramas: dict[str, list[int]] = defaultdict(list)
        self.kgramas_palavra: list[int] = []
        self._construir()

    @classmethod
    def de_textos(cls, textos: Iterable[str], freq_minima: int = 2, **kwargs) -> "CorretorOrtografico":
        contagem: Counter = Counter()
        for texto in textos:
            contagem.update(tokens_superficie(texto))
        filtrado = Counter({w: c for w, c in contagem.items()
                            if c >= freq_minima and not w.isdigit() and 2 < len(w) <= 25})
        return cls(filtrado, **kwargs)

    def _construir(self) -> None:
        # vocabulario em ordem de frequencia decrescente -> as primeiras palavras
        # que chegam a cada no sao as mais frequentes daquele prefixo
        for idx, palavra in enumerate(self.vocabulario):
            no = self.raiz
            for ch in palavra:
                no = no.filhos.setdefault(ch, NoTrie())
                if len(no.melhores) < self.n_autocompletar:
                    no.melhores.append(palavra)
            no.fim = True
            gramas = kgramas(palavra, self.k)
            self.kgramas_palavra.append(len(gramas))
            for g in gramas:
                self.indice_kgramas[g].append(idx)

    # ------------------------------------------------------- autocompletar
    def autocompletar(self, prefixo: str) -> list[str]:
        no = self.raiz
        for ch in prefixo:
            no = no.filhos.get(ch)
            if no is None:
                return []
        return list(no.melhores)

    def existe(self, palavra: str) -> bool:
        return palavra in self.freq

    # ---------------------------------------------------- estagio 1 + 2
    def candidatos_kgrama(self, palavra: str) -> list[str]:
        gramas = kgramas(palavra, self.k)
        intersecao: Counter = Counter()
        for g in gramas:
            for idx in self.indice_kgramas.get(g, ()):
                intersecao[idx] += 1
        n = len(gramas)
        alvo = len(palavra)
        selecionados = []
        for idx, comum in intersecao.items():
            jaccard = comum / (n + self.kgramas_palavra[idx] - comum)
            if jaccard >= self.jaccard_min and abs(len(self.vocabulario[idx]) - alvo) <= self.max_distancia:
                selecionados.append(self.vocabulario[idx])
        return selecionados

    def _ranquear(self, palavra: str, candidatos: Iterable[str], n: int) -> list[Sugestao]:
        sugestoes = []
        for cand in candidatos:
            d = levenshtein(palavra, cand)
            if d <= self.max_distancia:
                sugestoes.append(Sugestao(cand, d, self.freq[cand]))
        sugestoes.sort(key=lambda s: (s.distancia, -s.frequencia, s.palavra))
        return sugestoes[:n]

    def corrigir(self, palavra: str, n: int = 5) -> tuple[list[Sugestao], int]:
        """2 estagios. Retorna (sugestoes, candidatos avaliados com Levenshtein)."""
        candidatos = self.candidatos_kgrama(palavra)
        return self._ranquear(palavra, candidatos, n), len(candidatos)

    def corrigir_forca_bruta(self, palavra: str, n: int = 5) -> tuple[list[Sugestao], int]:
        """Linha de base: Levenshtein contra o vocabulario inteiro."""
        return self._ranquear(palavra, self.vocabulario, n), len(self.vocabulario)

    def corrigir_consulta(self, consulta: str, conhecida: Callable[[str], bool] | None = None
                          ) -> tuple[str, list[tuple[str, str]]]:
        """'Voce quis dizer': troca palavras fora do vocabulario pela melhor sugestao.

        `conhecida` permite consultar um vocabulario maior (ex.: o do indice invertido),
        para nao "corrigir" uma palavra rara que existe no corpus."""
        trocas = []
        saida = []
        for token in _TOKEN_RE.findall(normalizar(consulta)):
            if (self.existe(token) or len(token) <= 3 or token in STOPWORDS or token.isdigit()
                    or (conhecida is not None and conhecida(token))):
                saida.append(token)
                continue
            sugestoes, _ = self.corrigir(token, 1)
            if sugestoes and sugestoes[0].palavra != token:
                trocas.append((token, sugestoes[0].palavra))
                saida.append(sugestoes[0].palavra)
            else:
                saida.append(token)
        return " ".join(saida), trocas
