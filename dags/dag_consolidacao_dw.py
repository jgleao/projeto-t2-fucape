"""DAG 2 - Consolidacao da camada raw no Data Warehouse (modelo estrela de Kimball).

Disparo: encadeado ao DAG 1 por Dataset (roda assim que o DAG 1 publica
"raw/steam_reviews"). Tambem pode ser disparado manualmente com full_refresh.

Fluxo: criar_estruturas -> preparar_staging -> [dim_tempo, dim_jogo, dim_autor, dim_review]
       -> carregar_fato -> validar_qualidade -> registrar_watermark

Idempotencia:
* staging e truncada e recarregada a cada execucao;
* dimensoes: upsert pela chave natural (SK estavel, SCD tipo 1);
* fato: upsert pela chave degenerada recommendationid (grao = 1 review), entao
  reexecutar nao duplica nem infla metricas;
* o watermark so avanca depois da validacao de qualidade passar.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context

from src.datasets import RAW_REVIEWS_DATASET
from src.warehouse import loader

default_args = {
    "owner": "joao.vieira",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
}


@dag(
    dag_id="dag_consolidacao_dw",
    description="Limpa, modela (star schema) e carrega as reviews no Data Warehouse",
    schedule=[RAW_REVIEWS_DATASET],
    start_date=pendulum.datetime(2026, 11, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    # Nasce ativo: um DAG consumidor pausado nao e enfileirado pelo evento do Dataset.
    is_paused_upon_creation=False,
    default_args=default_args,
    tags=["t2", "dw", "kimball", "star-schema"],
    params={"full_refresh": Param(False, type="boolean",
                                  description="Reprocessa toda a camada raw (ignora o watermark)")},
    doc_md=__doc__,
)
def dag_consolidacao_dw():
    @task
    def criar_estruturas() -> None:
        loader.criar_estruturas()

    @task
    def preparar_staging() -> dict:
        return loader.preparar_staging(bool(get_current_context()["params"]["full_refresh"]))

    @task
    def carregar_dim_tempo() -> None:
        loader.carregar_dim_tempo()

    @task
    def carregar_dim_jogo() -> int:
        return loader.carregar_dim_jogo()

    @task
    def carregar_dim_autor() -> None:
        loader.carregar_dim_autor()

    @task
    def carregar_dim_review() -> None:
        loader.carregar_dim_review()

    @task
    def carregar_fato() -> dict:
        return loader.carregar_fato()

    @task
    def validar_qualidade(info_staging: dict, info_fato: dict) -> dict:
        return loader.validar_qualidade(get_current_context()["run_id"], info_staging, info_fato)

    @task
    def registrar_watermark(info_staging: dict) -> str:
        loader.registrar_watermark(info_staging["novo_watermark"])
        return info_staging["novo_watermark"]

    estrutura = criar_estruturas()
    staging = preparar_staging()
    dims = [carregar_dim_tempo(), carregar_dim_jogo(), carregar_dim_autor(), carregar_dim_review()]
    fato = carregar_fato()
    qualidade = validar_qualidade(staging, fato)
    watermark = registrar_watermark(staging)

    estrutura >> staging >> dims >> fato
    qualidade >> watermark


dag_consolidacao_dw()
