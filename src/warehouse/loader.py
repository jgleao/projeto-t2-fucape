"""Etapas da consolidacao (DAG 2): staging -> dimensoes -> fato -> validacao.

Cada funcao e idempotente e pode ser chamada isoladamente (tarefas do Airflow
ou linha de comando: python -m src.warehouse.loader --full-refresh).
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg2.extras import execute_values

from src.db import executar_arquivo_sql, ler_sql, transacao

log = logging.getLogger(__name__)

PROCESSO = "consolidacao_reviews"
INICIO_DOS_TEMPOS = datetime(1970, 1, 1, tzinfo=timezone.utc)

GENEROS_PT = {
    "Action": "Acao", "Adventure": "Aventura", "Casual": "Casual", "Indie": "Indie",
    "Massively Multiplayer": "Multijogador Massivo", "Racing": "Corrida", "RPG": "RPG",
    "Simulation": "Simulacao", "Sports": "Esportes", "Strategy": "Estrategia",
    "Free to Play": "Gratuito para Jogar", "Early Access": "Acesso Antecipado",
}


# ---------------------------------------------------------------- estrutura
def criar_estruturas() -> None:
    executar_arquivo_sql("01_dw_ddl.sql")
    executar_arquivo_sql("13_dim_perfil.sql")


# ------------------------------------------------------------------ staging
def ler_watermark() -> datetime:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute("SELECT watermark FROM dw.etl_controle WHERE processo = %s", (PROCESSO,))
        linha = cur.fetchone()
    return linha[0] if linha else INICIO_DOS_TEMPOS


def preparar_staging(full_refresh: bool = False) -> dict[str, Any]:
    """Carrega stg.reviews com o que mudou na raw desde o ultimo watermark."""
    watermark = INICIO_DOS_TEMPOS if full_refresh else ler_watermark()
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(ler_sql("02_staging.sql"), {"watermark": watermark})
        cur.execute("SELECT count(*) FROM stg.reviews")
        (linhas,) = cur.fetchone()
        # novo watermark = maior last_ingested_at entre as linhas processadas
        cur.execute(
            """SELECT max(r.last_ingested_at) FROM raw.steam_reviews r
               JOIN stg.reviews s USING (recommendationid)""")
        (novo,) = cur.fetchone()
    info = {
        "watermark_anterior": watermark.isoformat(),
        "novo_watermark": (novo or watermark).isoformat(),
        "linhas_staging": int(linhas),
        "full_refresh": full_refresh,
    }
    log.info("Staging: %s", info)
    return info


# ------------------------------------------------------------- dimensoes
def carregar_dim_tempo() -> None:
    executar_arquivo_sql("10_dim_tempo.sql")


def carregar_dim_autor() -> None:
    executar_arquivo_sql("12_dim_autor.sql")


def carregar_dim_review() -> None:
    executar_arquivo_sql("14_dim_review.sql")


def _parse_data_lancamento(texto: str | None) -> date | None:
    if not texto:
        return None
    for formato in ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    return None


def transformar_detalhes(app_id: int, objeto: dict[str, Any] | None) -> tuple:
    """Desaninha o JSON de appdetails em uma linha da dim_jogo."""
    dados = (objeto or {}).get("data") if (objeto or {}).get("success") else None
    if not dados:
        return (app_id, f"App {app_id}", None, None, None, None, None, None, None, None, None, None)

    generos = [GENEROS_PT.get(g.get("description"), g.get("description"))
               for g in dados.get("genres") or [] if g.get("description")]
    preco = dados.get("price_overview") or {}
    gratuito = bool(dados.get("is_free"))
    preco_base = Decimal(preco["initial"]) / 100 if preco.get("initial") is not None else (
        Decimal(0) if gratuito else None)
    lancamento = _parse_data_lancamento((dados.get("release_date") or {}).get("date"))
    return (
        app_id,
        (dados.get("name") or f"App {app_id}").strip(),
        dados.get("type"),
        ", ".join(dados.get("developers") or []) or None,
        ", ".join(dados.get("publishers") or []) or None,
        generos[0] if generos else None,
        ", ".join(generos) or None,
        gratuito,
        preco_base,
        lancamento,
        lancamento.year if lancamento else None,
        (dados.get("short_description") or "").strip() or None,
    )


def carregar_dim_jogo() -> int:
    """dim_jogo (SCD tipo 1) a partir de raw.steam_app_details + jogos sem detalhes."""
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ids.app_id, d.payload
               FROM (SELECT app_id FROM raw.steam_app_details
                     UNION SELECT DISTINCT app_id FROM raw.steam_reviews) ids
               LEFT JOIN raw.steam_app_details d USING (app_id)""")
        linhas = [transformar_detalhes(app_id, payload) for app_id, payload in cur.fetchall()]
        if not linhas:
            return 0
        execute_values(cur, """
            INSERT INTO dw.dim_jogo (app_id, nome_jogo, tipo, desenvolvedor, publicadora, genero_principal,
                                     generos, gratuito, preco_base_brl, data_lancamento, ano_lancamento,
                                     descricao_curta)
            VALUES %s
            ON CONFLICT (app_id) DO UPDATE SET
                nome_jogo = EXCLUDED.nome_jogo, tipo = EXCLUDED.tipo,
                desenvolvedor = EXCLUDED.desenvolvedor, publicadora = EXCLUDED.publicadora,
                genero_principal = EXCLUDED.genero_principal, generos = EXCLUDED.generos,
                gratuito = EXCLUDED.gratuito, preco_base_brl = EXCLUDED.preco_base_brl,
                data_lancamento = EXCLUDED.data_lancamento, ano_lancamento = EXCLUDED.ano_lancamento,
                descricao_curta = EXCLUDED.descricao_curta, atualizado_em = now()
            WHERE (dw.dim_jogo.nome_jogo, dw.dim_jogo.generos, dw.dim_jogo.preco_base_brl,
                   dw.dim_jogo.descricao_curta, dw.dim_jogo.data_lancamento)
                  IS DISTINCT FROM (EXCLUDED.nome_jogo, EXCLUDED.generos, EXCLUDED.preco_base_brl,
                   EXCLUDED.descricao_curta, EXCLUDED.data_lancamento)
            """, linhas)
    return len(linhas)


# ------------------------------------------------------------------- fato
def carregar_fato() -> dict[str, int]:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(ler_sql("20_fato_review.sql"))
        flags = [flag for (flag,) in cur.fetchall()]
    resultado = {"fato_inseridas": sum(flags), "fato_atualizadas": len(flags) - sum(flags)}
    log.info("Fato: %s", resultado)
    return resultado


# -------------------------------------------------------------- qualidade
CHECKS_SQL = {
    # Cada consulta deve retornar 0 para o check passar.
    "fato_duplicada_por_review": """
        SELECT count(*) FROM (SELECT recommendationid FROM dw.fato_review
                              GROUP BY 1 HAVING count(*) > 1) d""",
    "fato_sem_dimensao_conhecida": """
        SELECT count(*) FROM dw.fato_review
        WHERE -1 IN (sk_tempo, sk_jogo, sk_autor, sk_perfil, sk_review)""",
    "raw_ausente_na_fato": """
        SELECT count(*) FROM raw.steam_reviews r
        LEFT JOIN dw.fato_review f USING (recommendationid) WHERE f.recommendationid IS NULL""",
    "qtd_reviews_diferente_de_1": "SELECT count(*) FROM dw.fato_review WHERE qtd_reviews <> 1",
    "recomendacao_inconsistente": """
        SELECT count(*) FROM dw.fato_review
        WHERE qtd_recomendacoes + qtd_nao_recomendacoes <> qtd_reviews""",
    "metricas_negativas": """
        SELECT count(*) FROM dw.fato_review
        WHERE votos_uteis < 0 OR votos_engracados < 0 OR minutos_jogados_review < 0""",
}


def validar_qualidade(run_id: str, info_staging: dict[str, Any] | None = None,
                      info_fato: dict[str, int] | None = None) -> dict[str, Any]:
    """Roda os checks, registra a execucao em dw.etl_execucao e falha se algum quebrar."""
    with transacao() as conn, conn.cursor() as cur:
        checks = {}
        for nome, sql in CHECKS_SQL.items():
            cur.execute(sql)
            checks[nome] = int(cur.fetchone()[0])
        cur.execute("SELECT count(*), COALESCE(sum(votos_uteis), 0) FROM dw.fato_review")
        total_fato, soma_votos = cur.fetchone()
        status = "sucesso" if all(v == 0 for v in checks.values()) else "falha_qualidade"
        cur.execute(
            """INSERT INTO dw.etl_execucao (run_id, linhas_staging, fato_inseridas, fato_atualizadas,
                                            total_fato, soma_votos_uteis, checks, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (run_id) DO UPDATE SET
                 linhas_staging = EXCLUDED.linhas_staging, fato_inseridas = EXCLUDED.fato_inseridas,
                 fato_atualizadas = EXCLUDED.fato_atualizadas, total_fato = EXCLUDED.total_fato,
                 soma_votos_uteis = EXCLUDED.soma_votos_uteis, checks = EXCLUDED.checks,
                 status = EXCLUDED.status, finalizado_em = now()""",
            (run_id, (info_staging or {}).get("linhas_staging"), (info_fato or {}).get("fato_inseridas"),
             (info_fato or {}).get("fato_atualizadas"), total_fato, soma_votos, json.dumps(checks), status))
    resultado = {"status": status, "checks": checks, "total_fato": int(total_fato),
                 "soma_votos_uteis": int(soma_votos)}
    log.info("Qualidade: %s", resultado)
    if status != "sucesso":
        raise ValueError(f"Checks de qualidade falharam: {checks}")
    return resultado


def registrar_watermark(novo_watermark_iso: str) -> None:
    """So avanca o watermark depois que fato e validacao terminaram com sucesso."""
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO dw.etl_controle (processo, watermark) VALUES (%s, %s)
               ON CONFLICT (processo) DO UPDATE
               SET watermark = GREATEST(dw.etl_controle.watermark, EXCLUDED.watermark), atualizado_em = now()""",
            (PROCESSO, datetime.fromisoformat(novo_watermark_iso)))


# -------------------------------------------------------- execucao local
def executar_tudo(run_id: str = "manual", full_refresh: bool = False) -> dict[str, Any]:
    criar_estruturas()
    info = preparar_staging(full_refresh)
    carregar_dim_tempo()
    carregar_dim_jogo()
    carregar_dim_autor()
    carregar_dim_review()
    fato = carregar_fato()
    qualidade = validar_qualidade(run_id, info, fato)
    registrar_watermark(info["novo_watermark"])
    return {"staging": info, "fato": fato, "qualidade": qualidade}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Consolidacao raw -> DW fora do Airflow")
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()
    print(json.dumps(executar_tudo(full_refresh=args.full_refresh), indent=2, default=str))
