"""Carrega o corpus textual direto do Data Warehouse (dim_review + fato + dimensoes)."""

from __future__ import annotations

from typing import Any

from src.db import transacao

SQL_CORPUS = """
SELECT r.recommendationid, r.texto_limpo, j.nome_jogo, j.genero_principal,
       p.desc_recomendacao, f.votos_uteis, round(f.minutos_jogados_review / 60.0, 1) AS horas,
       t.data_completa, r.qtd_palavras
FROM dw.fato_review f
JOIN dw.dim_review r        ON r.sk_review = f.sk_review
JOIN dw.dim_jogo j          ON j.sk_jogo   = f.sk_jogo
JOIN dw.dim_perfil_review p ON p.sk_perfil = f.sk_perfil
JOIN dw.dim_tempo t         ON t.sk_tempo  = f.sk_tempo
WHERE r.qtd_palavras >= %(min_palavras)s
ORDER BY f.sk_fato
"""


def carregar_corpus(min_palavras: int = 3) -> tuple[list[str], list[dict[str, Any]]]:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(SQL_CORPUS, {"min_palavras": min_palavras})
        linhas = cur.fetchall()
    textos = [ln[1] for ln in linhas]
    metas = [{
        "recommendationid": ln[0], "jogo": ln[2], "genero": ln[3], "recomendacao": ln[4],
        "votos_uteis": ln[5], "horas": float(ln[6] or 0), "data": ln[7], "palavras": ln[8],
    } for ln in linhas]
    return textos, metas
