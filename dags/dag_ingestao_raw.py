"""DAG 1 - Ingestao resiliente das reviews da Steam para a camada raw (bronze).

Fluxo: preparar_camada_raw -> listar_jogos -> [coletar_detalhes_jogo, coletar_reviews_jogo]
       (mapeamento dinamico: uma tarefa por jogo) -> publicar_dataset_raw.

Resiliencia:
* Paginacao por cursor (filter=recent) ate o watermark, pagina vazia ou cursor repetido.
* HTTP 429/5xx/timeout -> exponential backoff com jitter, respeitando Retry-After.
* Intervalo minimo de 1 s entre requisicoes e no maximo 2 jogos em paralelo (polidez).
* Retentativa da propria tarefa pelo Airflow (retry_exponential_backoff).

Idempotencia: upsert pela chave natural (recommendationid) e so altera a linha
quando o hash do payload muda. Clear/Retry nao gera duplicatas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pendulum
from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule

from src.config import ConfigColeta, app_ids_configurados
from src.datasets import RAW_REVIEWS_DATASET
from src.ingestion import raw_store
from src.ingestion.http_client import ClienteHttpResiliente
from src.ingestion.steam_api import ResultadoPaginacao, SteamApi

log = logging.getLogger(__name__)

CFG = ConfigColeta()

default_args = {
    "owner": "joao.vieira",
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
}


@dag(
    dag_id="dag_ingestao_raw",
    description="Coleta reviews e detalhes de jogos da Steam (API publica) para a camada raw",
    schedule="0 6 * * *",  # todo dia as 06:00 (America/Sao_Paulo)
    start_date=pendulum.datetime(2026, 11, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["t2", "ingestao", "raw", "steam"],
    params={
        "max_paginas_inicial": Param(CFG.max_paginas_inicial, type="integer", minimum=1, maximum=200,
                                     description="Paginas (100 reviews) por jogo na primeira carga"),
        "max_paginas_incremental": Param(CFG.max_paginas_incremental, type="integer", minimum=1, maximum=200,
                                         description="Paginas por jogo quando ja existe watermark"),
        "idioma": Param(CFG.idioma, type="string", description="Idioma das reviews na API da Steam"),
    },
    doc_md=__doc__,
)
def dag_ingestao_raw():
    @task
    def preparar_camada_raw() -> None:
        raw_store.criar_schema_raw()

    @task
    def listar_jogos() -> list[int]:
        jogos = app_ids_configurados()
        log.info("Jogos a coletar: %s", jogos)
        return jogos

    @task(max_active_tis_per_dagrun=2)
    def coletar_detalhes_jogo(app_id: int) -> dict:
        ctx = get_current_context()
        inicio = datetime.now(timezone.utc)
        http = ClienteHttpResiliente()
        try:
            objeto = SteamApi(http).detalhes_jogo(app_id)
            alterou = raw_store.upsert_detalhes(app_id, objeto, ctx["run_id"])
        except Exception as exc:
            raw_store.registrar_log(ctx["run_id"], app_id, "detalhes", "erro", inicio,
                                    requisicoes=http.stats.requisicoes, retentativas=http.stats.retentativas,
                                    respostas_429=http.stats.respostas_429, mensagem=str(exc)[:500])
            raise
        raw_store.registrar_log(ctx["run_id"], app_id, "detalhes", "sucesso", inicio,
                                linhas_recebidas=1, linhas_atualizadas=int(alterou),
                                requisicoes=http.stats.requisicoes, retentativas=http.stats.retentativas,
                                respostas_429=http.stats.respostas_429)
        return {"app_id": app_id, "alterado": alterou}

    # ALL_DONE: a falha nos detalhes de um jogo nao impede a coleta de reviews de nenhum jogo
    @task(max_active_tis_per_dagrun=2, trigger_rule=TriggerRule.ALL_DONE)
    def coletar_reviews_jogo(app_id: int) -> dict:
        ctx = get_current_context()
        params = ctx["params"]
        run_id = ctx["run_id"]
        inicio = datetime.now(timezone.utc)

        # Estado de cobertura explicito: uma carga inicial interrompida continua em
        # modo inicial no retry (o upsert torna o recomeco seguro), e o watermark so
        # avanca quando a janela inteira foi coberta.
        carga_completa, watermark = raw_store.ler_estado(app_id)
        incremental = carga_completa and watermark is not None
        if incremental:
            max_paginas = params["max_paginas_incremental"]
            parar_antes = watermark - CFG.sobreposicao_segundos
        else:
            max_paginas, parar_antes = params["max_paginas_inicial"], None

        http = ClienteHttpResiliente()
        api = SteamApi(http)
        pag = ResultadoPaginacao()
        inseridas = atualizadas = 0
        mais_nova = 0
        try:
            for pagina in api.paginas_reviews(app_id, idioma=params["idioma"], por_pagina=CFG.reviews_por_pagina,
                                              max_paginas=max_paginas, parar_antes_de_ts=parar_antes,
                                              resultado=pag):
                ins, upd = raw_store.upsert_reviews(app_id, pagina.reviews, run_id)
                inseridas += ins
                atualizadas += upd
                mais_nova = max([mais_nova] + [int(r.get("timestamp_created") or 0) for r in pagina.reviews])
                log.info("app %s pagina %d: %d reviews (%d novas, %d alteradas)",
                         app_id, pagina.numero, len(pagina.reviews), ins, upd)
        except Exception as exc:
            raw_store.registrar_log(run_id, app_id, "reviews", "erro", inicio, paginas=pag.paginas,
                                    linhas_recebidas=pag.reviews, linhas_inseridas=inseridas,
                                    linhas_atualizadas=atualizadas, requisicoes=http.stats.requisicoes,
                                    retentativas=http.stats.retentativas, respostas_429=http.stats.respostas_429,
                                    motivo_parada="erro", mensagem=str(exc)[:500])
            raise

        # Na carga inicial, o limite de paginas e a profundidade configurada do historico.
        # No incremental, parar pelo limite significa que nao alcancamos o watermark:
        # entao ele NAO avanca, e a proxima execucao recomeca da janela antiga, sem lacuna.
        cobertura_ok = (not incremental) or not pag.motivo_parada.startswith("limite")
        if cobertura_ok:
            raw_store.salvar_estado(app_id, True, mais_nova or watermark)
        else:
            pag.motivo_parada += " (cobertura incompleta: watermark mantido)"
            log.warning("app %s: limite de %d paginas antes do watermark; aumente max_paginas_incremental",
                        app_id, max_paginas)

        resumo = {
            "app_id": app_id, "modo": "incremental" if incremental else "carga_inicial",
            "paginas": pag.paginas, "recebidas": pag.reviews, "inseridas": inseridas,
            "atualizadas": atualizadas, "inalteradas": pag.reviews - inseridas - atualizadas,
            "retentativas": http.stats.retentativas, "respostas_429": http.stats.respostas_429,
            "motivo_parada": pag.motivo_parada,
        }
        raw_store.registrar_log(run_id, app_id, "reviews", "sucesso", inicio, paginas=pag.paginas,
                                linhas_recebidas=pag.reviews, linhas_inseridas=inseridas,
                                linhas_atualizadas=atualizadas, requisicoes=http.stats.requisicoes,
                                retentativas=http.stats.retentativas, respostas_429=http.stats.respostas_429,
                                motivo_parada=pag.motivo_parada)
        log.info("Resumo: %s", resumo)
        return resumo

    @task(outlets=[RAW_REVIEWS_DATASET], trigger_rule=TriggerRule.ALL_DONE)
    def publicar_dataset_raw(resumos: list[dict] | None, jogos: list[int]) -> dict:
        """Emite o Dataset que dispara o DAG 2. Tolera falha parcial (alguns jogos),
        mas falha se nenhum jogo foi coletado."""
        validos = [r for r in (resumos or []) if r]
        if not validos:
            raise RuntimeError("Nenhum jogo foi coletado com sucesso nesta execucao")
        faltando = sorted(set(jogos) - {r["app_id"] for r in validos})
        if faltando:
            log.warning("Falha parcial: %d jogo(s) sem coleta nesta execucao: %s "
                        "(detalhes em raw.ingestion_log; o proximo run tenta de novo)", len(faltando), faltando)
        total = {
            "jogos_ok": len(validos),
            "jogos_com_falha": faltando,
            "reviews_recebidas": sum(r["recebidas"] for r in validos),
            "reviews_novas": sum(r["inseridas"] for r in validos),
            "reviews_alteradas": sum(r["atualizadas"] for r in validos),
            "retentativas": sum(r["retentativas"] for r in validos),
        }
        log.info("Ingestao concluida: %s", total)
        return total

    jogos = listar_jogos()
    preparo = preparar_camada_raw()
    preparo >> jogos
    detalhes = coletar_detalhes_jogo.expand(app_id=jogos)
    reviews = coletar_reviews_jogo.expand(app_id=jogos)
    # detalhes antes de reviews: nunca mais de 2 clientes HTTP simultaneos (polidez)
    detalhes >> reviews
    publicar_dataset_raw(reviews, jogos)


dag_ingestao_raw()
