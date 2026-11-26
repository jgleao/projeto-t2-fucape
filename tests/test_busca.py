"""A poda do WAND / Block-Max WAND tem que ser SEGURA: o Top-K deve ser identico
ao do BM25 exaustivo, para qualquer consulta e qualquer K."""

import random

import pytest

from src.search_engine.baseline import busca_exaustiva, busca_taat_heap
from src.search_engine.index import IndiceInvertido
from src.search_engine.optimized import busca_block_max_wand, busca_wand, busca_wand_campeoes
from src.search_engine.sintetico import gerar_corpus

OTIMIZADOS = [busca_wand, busca_wand_campeoes, busca_block_max_wand, busca_taat_heap]


@pytest.fixture(scope="module")
def indice():
    return IndiceInvertido.construir(gerar_corpus(n_docs=4000, tam_vocab=3000, semente=7),
                                     tamanho_bloco=16, tamanho_campeoes=16)


def _scores(resultado):
    """Top-K completo: (doc_id, score). Compara DOCUMENTOS, nao so scores."""
    return [(d, round(s, 12)) for d, s in resultado.top]


def _consultas(indice, n, semente=123):
    rng = random.Random(semente)
    vocab = sorted(indice.postagens)
    return [" ".join(rng.sample(vocab, rng.randint(1, 6))) for _ in range(n)]


@pytest.mark.parametrize("k", [1, 5, 10, 50])
@pytest.mark.parametrize("busca", OTIMIZADOS, ids=lambda f: f.__name__)
def test_topk_identico_ao_exaustivo(indice, busca, k):
    for consulta in _consultas(indice, 120, semente=k):
        esperado = busca_exaustiva(indice, consulta, k)
        obtido = busca(indice, consulta, k)
        assert _scores(obtido) == _scores(esperado), consulta


@pytest.mark.parametrize("semente", range(60))
def test_empates_desempatados_como_no_exaustivo(semente):
    """Vocabulario minusculo e documentos curtos e repetidos -> muitos scores empatados.
    O Top-K otimizado tem que trazer os MESMOS documentos (desempate por menor doc_id)."""
    rng = random.Random(semente)
    vocab = [f"t{i}" for i in range(8)]
    textos = [" ".join(rng.choices(vocab, k=rng.randint(1, 4))) for _ in range(rng.randint(30, 400))]
    indice = IndiceInvertido.construir(textos, tamanho_bloco=4, tamanho_campeoes=3)
    for consulta in ["t0", "t0 t1", "t1 t2 t3", "t0 t4 t5 t6 t7"]:
        for k in (1, 2, 3, 5, 10):
            esperado = _scores(busca_exaustiva(indice, consulta, k))
            for busca in OTIMIZADOS:
                assert _scores(busca(indice, consulta, k)) == esperado, (semente, consulta, k, busca.__name__)


def test_consultas_com_termos_frequentes(indice):
    for consulta in ["jogo muito bom", "jogo travando muito", "melhor jogo jogar horas", "nao recomendo"]:
        esperado = busca_exaustiva(indice, consulta, 10)
        for busca in OTIMIZADOS:
            assert _scores(busca(indice, consulta, 10)) == _scores(esperado)


def test_scores_batem_com_formula_bm25(indice):
    resultado = busca_wand_campeoes(indice, "travando servidor lag", 10)
    for doc_id, score in resultado.top:
        assert score == pytest.approx(indice.score_documento(doc_id, resultado.termos))


def test_poda_evita_avaliacoes(indice):
    consulta = "jogo travando muito"
    candidatos = busca_taat_heap(indice, consulta, 10).stats["candidatos"]
    for busca in (busca_wand, busca_wand_campeoes, busca_block_max_wand):
        assert busca(indice, consulta, 10).stats["docs_pontuados"] < candidatos


def test_consulta_vazia_ou_fora_do_vocabulario(indice):
    for busca in [busca_exaustiva, *OTIMIZADOS]:
        assert busca(indice, "", 10).top == []
        assert busca(indice, "xyzxyz qwqwqw", 10).top == []


def test_k_maior_que_candidatos(indice):
    consulta = "cheater"
    esperado = busca_exaustiva(indice, consulta, 10_000)
    for busca in OTIMIZADOS:
        assert _scores(busca(indice, consulta, 10_000)) == _scores(esperado)


def test_bm25_idf_positivo_e_limites_exatos(indice):
    for termo, lista in list(indice.postagens.items())[:200]:
        assert lista.idf > 0
        maior = max(indice.score_documento(d, [termo]) for d in lista.docs)
        assert lista.limite == pytest.approx(maior)
        assert max(lista.bloco_max) == pytest.approx(maior)
