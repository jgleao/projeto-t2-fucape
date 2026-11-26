"""Gravacao idempotente na camada raw (bronze) do Postgres.

Idempotencia: a chave natural da Steam (recommendationid / app_id) e PRIMARY KEY.
O upsert so reescreve a linha quando o hash do payload muda, entao reexecutar
a mesma coleta (Clear / Retry no Airflow) nao cria duplicatas nem "toca" linhas
iguais.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

from psycopg2.extras import Json, execute_values

from src.db import executar_arquivo_sql, transacao


def hash_payload(payload: Any) -> str:
    texto = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def criar_schema_raw() -> None:
    executar_arquivo_sql("00_raw_schema.sql")


def watermark_reviews(app_id: int) -> int | None:
    """Maior timestamp_created ja coletado do jogo (None = primeira carga)."""
    with transacao() as conn, conn.cursor() as cur:
        cur.execute("SELECT max(timestamp_created) FROM raw.steam_reviews WHERE app_id = %s", (app_id,))
        (valor,) = cur.fetchone()
    return int(valor) if valor is not None else None


SQL_UPSERT_REVIEWS = """
INSERT INTO raw.steam_reviews
    (recommendationid, app_id, payload, payload_hash, timestamp_created, timestamp_updated, last_run_id)
VALUES %s
ON CONFLICT (recommendationid) DO UPDATE SET
    payload           = EXCLUDED.payload,
    payload_hash      = EXCLUDED.payload_hash,
    timestamp_updated = EXCLUDED.timestamp_updated,
    last_run_id       = EXCLUDED.last_run_id,
    last_ingested_at  = now()
WHERE raw.steam_reviews.payload_hash IS DISTINCT FROM EXCLUDED.payload_hash
RETURNING (xmax = 0) AS inserida
"""


def upsert_reviews(app_id: int, reviews: Iterable[dict[str, Any]], run_id: str) -> tuple[int, int]:
    """Grava uma pagina de reviews. Retorna (inseridas, atualizadas)."""
    por_id: dict[str, dict[str, Any]] = {}
    for review in reviews:
        rid = str(review.get("recommendationid") or "").strip()
        if rid:
            por_id[rid] = review  # deduplica dentro do lote (ON CONFLICT exige)
    if not por_id:
        return 0, 0

    linhas = [
        (rid, app_id, Json(r), hash_payload(r), r.get("timestamp_created"), r.get("timestamp_updated"), run_id)
        for rid, r in por_id.items()
    ]
    with transacao() as conn, conn.cursor() as cur:
        resultado = execute_values(cur, SQL_UPSERT_REVIEWS, linhas, page_size=500, fetch=True)
    inseridas = sum(1 for (flag,) in resultado if flag)
    return inseridas, len(resultado) - inseridas


def upsert_detalhes(app_id: int, objeto: dict[str, Any], run_id: str) -> bool:
    """Grava o retorno bruto de appdetails. Retorna True se inseriu/alterou."""
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.steam_app_details (app_id, payload, payload_hash, success, last_run_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (app_id) DO UPDATE SET
                payload = EXCLUDED.payload, payload_hash = EXCLUDED.payload_hash,
                success = EXCLUDED.success, last_run_id = EXCLUDED.last_run_id, fetched_at = now()
            WHERE raw.steam_app_details.payload_hash IS DISTINCT FROM EXCLUDED.payload_hash
            RETURNING app_id
            """,
            (app_id, Json(objeto), hash_payload(objeto), bool(objeto.get("success")), run_id),
        )
        return cur.fetchone() is not None


def registrar_log(run_id: str, app_id: int, entidade: str, status: str, iniciado_em: datetime,
                  **campos: Any) -> None:
    colunas = ["paginas", "linhas_recebidas", "linhas_inseridas", "linhas_atualizadas",
               "requisicoes", "retentativas", "respostas_429", "motivo_parada", "mensagem"]
    valores = [campos.get(c, 0 if c not in ("motivo_parada", "mensagem") else None) for c in colunas]
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO raw.ingestion_log (run_id, app_id, entidade, status, iniciado_em, {", ".join(colunas)})
            VALUES (%s, %s, %s, %s, %s, {", ".join(["%s"] * len(colunas))})
            ON CONFLICT (run_id, app_id, entidade) DO UPDATE SET
                status = EXCLUDED.status, iniciado_em = EXCLUDED.iniciado_em, finalizado_em = now(),
                {", ".join(f"{c} = EXCLUDED.{c}" for c in colunas)}
            """,
            [run_id, app_id, entidade, status, iniciado_em, *valores],
        )
