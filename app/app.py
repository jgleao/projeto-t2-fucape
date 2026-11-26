"""Painel executivo - Steam Reviews Intelligence (T2 FUCAPE).

Abas:
1. Visao de Negocios      - KPIs e agregacoes direto do modelo estrela
2. Busca Inteligente      - BM25 + WAND/Champion Lists, correcao ortografica e autocompletar
3. Engenharia & Benchmark - saude dos pipelines, idempotencia e benchmark Antes vs. Depois
4. Modelo Dimensional     - tabelas do Data Warehouse, granularidade e amostras

Execucao: streamlit run app/app.py   (ou o servico "dashboard" do docker compose)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

import consultas as q  # noqa: E402
from src.search_engine.benchmark import (CONSULTAS_PADRAO, ERROS_PADRAO, benchmark_ortografia,  # noqa: E402
                                         benchmark_ranking, mesmo_top)
from src.search_engine.motor import MotorBusca  # noqa: E402
from src.search_engine.text import normalizar, reduzir  # noqa: E402

st.set_page_config(page_title="Steam Reviews Intelligence", page_icon="🎮", layout="wide")

# Paleta categorica validada (ordem fixa) + tinta de texto recessiva
AZUL, LARANJA, AQUA, AMARELO = "#257de0", "#f47230", "#00b894", "#f2a600"
CINZA_TEXTO, GRADE = "#666666", "#e6e6e6"
COR_RECOMENDACAO = alt.Scale(domain=["Recomendado", "Nao recomendado"], range=[AZUL, LARANJA])
NOMES_ALGORITMO = {"wand_campeoes": "WAND + Champion Lists", "bmw": "Block-Max WAND", "wand": "WAND classico"}

st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; max-width: 1400px;}
  div[data-testid="stMetric"] {background: var(--secondary-background-color); border-radius: 12px;
                               padding: 14px 16px; border: 1px solid rgba(128,128,128,.15);}
  div[data-testid="stMetricLabel"] p {font-size: .82rem; color: #666;}
  .hero {padding: 18px 22px; border-radius: 16px; margin-bottom: 8px;
         background: linear-gradient(120deg, #0e3d7e 0%, #257de0 60%, #00b894 140%); color: #fff;}
  .hero h1 {font-size: 1.7rem; margin: 0; color: #fff;}
  .hero p {margin: 4px 0 0; opacity: .9;}
  .tag {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;
        margin-right:6px; border:1px solid rgba(128,128,128,.3);}
  .tag-rec {background: rgba(37,125,224,.12); color:#1757ac;}
  .tag-nao {background: rgba(244,114,48,.14); color:#a84410;}
  mark {background: rgba(242,166,0,.35); padding: 0 2px; border-radius: 3px;}
</style>""", unsafe_allow_html=True)


def tema(chart: alt.Chart, altura: int = 300) -> alt.Chart:
    return (chart.properties(height=altura)
            .configure_axis(gridColor=GRADE, domainColor=GRADE, tickColor=GRADE, labelColor=CINZA_TEXTO,
                            titleColor=CINZA_TEXTO, labelFontSize=11, titleFontSize=11, titleFontWeight="normal")
            .configure_legend(labelColor=CINZA_TEXTO, titleColor=CINZA_TEXTO, orient="top", title=None)
            .configure_view(strokeWidth=0))


# ----------------------------------------------------------------- dados
@st.cache_data(ttl=60, show_spinner=False)
def status_dw() -> tuple[bool, str, int, str]:
    """(conectado, mensagem, linhas na fato, versao do corpus para a chave do cache do indice)."""
    try:
        linha = q.df("""SELECT (SELECT count(*) FROM dw.fato_review) AS total,
                               (SELECT max(atualizado_em) FROM dw.dim_review)::text AS ultima_edicao""").iloc[0]
        total = int(linha["total"] or 0)
        return True, "conectado", total, f"{total}|{linha['ultima_edicao']}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).splitlines()[0][:160], 0, "offline"


@st.cache_data(ttl=120, show_spinner=False)
def status_airflow() -> dict[str, dict]:
    url = os.getenv("AIRFLOW_API_URL", "http://localhost:8080/api/v1")
    auth = (os.getenv("AIRFLOW_API_USER", "airflow"), os.getenv("AIRFLOW_API_PASSWORD", "airflow"))
    saida = {}
    for dag_id in ("dag_ingestao_raw", "dag_consolidacao_dw"):
        try:
            r = requests.get(f"{url}/dags/{dag_id}/dagRuns", params={"order_by": "-execution_date", "limit": 5},
                             auth=auth, timeout=3)
            r.raise_for_status()
            runs = r.json().get("dag_runs", [])
            saida[dag_id] = {"ok": True, "runs": runs}
        except Exception as exc:  # noqa: BLE001
            saida[dag_id] = {"ok": False, "erro": exc.__class__.__name__, "runs": []}
    return saida


@st.cache_resource(show_spinner="Indexando o corpus do Data Warehouse (indice invertido + Trie + k-gramas)...")
def carregar_motor(versao_dw: str, fonte: str) -> MotorBusca:
    if fonte == "dw":
        from src.search_engine.corpus import carregar_corpus
        textos, metas = carregar_corpus()
    else:
        from src.search_engine.sintetico import gerar_corpus
        textos = gerar_corpus(40_000)
        metas = [{"jogo": "Corpus sintetico", "recomendacao": "-", "horas": 0, "votos_uteis": 0, "data": None}
                 for _ in textos]
    return MotorBusca(textos, metas)


def destacar(texto: str, termos: list[str], limite: int = 600) -> str:
    alvo = set(termos)
    trecho = texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + " ..."
    trecho = trecho.replace("<", "&lt;").replace(">", "&gt;")

    def troca(m: re.Match) -> str:
        palavra = m.group(0)
        return f"<mark>{palavra}</mark>" if reduzir(normalizar(palavra)) in alvo else palavra
    return re.sub(r"[\wÀ-ÿ]+", troca, trecho)


def fmt_int(v) -> str:
    return f"{int(v):,}".replace(",", ".") if pd.notna(v) else "-"


def num(v) -> float:
    """None/NaN -> 0.0 (NaN e "truthy", entao `v or 0` nao basta)."""
    return float(v) if v is not None and pd.notna(v) else 0.0


# ---------------------------------------------------------------- layout
dw_ok, dw_msg, total_fato, versao_corpus = status_dw()

with st.sidebar:
    st.markdown("### 🎮 Steam Reviews Intelligence")
    st.caption("T2 · Modelagem Informacional & PLN/RI · FUCAPE 2026")
    st.markdown(f"**Data Warehouse:** {'🟢' if dw_ok else '🔴'} {dw_msg}")
    if dw_ok:
        st.markdown(f"**Linhas na fato:** {fmt_int(total_fato)}")
    fonte_busca = "dw" if dw_ok and total_fato > 0 else "sintetico"
    if fonte_busca == "sintetico":
        st.warning("DW vazio ou fora do ar: a busca usa um corpus sintetico ate os DAGs rodarem.")
    if st.button("🔄 Recarregar dados", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.divider()
    st.caption("Fonte: API publica da Steam (reviews em PT-BR) → Airflow → Postgres (Star Schema) → este painel.")

st.markdown("""<div class="hero"><h1>Steam Reviews Intelligence</h1>
<p>O que os jogadores brasileiros dizem sobre os maiores jogos da Steam: pipeline Airflow, Data Warehouse
Kimball e busca BM25 com poda WAND.</p></div>""", unsafe_allow_html=True)

aba_negocio, aba_busca, aba_eng, aba_modelo = st.tabs(
    ["📊 Visão de Negócios", "🔎 Busca Inteligente", "⚙️ Engenharia & Benchmark", "🧬 Modelo Dimensional"])

# ======================================================= 1. NEGOCIOS ===
with aba_negocio:
    periodo = q.periodo_disponivel() if dw_ok and total_fato > 0 else None
    if periodo is None:
        st.info("O Data Warehouse ainda nao tem dados. Rode `dag_ingestao_raw` no Airflow "
                "(o `dag_consolidacao_dw` dispara sozinho via Dataset) e clique em Recarregar dados.")
    else:
        jogos_df = q.jogos_disponiveis()
        c1, c2 = st.columns([3, 2])
        with c1:
            escolhidos = st.multiselect("Jogos", jogos_df["nome_jogo"].tolist(),
                                        placeholder="Todos os jogos")
        with c2:
            intervalo = st.date_input("Período de publicação da review", value=periodo,
                                      min_value=periodo[0], max_value=periodo[1])
            inicio, fim = intervalo if isinstance(intervalo, (tuple, list)) and len(intervalo) == 2 else periodo
        sks = jogos_df[jogos_df["nome_jogo"].isin(escolhidos)]["sk_jogo"].tolist() if escolhidos \
            else jogos_df["sk_jogo"].tolist()
        p = q.params([int(s) for s in sks], inicio, fim)
        k = q.kpis(p)

        m = st.columns(6)
        m[0].metric("Reviews", fmt_int(k["reviews"]))
        m[1].metric("% Recomendam", f"{num(k['pct_rec']) * 100:.1f}%")
        m[2].metric("Horas jogadas (mediana)", f"{num(k['horas_mediana']):.1f} h")
        m[3].metric("Votos 'útil'", fmt_int(k["votos_uteis"]))
        m[4].metric("Autores únicos", fmt_int(k["autores"]))
        m[5].metric("Palavras por review", f"{num(k['palavras_media']):.0f}")

        g1, g2 = st.columns([3, 2])
        with g1:
            st.markdown("##### Volume mensal de reviews")
            mes = q.por_mes(p)
            ch = alt.Chart(mes).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, stroke="white",
                                         strokeWidth=1).encode(
                x=alt.X("ano_mes:O", title=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y("sum(reviews):Q", title="Reviews"),
                color=alt.Color("recomendacao:N", scale=COR_RECOMENDACAO),
                order=alt.Order("recomendacao:N", sort="descending"),
                tooltip=[alt.Tooltip("ano_mes:O", title="Mes"), alt.Tooltip("recomendacao:N", title="Tipo"),
                         alt.Tooltip("sum(reviews):Q", title="Reviews", format=",")])
            st.altair_chart(tema(ch), width="stretch")
        with g2:
            st.markdown("##### Taxa de recomendação por jogo")
            jg = q.por_jogo(p)
            ch = alt.Chart(jg).mark_bar(cornerRadiusEnd=4, color=AZUL, height=14).encode(
                x=alt.X("pct_rec:Q", title="% recomendam", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("jogo:N", sort="-x", title=None),
                tooltip=[alt.Tooltip("jogo:N", title="Jogo"), alt.Tooltip("pct_rec:Q", title="% recomendam", format=".1%"),
                         alt.Tooltip("reviews:Q", title="Reviews", format=","),
                         alt.Tooltip("horas_mediana:Q", title="Horas (mediana)", format=".1f")])
            st.altair_chart(tema(ch, max(260, 22 * len(jg))), width="stretch")

        g3, g4, g5 = st.columns(3)
        with g3:
            st.markdown("##### Quem joga mais recomenda mais?")
            fh = q.por_faixa_horas(p)
            ch = alt.Chart(fh).mark_bar(cornerRadiusEnd=4, color=AZUL, width=alt.RelativeBandSize(0.6)).encode(
                x=alt.X("faixa:N", sort=fh["faixa"].tolist(), title="Horas jogadas ao escrever",
                        axis=alt.Axis(labelAngle=0)),
                y=alt.Y("pct_rec:Q", title="% recomendam", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                tooltip=[alt.Tooltip("faixa:N", title="Faixa"), alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam"),
                         alt.Tooltip("reviews:Q", format=",", title="Reviews")])
            st.altair_chart(tema(ch, 260), width="stretch")
        with g4:
            st.markdown("##### Reviews por dia da semana")
            ds = q.por_dia_semana(p)
            ch = alt.Chart(ds).mark_bar(cornerRadiusEnd=4, color=AZUL, width=alt.RelativeBandSize(0.6)).encode(
                x=alt.X("dia_semana:N", sort=ds["dia_semana"].tolist(), title=None,
                        axis=alt.Axis(labelAngle=-30, labelExpr="slice(datum.label, 0, 3)")),
                y=alt.Y("reviews:Q", title="Reviews"),
                tooltip=[alt.Tooltip("dia_semana:N", title="Dia"), alt.Tooltip("reviews:Q", format=",", title="Reviews"),
                         alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam")])
            st.altair_chart(tema(ch, 260), width="stretch")
        with g5:
            st.markdown("##### Origem da cópia do jogo")
            aq = q.por_aquisicao(p)
            ch = alt.Chart(aq).mark_bar(cornerRadiusEnd=4, color=AZUL, height=16).encode(
                y=alt.Y("aquisicao:N", sort="-x", title=None),
                x=alt.X("reviews:Q", title="Reviews"),
                tooltip=[alt.Tooltip("aquisicao:N", title="Origem"), alt.Tooltip("reviews:Q", format=",", title="Reviews"),
                         alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam")])
            st.altair_chart(tema(ch, 260), width="stretch")

        st.markdown("##### Gêneros")
        gen = q.por_genero(p)
        st.dataframe(gen, hide_index=True, width="stretch", column_config={
            "genero": "Gênero principal", "jogos": "Jogos", "reviews": st.column_config.NumberColumn("Reviews", format="%d"),
            "pct_rec": st.column_config.ProgressColumn("% recomendam", min_value=0, max_value=1, format="percent")})

        st.markdown("##### As reviews que a comunidade achou mais úteis")
        for _, ln in q.mais_uteis(p).iterrows():
            classe = "tag-rec" if ln["recomendacao"] == "Recomendado" else "tag-nao"
            with st.container(border=True):
                st.markdown(f"<span class='tag {classe}'>{ln['recomendacao']}</span>"
                            f"<b>{ln['jogo']}</b> · 👍 {fmt_int(ln['votos_uteis'])} votos úteis · "
                            f"{ln['horas']:.1f} h jogadas · {ln['data']}", unsafe_allow_html=True)
                st.markdown(destacar(ln["texto"] or "", [], 450), unsafe_allow_html=True)

# ========================================================== 2. BUSCA ===
with aba_busca:
    motor = carregar_motor(versao_corpus, fonte_busca)
    st.caption(f"Índice: {fmt_int(motor.indice.n_docs)} reviews · {fmt_int(len(motor.indice.postagens))} termos · "
               f"construído em {motor.tempo_indexacao_s:.1f}s · corretor com "
               f"{fmt_int(len(motor.corretor.vocabulario))} palavras")
    c1, c2, c3, c4 = st.columns([5, 1.3, 2, 1.4])
    with c1:
        consulta = st.text_input("O que você quer encontrar nas reviews?", value="jogo travando muito no servdor",
                                 placeholder="ex.: otimização ruim, história emocionante, jogar com amigos")
    with c2:
        k_top = st.number_input("Top-K", 1, 100, 10)
    with c3:
        algoritmo = st.selectbox("Algoritmo otimizado", list(NOMES_ALGORITMO), format_func=NOMES_ALGORITMO.get)
    with c4:
        corrigir = st.toggle("Corrigir erros", value=True)

    ultimo = normalizar(consulta.split()[-1]) if consulta.split() else ""
    if len(ultimo) >= 2:
        sugestoes = motor.corretor.autocompletar(ultimo)
        if sugestoes:
            st.caption("Autocompletar (Trie, O(|P|)): " + " · ".join(f"`{s}`" for s in sugestoes[:8]))

    if consulta.strip():
        resp = motor.buscar(consulta, int(k_top), algoritmo, corrigir)
        if resp.correcoes:
            trocas = ", ".join(f"~~{a}~~ → **{b}**" for a, b in resp.correcoes)
            st.info(f"Você quis dizer: **{resp.consulta_usada}**  ({trocas}) · "
                    f"correção em {resp.tempo_correcao_ms:.2f} ms")
        candidatos = len({d for t in resp.resultado.termos for d in motor.indice.postagens[t].docs}) \
            if resp.resultado.termos else 0
        avaliados = resp.resultado.stats.get("docs_pontuados", 0)
        m = st.columns(5)
        m[0].metric("Baseline: BM25 exaustivo", f"{resp.tempo_baseline_ms:.2f} ms",
                    help="Pontua os N documentos da base e ordena todos (antes)")
        m[1].metric(NOMES_ALGORITMO[algoritmo], f"{resp.tempo_otimizado_ms:.2f} ms",
                    delta=f"-{resp.delta_pct:.1f}%" if resp.delta_pct >= 0 else f"+{-resp.delta_pct:.1f}%",
                    delta_color="inverse")
        m[2].metric("Speedup", f"{resp.speedup:.1f}×")
        m[3].metric("Docs pontuados", f"{fmt_int(avaliados)} / {fmt_int(candidatos)}",
                    help="Documentos pontuados pelo algoritmo otimizado / documentos que contêm algum termo")
        m[4].metric("Taxa de poda", f"{(1 - avaliados / candidatos) * 100 if candidatos else 0:.1f}%")
        identico = mesmo_top(resp.resultado, resp.baseline)
        st.caption(("✅ Top-K idêntico ao exaustivo (poda segura)" if identico else "⚠️ Top-K diferente do exaustivo")
                   + f" · termos analisados: {', '.join(resp.resultado.termos) or '-'}")

        if not resp.docs:
            st.warning("Nenhuma review contém esses termos.")
        for pos, doc in enumerate(resp.docs, 1):
            classe = "tag-rec" if doc.get("recomendacao") == "Recomendado" else "tag-nao"
            with st.container(border=True):
                st.markdown(
                    f"**#{pos}** · <span class='tag {classe}'>{doc.get('recomendacao', '-')}</span>"
                    f"<b>{doc.get('jogo', '-')}</b> · BM25 <code>{doc['score']:.3f}</code> · "
                    f"{doc.get('horas', 0):.1f} h jogadas · 👍 {fmt_int(doc.get('votos_uteis', 0))} · "
                    f"{doc.get('data') or ''}", unsafe_allow_html=True)
                st.markdown(destacar(doc["texto"], resp.resultado.termos), unsafe_allow_html=True)

# ================================================ 3. ENGENHARIA ========
with aba_eng:
    st.markdown("#### Saúde dos pipelines")
    af = status_airflow()
    cols = st.columns(2)
    for col, dag_id in zip(cols, ("dag_ingestao_raw", "dag_consolidacao_dw")):
        info = af[dag_id]
        with col, st.container(border=True):
            if not info["ok"]:
                st.markdown(f"**{dag_id}** · ⚪ API do Airflow indisponível ({info['erro']})")
                continue
            runs = info["runs"]
            if not runs:
                st.markdown(f"**{dag_id}** · ainda sem execuções")
                continue
            icone = {"success": "🟢", "failed": "🔴", "running": "🔵", "queued": "🟡"}
            st.markdown(f"**{dag_id}** · última: {icone.get(runs[0]['state'], '⚪')} `{runs[0]['state']}` "
                        f"em {str(runs[0].get('end_date') or runs[0].get('start_date'))[:19]}")
            st.caption("Últimas execuções: " + " ".join(icone.get(r["state"], "⚪") for r in runs))

    if dw_ok:
        try:
            ing = q.ultima_ingestao()
            if not ing.empty:
                st.markdown("##### DAG 1 · última ingestão por jogo (resiliência e paginação)")
                t = st.columns(4)
                t[0].metric("Requisições HTTP", fmt_int(ing["requisicoes"].sum()))
                t[1].metric("Retentativas (backoff)", fmt_int(ing["retentativas"].sum()))
                t[2].metric("Respostas 429", fmt_int(ing["respostas_429"].sum()))
                t[3].metric("Reviews novas / alteradas",
                            f"{fmt_int(ing['novas'].sum())} / {fmt_int(ing['alteradas'].sum())}")
                st.dataframe(ing, hide_index=True, width="stretch")
            etl = q.historico_etl()
            if not etl.empty:
                st.markdown("##### DAG 2 · histórico de cargas e prova de idempotência")
                st.caption("Reexecutar o DAG 2 (ou o DAG 1 sem reviews novas) mantém `total_fato` e "
                           "`soma_votos_uteis` constantes: o upsert pela chave natural não duplica nem infla métricas.")
                st.dataframe(etl, hide_index=True, width="stretch")
            hist = q.historico_ingestao()
            if not hist.empty:
                with st.expander("Histórico do DAG 1 (camada raw)"):
                    st.dataframe(hist, hide_index=True, width="stretch")
        except Exception as exc:  # noqa: BLE001
            st.info(f"Tabelas de auditoria ainda não existem ({exc.__class__.__name__}). Rode os DAGs.")

    st.divider()
    st.markdown("#### Benchmark ao vivo · Antes vs. Depois")
    st.caption("Mesmo índice, mesmas consultas. Tempo com `time.perf_counter()` (média de N execuções, "
               "1 aquecimento, GC desligado). Δ% = (T_baseline − T_otimizado) / T_baseline × 100.")
    b1, b2, b3 = st.columns([1, 1, 3])
    repeticoes = b1.slider("Repetições", 3, 30, 7)
    k_bench = b2.slider("K", 1, 100, 10)
    if b3.button("▶️ Rodar benchmark completo", type="primary"):
        with st.spinner("Medindo 5 algoritmos x 12 consultas + correção ortográfica..."):
            st.session_state["bench"] = benchmark_ranking(motor.indice, CONSULTAS_PADRAO, k_bench, repeticoes)
            st.session_state["bench_ort"] = benchmark_ortografia(motor.corretor, ERROS_PADRAO, 3)

    if "bench" not in st.session_state:
        salvo = RAIZ / "docs" / "resultados_benchmark.json"
        if salvo.exists():
            dados = json.loads(salvo.read_text(encoding="utf-8"))
            st.info(f"Mostrando o último benchmark salvo ({dados['corpus']}, {dados['ambiente']['gerado_em']}). "
                    "Clique em Rodar para medir agora.")
            st.session_state["bench"] = (dados["ranking"]["consultas"], dados["ranking"]["resumo"])
            st.session_state["bench_ort"] = (dados["ortografia"]["palavras"], dados["ortografia"]["resumo"])
            st.session_state["escala"] = dados.get("escala", [])

    if "bench" in st.session_state:
        linhas, resumo = st.session_state["bench"]
        r = st.columns(5)
        r[0].metric("Baseline exaustivo", f"{resumo['exaustivo_ms_medio']:.2f} ms")
        r[1].metric("WAND + Champion Lists", f"{resumo['wand_campeoes_ms_medio']:.2f} ms",
                    delta=f"-{resumo['wand_campeoes_delta_pct']:.1f}%", delta_color="inverse")
        r[2].metric("Speedup", f"{resumo['wand_campeoes_speedup']:.1f}×")
        r[3].metric("Docs podados", f"{resumo['wand_campeoes_poda_docs_pct']:.1f}%")
        r[4].metric("Top-K idêntico", "✅ 100%" if resumo["wand_campeoes_topk_identico"] and
                    resumo["bmw_topk_identico"] else "⚠️ não")

        longo = pd.DataFrame([{"consulta": ln["consulta"], "algoritmo": nome, "ms": ln[f"{chave}_ms"]}
                              for ln in linhas for chave, nome in
                              [("exaustivo", "1. BM25 exaustivo (baseline)"), ("wand", "2. WAND classico"),
                               ("wand_campeoes", "3. WAND + Champion Lists"), ("bmw", "4. Block-Max WAND")]])
        ordem_algo = sorted(longo["algoritmo"].unique())
        ch = alt.Chart(longo).mark_bar(cornerRadiusEnd=3, height=alt.RelativeBandSize(0.85)).encode(
            y=alt.Y("consulta:N", title=None, sort=[ln["consulta"] for ln in linhas]),
            yOffset=alt.YOffset("algoritmo:N", sort=ordem_algo),
            x=alt.X("ms:Q", title="Tempo médio por consulta (ms) · menor é melhor"),
            color=alt.Color("algoritmo:N", sort=ordem_algo,
                            scale=alt.Scale(domain=ordem_algo, range=[LARANJA, AMARELO, AZUL, AQUA])),
            tooltip=["consulta", "algoritmo", alt.Tooltip("ms:Q", format=".3f")])
        st.altair_chart(tema(ch, 34 * len(linhas) + 40), width="stretch")

        tabela = pd.DataFrame([{
            "Consulta": ln["consulta"], "Candidatos": ln["candidatos"],
            "Exaustivo (ms)": ln["exaustivo_ms"], "TAAT+heap (ms)": ln["taat_heap_ms"], "WAND (ms)": ln["wand_ms"],
            "WAND+CL (ms)": ln["wand_campeoes_ms"], "BMW (ms)": ln["bmw_ms"],
            "Δ% WAND+CL": ln["wand_campeoes_delta_pct"], "Speedup": ln["wand_campeoes_speedup"],
            "Poda %": ln["wand_campeoes_poda_docs_pct"], "Top-K =": "✅" if ln["wand_campeoes_mesmo_topk"] else "⚠️",
        } for ln in linhas])
        st.dataframe(tabela, hide_index=True, width="stretch")

        escala = st.session_state.get("escala") or []
        if escala:
            st.markdown("##### Escalabilidade: o ganho cresce com o tamanho da base")
            esc = pd.DataFrame([{"documentos": e["documentos"], "algoritmo": nome, "ms": e[chave]}
                                for e in escala for chave, nome in
                                [("exaustivo_ms_medio", "BM25 exaustivo (baseline)"),
                                 ("wand_campeoes_ms_medio", "WAND + Champion Lists")]])
            ch = alt.Chart(esc).mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=2).encode(
                x=alt.X("documentos:Q", title="Documentos indexados", axis=alt.Axis(format="~s")),
                y=alt.Y("ms:Q", title="Tempo médio (ms)"),
                color=alt.Color("algoritmo:N", scale=alt.Scale(domain=["BM25 exaustivo (baseline)",
                                                                        "WAND + Champion Lists"],
                                                                range=[LARANJA, AZUL])),
                tooltip=["documentos", "algoritmo", alt.Tooltip("ms:Q", format=".3f")])
            st.altair_chart(tema(ch, 280), width="stretch")

    if "bench_ort" in st.session_state:
        linhas_o, resumo_o = st.session_state["bench_ort"]
        st.markdown("##### Correção ortográfica · Trie + k-gramas/Jaccard + Levenshtein vs. Levenshtein força-bruta")
        r = st.columns(4)
        r[0].metric("Força bruta (vocabulário inteiro)", f"{resumo_o['forca_bruta_ms_medio']:.1f} ms")
        r[1].metric("2 estágios", f"{resumo_o['dois_estagios_ms_medio']:.2f} ms",
                    delta=f"-{resumo_o['delta_pct']:.1f}%", delta_color="inverse")
        r[2].metric("Speedup", f"{resumo_o['speedup']:.0f}×")
        r[3].metric("Mesma sugestão", f"{resumo_o['concordancia_pct']:.0f}%")
        st.dataframe(pd.DataFrame(linhas_o), hide_index=True, width="stretch")

    with st.expander("Estatísticas do índice invertido"):
        st.json(motor.indice.estatisticas())

# =============================================== 4. MODELO DIMENSIONAL ==
with aba_modelo:
    st.markdown("#### Granularidade da fato")
    st.success("**`dw.fato_review`: cada linha representa UMA review publicada por um jogador sobre um jogo "
               "na Steam, na data em que a review foi criada.**")
    st.markdown("""
| Tabela | Papel | Chave substituta | Chave natural |
|---|---|---|---|
| `fato_review` | Fato transacional (grão = 1 review) | `sk_fato` | `recommendationid` (degenerada) |
| `dim_tempo` | Calendário (dia, mês, trimestre, semestre, dia da semana) | `sk_tempo` | `data_completa` |
| `dim_jogo` | Jogo avaliado (gênero, desenvolvedora, preço, lançamento) | `sk_jogo` | `app_id` |
| `dim_autor` | Jogador (tamanho da biblioteca, experiência como avaliador) | `sk_autor` | `steamid` |
| `dim_perfil_review` | *Junk dimension*: recomendado, compra, grátis, acesso antecipado, Steam Deck | `sk_perfil` | combinação das 5 flags |
| `dim_review` | Texto da review (corpus da busca) | `sk_review` | `recommendationid` |
""")
    if dw_ok:
        try:
            st.markdown("##### Volume por camada")
            st.dataframe(q.contagem_tabelas(), hide_index=True, width="stretch")
            st.markdown("##### Amostra da fato (só chaves substitutas + métricas)")
            st.dataframe(q.amostra_fato(), hide_index=True, width="stretch")
        except Exception as exc:  # noqa: BLE001
            st.info(f"Tabelas ainda não criadas ({exc.__class__.__name__}).")
