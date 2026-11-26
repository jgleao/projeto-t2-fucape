"""Datasets do Airflow compartilhados entre DAGs (encadeamento orientado a dados)."""

from airflow.datasets import Dataset

# Publicado pelo DAG 1 ao terminar a ingestao; agenda o DAG 2.
RAW_REVIEWS_DATASET = Dataset("postgres://dw-postgres:5432/dw/raw/steam_reviews")
