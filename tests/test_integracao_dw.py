"""Teste de integracao ponta a ponta contra um Postgres REAL (raw -> staging -> star schema).

So roda com RODAR_INTEGRACAO=1 e num banco cujo nome termina em "_teste"
(ele APAGA os schemas raw/stg/dw). No CI o GitHub Actions sobe esse banco.
Localmente, com o docker compose de pe:
    docker exec t2-dw-postgres createdb -U dw dw_teste
    RODAR_INTEGRACAO=1 DW_DB=dw_teste python -m pytest tests/test_integracao_dw.py -v
"""

import copy
import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RODAR_INTEGRACAO") != "1",
                                reason="defina RODAR_INTEGRACAO=1 para rodar contra um Postgres real")


def _review(rid, steamid, ts, voto=True, votos_uteis=3, texto="Jogo [b]muito[/b] bom, travando as vezes"):
    return {
        "recommendationid": str(rid), "language": "brazilian", "review": texto,
        "timestamp_created": ts, "timestamp_updated": ts + 60, "voted_up": voto, "votes_up": votos_uteis,
        "votes_funny": 4294967295 if rid == 3 else 0, "weighted_vote_score": "0.5123",
        "comment_count": 1, "steam_purchase": True, "received_for_free": False,
        "written_during_early_access": False, "primarily_steam_deck": rid == 2,
        "author": {"steamid": steamid, "num_games_owned": 120, "num_reviews": 7,
                   "playtime_forever": 6000, "playtime_at_review": 3000},
    }


DETALHES = {"success": True, "data": {
    "name": "Stardew Valley", "type": "game", "is_free": False, "developers": ["ConcernedApe"],
    "publishers": ["ConcernedApe"], "genres": [{"id": "23", "description": "Indie"}],
    "price_overview": {"initial": 2499}, "release_date": {"date": "26 Feb, 2016"},
    "short_description": "Fazenda"}}


@pytest.fixture(scope="module")
def banco():
    from src.config import ConfigBanco
    from src.db import transacao
    assert ConfigBanco().dbname.endswith("_teste"), "use um banco *_teste: este teste apaga os schemas"
    with transacao() as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS dw CASCADE; DROP SCHEMA IF EXISTS stg CASCADE; "
                    "DROP SCHEMA IF EXISTS raw CASCADE;")
    from src.ingestion import raw_store
    raw_store.criar_schema_raw()
    return transacao


def _contar(transacao, tabela):
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {tabela}")
        return cur.fetchone()[0]


def test_pipeline_completo_e_idempotente(banco):
    from scripts.verificar_idempotencia import impressao_digital
    from src.ingestion import raw_store
    from src.warehouse import loader

    reviews = [_review(1, "a", 1_700_000_000), _review(2, "b", 1_700_090_000, voto=False),
               _review(3, "a", 1_710_000_000)]
    # camada raw: primeira carga insere, reexecucao identica nao toca nada
    assert raw_store.upsert_reviews(413150, reviews, "run1") == (3, 0)
    assert raw_store.upsert_reviews(413150, reviews + reviews[:1], "run1-retry") == (0, 0)
    assert raw_store.upsert_detalhes(413150, DETALHES, "run1") is True
    assert raw_store.upsert_detalhes(413150, DETALHES, "run1-retry") is False

    resultado = loader.executar_tudo("dag2-a")
    assert resultado["fato"] == {"fato_inseridas": 3, "fato_atualizadas": 0}
    assert resultado["qualidade"]["status"] == "sucesso"
    assert _contar(banco, "dw.fato_review") == 3
    assert _contar(banco, "dw.dim_autor") == 3          # 2 autores + membro -1
    assert _contar(banco, "dw.dim_perfil_review") == 33  # 32 combinacoes + membro -1
    assert _contar(banco, "dw.dim_jogo") == 2

    # incremental sem novidades: staging vazia e nada muda
    digital = impressao_digital()
    assert loader.executar_tudo("dag2-b")["staging"]["linhas_staging"] == 0
    assert impressao_digital() == digital
    # full refresh: reprocessa tudo e o DW continua identico
    assert loader.executar_tudo("dag2-c", full_refresh=True)["fato"]["fato_inseridas"] == 0
    assert impressao_digital() == digital

    # review editada na fonte: atualiza a linha, nao duplica
    editada = copy.deepcopy(reviews[0])
    editada["votes_up"] = 50
    assert raw_store.upsert_reviews(413150, [editada], "run2") == (0, 1)
    res = loader.executar_tudo("dag2-d")
    assert res["staging"]["linhas_staging"] == 1
    assert res["fato"] == {"fato_inseridas": 0, "fato_atualizadas": 1}
    assert _contar(banco, "dw.fato_review") == 3

    with banco() as conn, conn.cursor() as cur:
        cur.execute("""SELECT r.texto_limpo, f.votos_engracados, j.nome_jogo, j.preco_base_brl::float,
                              t.dia_semana, p.desc_recomendacao
                       FROM dw.fato_review f JOIN dw.dim_review r USING (sk_review)
                       JOIN dw.dim_jogo j USING (sk_jogo) JOIN dw.dim_tempo t USING (sk_tempo)
                       JOIN dw.dim_perfil_review p USING (sk_perfil)
                       WHERE f.recommendationid = '3'""")
        texto, engracados, jogo, preco, dia, rec = cur.fetchone()
    assert texto == "Jogo muito bom, travando as vezes"   # BBCode removido
    assert engracados == 0                                 # overflow 4294967295 tratado
    assert (jogo, preco, rec) == ("Stardew Valley", 24.99, "Recomendado")
    assert dia.endswith("feira") or dia in ("Sábado", "Domingo")


def test_corpus_da_busca_vem_do_dw(banco):
    from src.search_engine.corpus import carregar_corpus
    from src.search_engine.motor import MotorBusca
    textos, metas = carregar_corpus()
    assert len(textos) == 3 and metas[0]["jogo"] == "Stardew Valley"
    resp = MotorBusca(textos, metas).buscar("jogo travndo", k=2)
    assert resp.correcoes == [("travndo", "travando")] and len(resp.docs) == 2


def test_dados_sujos_da_api_nao_derrubam_a_carga(banco):
    """Casos levantados na revisao: uint32 estourado, NUL/surrogate no texto, review sem
    timestamp_created e autor anonimo. A carga tem que passar e registrar avisos."""
    from src.ingestion import raw_store
    from src.warehouse import loader

    estourada = _review(10, "c", 1_720_000_000, votos_uteis=4294967295)
    estourada["comment_count"] = 4294967295
    estourada["author"]["num_games_owned"] = 4294967295
    com_nul = _review(11, "d", 1_720_000_100, texto="texto com \x00 nul e \ud83d surrogate solto")
    sem_data = _review(12, "e", 1_720_000_200)
    del sem_data["timestamp_created"]
    anonima = _review(13, "x", 1_720_000_300)
    del anonima["author"]["steamid"]
    assert raw_store.upsert_reviews(413150, [estourada, com_nul, sem_data, anonima], "run-sujo") == (4, 0)

    res = loader.executar_tudo("dag2-sujo")
    checks = res["qualidade"]["checks"]
    assert res["qualidade"]["status"] == "sucesso"
    assert checks["aviso_raw_inelegivel"] == 1 and checks["aviso_autor_desconhecido"] == 1
    with banco() as conn, conn.cursor() as cur:
        cur.execute("SELECT votos_uteis, qtd_comentarios FROM dw.fato_review WHERE recommendationid = '10'")
        assert cur.fetchone() == (2147483647, 2147483647)
        cur.execute("""SELECT r.texto_limpo FROM dw.fato_review f JOIN dw.dim_review r USING (sk_review)
                       WHERE f.recommendationid = '11'""")
        assert "\x00" not in cur.fetchone()[0]


def test_estado_de_cobertura_da_coleta(banco):
    from src.ingestion import raw_store
    assert raw_store.ler_estado(999) == (False, None)
    raw_store.salvar_estado(999, False, None)            # carga inicial interrompida
    assert raw_store.ler_estado(999) == (False, None)
    raw_store.salvar_estado(999, True, 1_700_000_000)    # carga inicial concluida
    raw_store.salvar_estado(999, True, 1_600_000_000)    # watermark nunca anda para tras
    assert raw_store.ler_estado(999) == (True, 1_700_000_000)
