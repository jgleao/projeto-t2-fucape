"""Conexao com o Postgres do Data Warehouse (camadas raw, stg e dw)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg2

from src.config import ConfigBanco

SQL_DIR = Path(__file__).resolve().parent / "warehouse" / "sql"


def conectar(config: ConfigBanco | None = None):
    return psycopg2.connect(**(config or ConfigBanco()).dsn())


@contextmanager
def transacao(config: ConfigBanco | None = None) -> Iterator:
    """Abre uma conexao, faz commit no sucesso e rollback em qualquer erro."""
    conn = conectar(config)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ler_sql(nome_arquivo: str) -> str:
    return (SQL_DIR / nome_arquivo).read_text(encoding="utf-8")


def executar_arquivo_sql(nome_arquivo: str, params: dict | None = None) -> None:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(ler_sql(nome_arquivo), params)
