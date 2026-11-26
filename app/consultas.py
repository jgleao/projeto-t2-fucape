"""Consultas analiticas ao modelo estrela (usadas pelo painel)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.db import transacao


def df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        colunas = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=colunas)


def escalar(sql: str, params: dict[str, Any] | None = None) -> Any:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        linha = cur.fetchone()
        return linha[0] if linha else None


FILTRO = """
    FROM dw.fato_review f
    JOIN dw.dim_tempo t         ON t.sk_tempo  = f.sk_tempo
    JOIN dw.dim_jogo j          ON j.sk_jogo   = f.sk_jogo
    JOIN dw.dim_perfil_review p ON p.sk_perfil = f.sk_perfil
    JOIN dw.dim_autor a         ON a.sk_autor  = f.sk_autor
    WHERE f.sk_jogo = ANY(%(jogos)s) AND t.data_completa BETWEEN %(inicio)s AND %(fim)s
"""


def params(jogos: list[int], inicio: date, fim: date) -> dict[str, Any]:
    return {"jogos": jogos, "inicio": inicio, "fim": fim}


def jogos_disponiveis() -> pd.DataFrame:
    return df("""SELECT j.sk_jogo, j.nome_jogo, count(*) AS reviews
                 FROM dw.fato_review f JOIN dw.dim_jogo j ON j.sk_jogo = f.sk_jogo
                 GROUP BY 1, 2 ORDER BY 3 DESC""")


def periodo_disponivel() -> tuple[date, date] | None:
    linha = df("""SELECT min(t.data_completa) AS ini, max(t.data_completa) AS fim
                  FROM dw.fato_review f JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_tempo""")
    if linha.empty or linha.iloc[0]["ini"] is None:
        return None
    return linha.iloc[0]["ini"], linha.iloc[0]["fim"]


def kpis(p: dict) -> pd.Series:
    return df(f"""
        SELECT sum(f.qtd_reviews) AS reviews,
               sum(f.qtd_recomendacoes)::float / NULLIF(sum(f.qtd_reviews), 0) AS pct_rec,
               (percentile_cont(0.5) WITHIN GROUP (ORDER BY f.minutos_jogados_review) / 60.0)::float AS horas_mediana,
               sum(f.votos_uteis) AS votos_uteis,
               count(DISTINCT f.sk_jogo) AS jogos,
               count(DISTINCT f.sk_autor) AS autores,
               avg(f.qtd_palavras)::float AS palavras_media
        {FILTRO}""", p).iloc[0]


def por_mes(p: dict) -> pd.DataFrame:
    return df(f"""SELECT t.ano_mes, p.desc_recomendacao AS recomendacao, sum(f.qtd_reviews) AS reviews
                  {FILTRO} GROUP BY 1, 2 ORDER BY 1""", p)


def por_jogo(p: dict) -> pd.DataFrame:
    return df(f"""SELECT j.nome_jogo AS jogo, sum(f.qtd_reviews) AS reviews,
                         sum(f.qtd_recomendacoes)::float / sum(f.qtd_reviews) AS pct_rec,
                         (percentile_cont(0.5) WITHIN GROUP (ORDER BY f.minutos_jogados_review) / 60.0)::float
                             AS horas_mediana,
                         sum(f.votos_uteis) AS votos_uteis
                  {FILTRO} GROUP BY 1 ORDER BY 3 DESC""", p)


def por_dia_semana(p: dict) -> pd.DataFrame:
    return df(f"""SELECT t.dia_semana_num, t.dia_semana, sum(f.qtd_reviews) AS reviews,
                         sum(f.qtd_recomendacoes)::float / sum(f.qtd_reviews) AS pct_rec
                  {FILTRO} GROUP BY 1, 2 ORDER BY 1""", p)


def por_faixa_horas(p: dict) -> pd.DataFrame:
    return df(f"""
        SELECT faixa, ordem, sum(qtd) AS reviews, sum(rec)::float / sum(qtd) AS pct_rec FROM (
            SELECT f.qtd_reviews AS qtd, f.qtd_recomendacoes AS rec,
                   CASE WHEN f.minutos_jogados_review < 120   THEN 'Menos de 2h'
                        WHEN f.minutos_jogados_review < 600   THEN '2h a 10h'
                        WHEN f.minutos_jogados_review < 3000  THEN '10h a 50h'
                        WHEN f.minutos_jogados_review < 12000 THEN '50h a 200h'
                        ELSE 'Mais de 200h' END AS faixa,
                   CASE WHEN f.minutos_jogados_review < 120   THEN 1
                        WHEN f.minutos_jogados_review < 600   THEN 2
                        WHEN f.minutos_jogados_review < 3000  THEN 3
                        WHEN f.minutos_jogados_review < 12000 THEN 4 ELSE 5 END AS ordem
            {FILTRO}) x GROUP BY 1, 2 ORDER BY 2""", p)


def por_aquisicao(p: dict) -> pd.DataFrame:
    return df(f"""SELECT p.desc_aquisicao AS aquisicao, sum(f.qtd_reviews) AS reviews,
                         sum(f.qtd_recomendacoes)::float / sum(f.qtd_reviews) AS pct_rec
                  {FILTRO} GROUP BY 1 ORDER BY 2 DESC""", p)


def por_genero(p: dict) -> pd.DataFrame:
    return df(f"""SELECT COALESCE(j.genero_principal, 'Sem genero') AS genero, count(DISTINCT j.sk_jogo) AS jogos,
                         sum(f.qtd_reviews) AS reviews,
                         sum(f.qtd_recomendacoes)::float / sum(f.qtd_reviews) AS pct_rec
                  {FILTRO} GROUP BY 1 ORDER BY 3 DESC""", p)


def mais_uteis(p: dict, n: int = 8) -> pd.DataFrame:
    return df(f"""SELECT j.nome_jogo AS jogo, p.desc_recomendacao AS recomendacao, f.votos_uteis,
                         round(f.minutos_jogados_review / 60.0, 1)::float AS horas, t.data_completa AS data,
                         r.texto_limpo AS texto
                  {FILTRO.replace('WHERE', 'JOIN dw.dim_review r ON r.sk_review = f.sk_review WHERE')}
                  ORDER BY f.votos_uteis DESC LIMIT {int(n)}""", p)


# ---------------------------------------------------------- engenharia
def contagem_tabelas() -> pd.DataFrame:
    tabelas = [
        ("raw", "steam_reviews", "Bronze: review original (JSONB)"),
        ("raw", "steam_app_details", "Bronze: detalhes do jogo (JSONB)"),
        ("raw", "ingestion_log", "Auditoria da ingestao"),
        ("stg", "reviews", "Staging da ultima execucao"),
        ("dw", "dim_tempo", "Dimensao calendario"),
        ("dw", "dim_jogo", "Dimensao jogo"),
        ("dw", "dim_autor", "Dimensao autor"),
        ("dw", "dim_perfil_review", "Junk dimension de flags"),
        ("dw", "dim_review", "Dimensao texto (corpus da busca)"),
        ("dw", "fato_review", "Fato: 1 linha = 1 review"),
    ]
    sql = " UNION ALL ".join(
        f"SELECT '{s}' AS camada, '{t}' AS tabela, '{d}' AS papel, count(*) AS linhas FROM {s}.{t}"
        for s, t, d in tabelas)
    return df(sql)


def ultima_ingestao() -> pd.DataFrame:
    return df("""
        WITH ultima AS (SELECT run_id FROM raw.ingestion_log ORDER BY finalizado_em DESC LIMIT 1)
        SELECT COALESCE(j.nome_jogo, 'App ' || l.app_id) AS jogo, l.entidade, l.status, l.paginas,
               l.linhas_recebidas AS recebidas, l.linhas_inseridas AS novas, l.linhas_atualizadas AS alteradas,
               l.requisicoes, l.retentativas, l.respostas_429, l.motivo_parada,
               round(extract(epoch FROM l.finalizado_em - l.iniciado_em)::numeric, 1)::float AS segundos
        FROM raw.ingestion_log l JOIN ultima u USING (run_id)
        LEFT JOIN dw.dim_jogo j ON j.app_id = l.app_id
        ORDER BY l.entidade DESC, l.linhas_recebidas DESC""")


def historico_ingestao() -> pd.DataFrame:
    return df("""SELECT run_id, min(iniciado_em) AS inicio, count(*) FILTER (WHERE status = 'sucesso') AS ok,
                        count(*) FILTER (WHERE status = 'erro') AS erros, sum(linhas_recebidas) AS recebidas,
                        sum(linhas_inseridas) AS novas, sum(linhas_atualizadas) AS alteradas,
                        sum(retentativas) AS retentativas, sum(respostas_429) AS respostas_429
                 FROM raw.ingestion_log GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")


def historico_etl() -> pd.DataFrame:
    return df("""SELECT run_id, finalizado_em, status, linhas_staging, fato_inseridas, fato_atualizadas,
                        total_fato, soma_votos_uteis, checks::text AS checks
                 FROM dw.etl_execucao ORDER BY finalizado_em DESC LIMIT 15""")


def amostra_fato(n: int = 10) -> pd.DataFrame:
    return df(f"""SELECT f.sk_fato, f.sk_tempo, f.sk_jogo, f.sk_autor, f.sk_perfil, f.sk_review,
                         f.recommendationid, f.qtd_reviews, f.qtd_recomendacoes, f.votos_uteis,
                         f.minutos_jogados_review, f.minutos_jogados_total, f.score_utilidade::float
                  FROM dw.fato_review f ORDER BY f.sk_fato DESC LIMIT {int(n)}""")
