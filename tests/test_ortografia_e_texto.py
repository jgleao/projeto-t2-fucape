from collections import Counter

import pytest

from src.search_engine.spelling import CorretorOrtografico, kgramas, levenshtein
from src.search_engine.text import analisar, reduzir, tokens_superficie


@pytest.mark.parametrize("a,b,d", [
    ("", "", 0), ("abc", "", 3), ("kitten", "sitting", 3), ("travando", "trvando", 1),
    ("servidor", "servdor", 1), ("flaw", "lawn", 2), ("jogo", "jogo", 0),
])
def test_levenshtein(a, b, d):
    assert levenshtein(a, b) == d == levenshtein(b, a)


def test_kgramas_com_bordas():
    assert kgramas("lag") == {"$l", "la", "ag", "g$"}


@pytest.fixture
def corretor():
    freq = Counter({"travando": 50, "travamento": 30, "traducao": 20, "servidor": 40,
                    "servidores": 5, "historia": 60, "graficos": 45, "multiplayer": 35})
    return CorretorOrtografico(freq)


def test_autocompletar_por_frequencia(corretor):
    assert corretor.autocompletar("tra") == ["travando", "travamento", "traducao"]
    assert corretor.autocompletar("xyz") == []


@pytest.mark.parametrize("errada,certa", [
    ("trvando", "travando"), ("servdor", "servidor"), ("histporia", "historia"),
    ("grafcos", "graficos"), ("multiplayr", "multiplayer"),
])
def test_dois_estagios_concorda_com_forca_bruta(corretor, errada, certa):
    sug, n_candidatos = corretor.corrigir(errada, 1)
    sug_bf, n_vocab = corretor.corrigir_forca_bruta(errada, 1)
    assert sug[0].palavra == sug_bf[0].palavra == certa
    assert n_candidatos <= n_vocab


def test_voce_quis_dizer_preserva_a_frase(corretor):
    frase, trocas = corretor.corrigir_consulta("Jogo trvando no servdor")
    assert frase == "jogo travando no servidor"
    assert trocas == [("trvando", "travando"), ("servdor", "servidor")]


def test_normalizacao_e_stopwords():
    assert tokens_superficie("O Jogo é ÓTIMO, mas TRAVA!") == ["jogo", "otimo", "trava"]


@pytest.mark.parametrize("entrada,saida", [
    ("jogos", "jogo"), ("bons", "bom"), ("melhores", "melhor"), ("missoes", "missao"),
    ("graficos", "grafico"), ("jogaveis", "jogavel"), ("lag", "lag"), ("bonus", "bonus"),
])
def test_reducao_de_plural(entrada, saida):
    assert reduzir(entrada) == saida


def test_analisar_unifica_singular_e_plural():
    assert analisar("Bugs e mais bugs") == analisar("bug bug")
