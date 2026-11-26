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
import estilo as ui  # noqa: E402
from src.search_engine.benchmark import (CONSULTAS_PADRAO, ERROS_PADRAO, benchmark_ortografia,  # noqa: E402
                                         benchmark_ranking, mesmo_top)
from src.search_engine.motor import MotorBusca  # noqa: E402
from src.search_engine.text import normalizar, reduzir  # noqa: E402

st.set_page_config(page_title="Steam Reviews Intelligence", page_icon=":material/query_stats:", layout="wide",
                   initial_sidebar_state="collapsed")
st.html(ui.CSS + ui.CSS_TABELA)

MARINHO, ACO, CORAL, PETROLEO = ui.MARINHO, ui.ACO, ui.CORAL, ui.PETROLEO
COR_RECOMENDACAO = alt.Scale(domain=["Recomendado", "Não recomendado"], range=[MARINHO, CORAL])
# numeros no padrao brasileiro nos eixos e tooltips (1.000,5)
LOCALE_BR = {"number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]}}
NOMES_ALGORITMO = {"wand_campeoes": "WAND + Champion Lists", "bmw": "Block-Max WAND", "wand": "WAND clássico"}


def tema(chart: alt.Chart, altura: int = 300) -> alt.Chart:
    """Graficos no tema escuro: fundo transparente, grade recessiva, texto suave."""
    return (chart.properties(height=altura, background="transparent")
            .configure(font=ui.FONTE, locale=LOCALE_BR)
            .configure_axis(gridColor=ui.GRADE, gridDash=[2, 4], domain=False, ticks=False, labelColor=ui.TEXTO_SUAVE,
                            titleColor=ui.TEXTO_SUAVE, labelFontSize=13, titleFontSize=13, titleFontWeight="normal",
                            labelPadding=6)
            .configure_legend(labelColor="#3b4a57", orient="top", title=None, symbolType="circle", labelFontSize=14, symbolSize=120)
            .configure_view(strokeWidth=0))


# ----------------------------------------------------------------- dados
@st.cache_data(ttl=60, show_spinner=False)
def status_dw() -> tuple[bool, str, int, str, int]:
    """(conectado, mensagem, linhas na fato, versao do corpus p/ cache do indice, jogos)."""
    try:
        linha = q.df("""SELECT (SELECT count(*) FROM dw.fato_review) AS total,
                               (SELECT count(DISTINCT sk_jogo) FROM dw.fato_review) AS jogos,
                               (SELECT max(atualizado_em) FROM dw.dim_review)::text AS ultima_edicao""").iloc[0]
        total = int(linha["total"] or 0)
        return True, "conectado", total, f"{total}|{linha['ultima_edicao']}", int(linha["jogos"] or 0)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).splitlines()[0][:160], 0, "offline", 0


@st.cache_data(ttl=120, show_spinner=False)
def status_airflow() -> dict[str, dict]:
    url = os.getenv("AIRFLOW_API_URL", "http://localhost:8080/api/v1")
    auth = (os.getenv("AIRFLOW_API_USER", "airflow"), os.getenv("AIRFLOW_API_PASSWORD", "airflow"))
    saida = {}
    for dag_id in ("dag_ingestao_raw", "dag_consolidacao_dw"):
        try:
            r = requests.get(f"{url}/dags/{dag_id}/dagRuns", params={"order_by": "-execution_date", "limit": 8},
                             auth=auth, timeout=8)
            r.raise_for_status()
            saida[dag_id] = {"ok": True, "runs": r.json().get("dag_runs", [])}
        except Exception as exc:  # noqa: BLE001
            saida[dag_id] = {"ok": False, "erro": exc.__class__.__name__, "runs": []}
    return saida


@st.cache_resource(show_spinner="Indexando o corpus (índice invertido + Trie + k-gramas)...")
def carregar_motor(versao_dw: str, fonte: str) -> MotorBusca:
    if fonte == "dw":
        from src.search_engine.corpus import carregar_corpus
        textos, metas = carregar_corpus()
    else:
        from src.search_engine.sintetico import gerar_corpus
        textos = gerar_corpus(40_000)
        metas = [{"jogo": "Corpus de demonstração", "recomendacao": "-", "horas": 0, "votos_uteis": 0, "data": None}
                 for _ in textos]
    return MotorBusca(textos, metas)


def destacar(texto: str, termos: list[str], limite: int = 600) -> str:
    alvo = set(termos)
    trecho = texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + " …"
    trecho = ui.e(trecho)

    def troca(m: re.Match) -> str:
        palavra = m.group(0)
        return f"<mark>{palavra}</mark>" if alvo and reduzir(normalizar(palavra)) in alvo else palavra
    return re.sub(r"[\wÀ-ÿ]+", troca, trecho)


def fmt_int(v) -> str:
    return f"{int(v):,}".replace(",", ".") if v is not None and pd.notna(v) else "-"


def num(v) -> float:
    """None/NaN -> 0.0 (NaN e "truthy", entao `v or 0` nao basta)."""
    return float(v) if v is not None and pd.notna(v) else 0.0


def pct(v: float, casas: int = 1) -> str:
    return f"{v * 100:.{casas}f}%".replace(".", ",")


def item_review(pos: int | None, doc: dict, termos: list[str]) -> str:
    rec = doc.get("recomendacao")
    selo = ('<span class="rec">Recomenda</span>' if rec == "Recomendado" else
            '<span class="rec nao">Não recomenda</span>' if rec == "Não recomendado" else "")
    score = doc.get("score")
    placar = f'<span class="score">BM25 {score:.3f}</span>' if score is not None else ""
    meta = [f"{num(doc.get('horas')):.1f} h jogadas".replace(".", ","),
            f"{fmt_int(doc.get('votos_uteis', 0))} votos úteis"]
    if doc.get("data"):
        meta.append(str(doc["data"]))
    posicao = f'<div class="pos">{pos:02d}</div>' if pos else ""
    return (f'<div class="painel item{"" if pos else " sem-pos"}">{posicao}<div><div class="cab">'
            f'<span class="jogo">{ui.e(doc.get("jogo", "-"))}</span>{selo}{placar}</div>'
            f'<div class="texto">{destacar(doc.get("texto") or "", termos)}</div>'
            f'<div class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</div></div></div>')


# ---------------------------------------------------------------- layout
dw_ok, dw_msg, total_fato, versao_corpus, total_jogos = status_dw()
fonte_busca = "dw" if dw_ok and total_fato > 0 else "sintetico"

with st.sidebar:
    st.markdown("**Steam Reviews Intelligence**")
    st.caption("T2 · Modelagem Informacional e PLN/RI · FUCAPE 2026")
    st.caption(f"Data Warehouse: **{'conectado' if dw_ok else 'offline'}**")
    if fonte_busca == "sintetico":
        st.caption("A busca usa um corpus de demonstração até a primeira carga do DW.")
    if st.button("Recarregar dados", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.divider()
    st.caption("**Fluxo:** API pública da Steam → Airflow (DAG 1 + DAG 2) → Postgres (Star Schema) → este painel")
    st.caption("[Abrir o Airflow](http://localhost:8080) · Postgres em localhost:5433")

st.html(f"""<div class="painel topo"><div class="marca"><div class="logo"><i></i></div><div>
<h1>Steam Reviews Intelligence</h1>
<div class="sobre">T2 · Modelagem Informacional e PLN/RI · FUCAPE 2026 · João Gilberto Leão Vieira</div>
</div></div><div class="meta">
<span class="pilula"><b>{fmt_int(total_fato)}</b> reviews</span>
<span class="pilula"><b>{fmt_int(total_jogos)}</b> jogos</span>
<span class="pilula escura"><span class="ponto{"" if dw_ok else " off"}"></span>
{"Pipeline ok" if total_fato > 0 else ("DW vazio" if dw_ok else "DW offline")}</span>
</div></div>""")

ABAS = {"negocios": "Visão de Negócios", "busca": "Busca Inteligente", "engenharia": "Engenharia & Benchmark",
        "modelo": "Modelo Dimensional"}
# ?aba=busca abre o painel direto na aba (util para a demonstracao em video)
aba_inicial = ABAS.get(str(st.query_params.get("aba", "")).lower())
aba_negocio, aba_busca, aba_eng, aba_modelo = st.tabs(list(ABAS.values()), default=aba_inicial)

# ======================================================= 1. NEGOCIOS ===
with aba_negocio:
    periodo = q.periodo_disponivel() if dw_ok and total_fato > 0 else None
    if periodo is None:
        st.html(ui.estado_vazio())
    else:
        jogos_df = q.jogos_disponiveis()
        c1, c2 = st.columns([3, 2])
        with c1:
            escolhidos = st.multiselect("Jogos", jogos_df["nome_jogo"].tolist(), placeholder="Todos os jogos")
        with c2:
            intervalo = st.date_input("Período de publicação da review", value=periodo, format="DD/MM/YYYY",
                                      min_value=periodo[0], max_value=periodo[1])
            inicio, fim = intervalo if isinstance(intervalo, (tuple, list)) and len(intervalo) == 2 else periodo
        sks = jogos_df[jogos_df["nome_jogo"].isin(escolhidos)]["sk_jogo"].tolist() if escolhidos \
            else jogos_df["sk_jogo"].tolist()
        p = q.params([int(s) for s in sks], inicio, fim)
        k = q.kpis(p)
        st.html(ui.kpis([
            ("Reviews", fmt_int(k["reviews"]), f"{fmt_int(k['jogos'])} jogos no recorte"),
            ("Recomendam", pct(num(k["pct_rec"])), "das reviews são positivas"),
            ("Horas jogadas", f"{num(k['horas_mediana']):.1f} h".replace(".", ","), "mediana ao escrever"),
            ("Votos úteis", fmt_int(k["votos_uteis"]), "engajamento da comunidade"),
            ("Autores únicos", fmt_int(k["autores"]), "jogadores distintos"),
            ("Palavras", f"{num(k['palavras_media']):.0f}", "média por review"),
        ], destaque=1))

        g1, g2 = st.columns([3, 2])
        with g1, st.container(key="card_mes"):
            st.html(ui.secao("Volume mensal de reviews", "positivas vs. negativas"))
            mes = q.por_mes(p)
            ch = alt.Chart(mes).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="rgba(255,255,255,.9)",
                                         strokeWidth=2).encode(
                x=alt.X("ano_mes:O", title=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y("sum(reviews):Q", title=None),
                color=alt.Color("recomendacao:N", scale=COR_RECOMENDACAO),
                order=alt.Order("recomendacao:N", sort="descending"),
                tooltip=[alt.Tooltip("ano_mes:O", title="Mês"), alt.Tooltip("recomendacao:N", title="Tipo"),
                         alt.Tooltip("sum(reviews):Q", title="Reviews", format=",")])
            st.altair_chart(tema(ch, 380), width="stretch")
        with g2, st.container(key="card_jogo"):
            st.html(ui.secao("Taxa de recomendação", "por jogo"))
            jg = q.por_jogo(p)
            ch = alt.Chart(jg).mark_bar(cornerRadiusEnd=6, color=MARINHO, height=13).encode(
                x=alt.X("pct_rec:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("jogo:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                tooltip=[alt.Tooltip("jogo:N", title="Jogo"), alt.Tooltip("pct_rec:Q", title="% recomendam", format=".1%"),
                         alt.Tooltip("reviews:Q", title="Reviews", format=","),
                         alt.Tooltip("horas_mediana:Q", title="Horas (mediana)", format=".1f")])
            st.altair_chart(tema(ch, max(380, 30 * len(jg))), width="stretch")

        g3, g4, g5 = st.columns(3)
        with g3, st.container(key="card_horas"):
            st.html(ui.secao("Quem joga mais recomenda mais?", "% positivas por horas jogadas"))
            fh = q.por_faixa_horas(p)
            ch = alt.Chart(fh).mark_bar(cornerRadiusEnd=6, color=PETROLEO, width=alt.RelativeBandSize(0.5)).encode(
                x=alt.X("faixa:N", sort=fh["faixa"].tolist(), title=None, axis=alt.Axis(labelAngle=0, labelOverlap=False)),
                y=alt.Y("pct_rec:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                tooltip=[alt.Tooltip("faixa:N", title="Faixa"), alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam"),
                         alt.Tooltip("reviews:Q", format=",", title="Reviews")])
            st.altair_chart(tema(ch, 320), width="stretch")
        with g4, st.container(key="card_semana"):
            st.html(ui.secao("Dia da semana", "quando os jogadores escrevem"))
            ds = q.por_dia_semana(p)
            ch = alt.Chart(ds).mark_bar(cornerRadiusEnd=6, color=MARINHO, width=alt.RelativeBandSize(0.5)).encode(
                x=alt.X("dia_semana:N", sort=ds["dia_semana"].tolist(), title=None,
                        axis=alt.Axis(labelAngle=0, labelExpr="slice(datum.label, 0, 3)")),
                y=alt.Y("reviews:Q", title=None),
                tooltip=[alt.Tooltip("dia_semana:N", title="Dia"), alt.Tooltip("reviews:Q", format=",", title="Reviews"),
                         alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam")])
            st.altair_chart(tema(ch, 320), width="stretch")
        with g5, st.container(key="card_origem"):
            st.html(ui.secao("Origem da cópia", "compra, key ou presente"))
            aq = q.por_aquisicao(p)
            ch = alt.Chart(aq).mark_bar(cornerRadiusEnd=6, color=MARINHO, height=18).encode(
                y=alt.Y("aquisicao:N", sort="-x", title=None, axis=alt.Axis(labelLimit=130)),
                x=alt.X("reviews:Q", title=None),
                tooltip=[alt.Tooltip("aquisicao:N", title="Origem"), alt.Tooltip("reviews:Q", format=",", title="Reviews"),
                         alt.Tooltip("pct_rec:Q", format=".1%", title="% recomendam")])
            st.altair_chart(tema(ch, 320), width="stretch")

        st.html(ui.secao("Gêneros", "volume e satisfação por gênero principal"))
        st.html(ui.tabela(q.por_genero(p), [("genero", "Gênero principal", "forte"), ("jogos", "Jogos", "int"),
                                            ("reviews", "Reviews", "int"), ("pct_rec", "Recomendam", "barra")]))

        st.html(ui.secao("As reviews mais úteis", "segundo os votos da própria comunidade"))
        uteis = q.mais_uteis(p)
        st.html('<div class="lista">' + "".join(item_review(None, ln.to_dict(), []) for _, ln in uteis.iterrows())
                + "</div>")

# ========================================================== 2. BUSCA ===
with aba_busca:
    motor = carregar_motor(versao_corpus, fonte_busca)
    c1, c2, c3, c4 = st.columns([5, 1.1, 2, 1.4], vertical_alignment="bottom")
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
    sugestoes = motor.corretor.autocompletar(ultimo) if len(ultimo) >= 2 else []
    st.html(f'<div class="auto"><span>Autocompletar (Trie):</span>'
            f'{" ".join(f"<span class=\'sug\'>{ui.e(s)}</span>" for s in sugestoes[:8]) or "<span>—</span>"}'
            f'<span class="dir">{fmt_int(motor.indice.n_docs)} reviews indexadas · '
            f'{fmt_int(len(motor.indice.postagens))} termos</span></div>')

    if consulta.strip():
        resp = motor.buscar(consulta, int(k_top), algoritmo, corrigir)
        termos = ", ".join(resp.resultado.termos) or "nenhum termo do vocabulário"
        if resp.correcoes:
            trocas = ", ".join(f"<s>{ui.e(a)}</s> → {ui.e(b)}" for a, b in resp.correcoes)
            ms = f"{resp.tempo_correcao_ms:.2f}".replace(".", ",")
            correcao = f" · corrigido: {trocas} em {ms} ms"
        else:
            correcao = ""
        st.html(f'<div class="nota">Buscando por <b>{ui.e(resp.consulta_usada)}</b>'
                f'<span class="suave">{correcao} · termos do índice: {ui.e(termos)}</span></div>')
        candidatos = len({d for t in resp.resultado.termos for d in motor.indice.postagens[t].docs}) \
            if resp.resultado.termos else 0
        avaliados = resp.resultado.stats.get("docs_pontuados", 0)
        identico = mesmo_top(resp.resultado, resp.baseline)
        st.html(ui.duelo("BM25 exaustivo", resp.tempo_baseline_ms, NOMES_ALGORITMO[algoritmo],
                         resp.tempo_otimizado_ms, resp.speedup, resp.delta_pct,
                         f"baseline · pontua os {fmt_int(motor.indice.n_docs)} docs e ordena tudo",
                         f"otimizado · poda dinâmica segura + heap Top-{int(k_top)}"))
        st.html(ui.kpis([
            ("Docs pontuados", f"{fmt_int(avaliados)} / {fmt_int(candidatos)}", "otimizado / candidatos"),
            ("Taxa de poda", pct(1 - avaliados / candidatos) if candidatos else "—", "avaliações evitadas"),
            ("Top-K igual ao exaustivo", "sim" if identico else "não", "mesmos docs, ordem e scores"),
            ("Resultados", fmt_int(len(resp.docs)), f"Top-{int(k_top)} por relevância BM25"),
        ], destaque=2 if identico else None))

        if not resp.docs:
            st.html('<div class="vazio"><h3>Nenhuma review contém esses termos</h3>'
                    '<p>Tente outras palavras ou ative a correção de erros.</p></div>')
        st.html('<div class="lista">' + "".join(item_review(i, d, resp.resultado.termos)
                                                for i, d in enumerate(resp.docs, 1)) + "</div>")

# ================================================ 3. ENGENHARIA ========
with aba_eng:
    st.html(ui.secao("Saúde dos pipelines", "estado das últimas execuções via API REST do Airflow"))
    af = status_airflow()
    cartoes = []
    for dag_id, papel in (("dag_ingestao_raw", "DAG 1 · ingestão resiliente → raw"),
                          ("dag_consolidacao_dw", "DAG 2 · consolidação → star schema")):
        info = af[dag_id]
        if not info["ok"]:
            estado, sub, pontos = '<span class="estado">API indisponível</span>', f"{papel} · {info['erro']}", ""
        elif not info["runs"]:
            estado, sub, pontos = '<span class="estado">sem execuções</span>', papel, ""
        else:
            ultima = info["runs"][0]
            quando = str(ultima.get("end_date") or ultima.get("start_date") or "")[:16].replace("T", " ")
            estado = f'<span class="estado {ui.e(ultima["state"])}">{ui.e(ultima["state"])}</span>'
            sub = f"{papel} · última em {quando}"
            pontos = "".join(f'<i class="{ui.e(r["state"])}" title="{ui.e(r["state"])}"></i>'
                             for r in reversed(info["runs"]))
        cartoes.append(f'<div class="painel dag"><span class="nome">{dag_id}</span>{estado}'
                       f'<div class="sub">{ui.e(sub)}</div><div class="pontos">{pontos}</div></div>')
    st.html(f'<div class="dags">{"".join(cartoes)}</div>')

    if dw_ok:
        try:
            ing = q.ultima_ingestao()
            if not ing.empty:
                st.html(ui.secao("DAG 1 · última ingestão", "paginação por cursor, backoff e rate limit por jogo"))
                st.html(ui.kpis([
                    ("Requisições HTTP", fmt_int(ing["requisicoes"].sum()), "à API da Steam"),
                    ("Retentativas", fmt_int(ing["retentativas"].sum()), "exponential backoff + jitter"),
                    ("Respostas 429", fmt_int(ing["respostas_429"].sum()), "rate limit tratado"),
                    ("Novas / alteradas", f"{fmt_int(ing['novas'].sum())} / {fmt_int(ing['alteradas'].sum())}",
                     "upsert idempotente"),
                ]))
                st.html(ui.tabela(ing, [
                    ("jogo", "Jogo", "forte"), ("entidade", "Entidade", "txt"), ("status", "Status", "estado"),
                    ("paginas", "Páginas", "int"), ("recebidas", "Recebidas", "int"), ("novas", "Novas", "int"),
                    ("alteradas", "Alteradas", "int"), ("requisicoes", "Requisições", "int"),
                    ("retentativas", "Retentativas", "int"), ("respostas_429", "HTTP 429", "int"),
                    ("motivo_parada", "Motivo da parada", "txt"), ("segundos", "Duração (s)", "num")]))
            etl = q.historico_etl()
            if not etl.empty:
                st.html(ui.secao("DAG 2 · prova de idempotência",
                                 "reexecutar mantém total_fato e soma_votos_uteis constantes"))
                st.html(ui.tabela(etl, [
                    ("run_id", "Execução", "forte"), ("finalizado_em", "Finalizada", "data"), ("status", "Status", "estado"),
                    ("linhas_staging", "Staging", "int"), ("fato_inseridas", "Inseridas", "int"),
                    ("fato_atualizadas", "Atualizadas", "int"), ("total_fato", "Total na fato", "int"),
                    ("soma_votos_uteis", "Σ votos úteis", "int"), ("checks", "Checks de qualidade", "checks")]))
            hist = q.historico_ingestao()
            if not hist.empty:
                st.html(ui.secao("DAG 1 · histórico", "execuções recentes da ingestão"))
                st.html(ui.tabela(hist, [
                    ("run_id", "Execução", "forte"), ("inicio", "Início", "data"), ("ok", "Jogos ok", "int"),
                    ("erros", "Erros", "int"), ("recebidas", "Recebidas", "int"), ("novas", "Novas", "int"),
                    ("alteradas", "Alteradas", "int"), ("retentativas", "Retentativas", "int"),
                    ("respostas_429", "HTTP 429", "int")]))
        except Exception as exc:  # noqa: BLE001
            st.info(f"Tabelas de auditoria ainda não existem ({exc.__class__.__name__}). Rode os DAGs.")

    st.html(ui.secao("Benchmark · Antes vs. Depois",
                     "mesmo índice e mesmas consultas · time.perf_counter() · Δ% = (T_base − T_opt) / T_base"))
    b1, b2, b3 = st.columns([1, 1, 2], vertical_alignment="bottom")
    repeticoes = b1.slider("Repetições", 3, 30, 7)
    k_bench = b2.slider("K", 1, 100, 10)
    if b3.button("Rodar benchmark completo", type="primary", width="stretch"):
        with st.spinner("Medindo 5 algoritmos × 12 consultas + correção ortográfica..."):
            st.session_state["bench"] = benchmark_ranking(motor.indice, CONSULTAS_PADRAO, k_bench, repeticoes)
            st.session_state["bench_ort"] = benchmark_ortografia(motor.corretor, ERROS_PADRAO, 3)
            st.session_state["bench_origem"] = "medido agora neste painel"

    if "bench" not in st.session_state:
        salvo = RAIZ / "docs" / "resultados_benchmark.json"
        if salvo.exists():
            dados = json.loads(salvo.read_text(encoding="utf-8"))
            st.session_state["bench"] = (dados["ranking"]["consultas"], dados["ranking"]["resumo"])
            st.session_state["bench_ort"] = (dados["ortografia"]["palavras"], dados["ortografia"]["resumo"])
            st.session_state["escala"] = dados.get("escala", [])
            st.session_state["bench_origem"] = f"último benchmark salvo · {dados['corpus']} · {dados['ambiente']['gerado_em']}"

    if "bench" in st.session_state:
        linhas, resumo = st.session_state["bench"]
        st.caption(f"Fonte: {st.session_state.get('bench_origem', '')}")
        st.html(ui.duelo("BM25 exaustivo", resumo["exaustivo_ms_medio"], "WAND + Champion Lists",
                         resumo["wand_campeoes_ms_medio"], resumo["wand_campeoes_speedup"],
                         resumo["wand_campeoes_delta_pct"], f"média de {resumo['consultas']} consultas",
                         f"poda de {resumo['wand_campeoes_poda_docs_pct']:.1f}% dos candidatos"))
        identico = resumo["wand_campeoes_topk_identico"] and resumo["bmw_topk_identico"]
        st.html(ui.kpis([
            ("WAND clássico", f"{resumo['wand_ms_medio']:.2f} ms", f"{resumo['wand_speedup']:.1f}× · sem aquecer o heap"),
            ("Block-Max WAND", f"{resumo['bmw_ms_medio']:.2f} ms", f"{resumo['bmw_speedup']:.1f}× · poda {resumo['bmw_poda_docs_pct']:.1f}%"),
            ("TAAT + heap", f"{resumo['taat_heap_ms_medio']:.2f} ms", f"{resumo['taat_heap_speedup']:.1f}× · ablação, sem poda"),
            ("Memória/consulta", f"{resumo.get('wand_campeoes_mem_kb_medio', 0):.0f} KB",
             f"vs. {resumo.get('exaustivo_mem_kb_medio', 0):,.0f} KB no exaustivo".replace(",", ".")),
            ("Top-K igual ao exaustivo", "100%" if identico else "não", "poda segura"),
        ], destaque=4 if identico else None))

        longo = pd.DataFrame([{"consulta": ln["consulta"], "algoritmo": nome, "ms": ln[f"{chave}_ms"]}
                              for ln in linhas for chave, nome in
                              [("exaustivo", "1. BM25 exaustivo (baseline)"), ("wand", "2. WAND clássico"),
                               ("wand_campeoes", "3. WAND + Champion Lists"), ("bmw", "4. Block-Max WAND")]])
        ordem_algo = sorted(longo["algoritmo"].unique())
        with st.container(key="card_bench"):
            st.html(ui.secao("Tempo por consulta", "menor é melhor"))
            ch = alt.Chart(longo).mark_bar(cornerRadiusEnd=4, height=alt.RelativeBandSize(0.8)).encode(
                y=alt.Y("consulta:N", title=None, sort=[ln["consulta"] for ln in linhas], axis=alt.Axis(labelLimit=220)),
                yOffset=alt.YOffset("algoritmo:N", sort=ordem_algo),
                x=alt.X("ms:Q", title="ms"),
                color=alt.Color("algoritmo:N", sort=ordem_algo,
                                scale=alt.Scale(domain=ordem_algo, range=[CORAL, ACO, MARINHO, PETROLEO])),
                tooltip=["consulta", "algoritmo", alt.Tooltip("ms:Q", format=".3f")])
            st.altair_chart(tema(ch, 44 * len(linhas) + 50), width="stretch")

        st.html(ui.secao("Resultado por consulta", "todas as medições do benchmark"))
        st.html(ui.tabela(linhas, [
            ("consulta", "Consulta", "forte"), ("candidatos", "Candidatos", "int"),
            ("exaustivo_ms", "Exaustivo", "ms"), ("taat_heap_ms", "TAAT + heap", "ms"), ("wand_ms", "WAND", "ms"),
            ("wand_campeoes_ms", "WAND + CL", "ms"), ("bmw_ms", "Block-Max", "ms"),
            ("wand_campeoes_speedup", "Speedup", "x"), ("wand_campeoes_poda_docs_pct", "Poda", "pct100"),
            ("wand_campeoes_mesmo_topk", "Top-K igual", "bool")]))

        escala = st.session_state.get("escala") or []
        if escala:
            with st.container(key="card_escala"):
                st.html(ui.secao("Escalabilidade", "o custo do exaustivo cresce com N; o do WAND, quase só com K"))
                esc = pd.DataFrame([{"documentos": e["documentos"], "algoritmo": nome, "ms": e[chave]}
                                    for e in escala for chave, nome in
                                    [("exaustivo_ms_medio", "BM25 exaustivo (baseline)"),
                                     ("wand_campeoes_ms_medio", "WAND + Champion Lists")]])
                ch = alt.Chart(esc).mark_line(point=alt.OverlayMarkDef(size=80, filled=True), strokeWidth=2.5).encode(
                    x=alt.X("documentos:Q", title="documentos indexados", axis=alt.Axis(format="~s")),
                    y=alt.Y("ms:Q", title="ms"),
                    color=alt.Color("algoritmo:N", scale=alt.Scale(domain=["BM25 exaustivo (baseline)",
                                                                            "WAND + Champion Lists"],
                                                                    range=[CORAL, MARINHO])),
                    tooltip=["documentos", "algoritmo", alt.Tooltip("ms:Q", format=".3f")])
                st.altair_chart(tema(ch, 340), width="stretch")

    if "bench_ort" in st.session_state:
        linhas_o, resumo_o = st.session_state["bench_ort"]
        st.html(ui.secao("Correção ortográfica", "Trie + k-gramas/Jaccard + Levenshtein vs. Levenshtein força-bruta"))
        st.html(ui.duelo("Levenshtein força-bruta", resumo_o["forca_bruta_ms_medio"], "2 estágios",
                         resumo_o["dois_estagios_ms_medio"], resumo_o["speedup"], resumo_o["delta_pct"],
                         "compara com o vocabulário inteiro",
                         f"mesma sugestão em {resumo_o['concordancia_pct']:.0f}% dos casos"))
        st.html(ui.tabela(linhas_o, [
            ("digitado", "Digitado", "forte"), ("sugestao_dois_estagios", "Sugestão", "txt"),
            ("forca_bruta_ms", "Força bruta", "ms"), ("dois_estagios_ms", "2 estágios", "ms"), ("speedup", "Speedup", "x"),
            ("candidatos_levenshtein", "Candidatos", "int"), ("vocabulario", "Vocabulário", "int"),
            ("mesma_sugestao", "Mesma sugestão", "bool")]))

    est = motor.indice.estatisticas()
    st.html(ui.secao("Índice invertido", "estruturas usadas pela busca"))
    st.html(ui.kpis([
        ("Documentos", fmt_int(est["documentos"]), "reviews indexadas"),
        ("Vocabulário", fmt_int(est["vocabulario"]), "termos distintos"),
        ("Postagens", fmt_int(est["postagens"]), "pares termo-documento"),
        ("Blocos", fmt_int(est["blocos"]), f"de {est['tamanho_bloco']} postagens (Block-Max)"),
        ("Memória", f"{est['memoria_postagens_mb']:.1f} MB".replace(".", ","), "listas de postagens"),
    ]))

# =============================================== 4. MODELO DIMENSIONAL ==
with aba_modelo:
    st.html('<div class="painel grao"><b>Granularidade da fato dw.fato_review:</b> cada linha representa '
            'uma review publicada por um jogador sobre um jogo na Steam, na data em que a review foi criada.</div>')
    st.html(ui.secao("Star Schema", "surrogate keys inteiras · membro desconhecido −1 · FKs reais"))
    st.html(ui.diagrama_estrela())
    if dw_ok:
        try:
            st.html(ui.secao("Volume por camada", "bronze (raw) → staging → Data Warehouse"))
            st.html(ui.tabela(q.contagem_tabelas(), [("camada", "Camada", "camada"), ("tabela", "Tabela", "forte"),
                                                     ("papel", "Papel", "txt"), ("linhas", "Linhas", "int")]))
            st.html(ui.secao("Amostra da fato", "só chaves substitutas e métricas"))
            st.html(ui.tabela(q.amostra_fato(), [
                ("sk_fato", "sk_fato", "int"), ("sk_tempo", "sk_tempo", "int"), ("sk_jogo", "sk_jogo", "int"),
                ("sk_autor", "sk_autor", "int"), ("sk_perfil", "sk_perfil", "int"), ("sk_review", "sk_review", "int"),
                ("recommendationid", "recommendationid", "txt"), ("qtd_reviews", "qtd_reviews", "int"),
                ("qtd_recomendacoes", "recomendações", "int"), ("votos_uteis", "votos_uteis", "int"),
                ("minutos_jogados_review", "min. na review", "int"), ("score_utilidade", "score", "num")]))
        except Exception as exc:  # noqa: BLE001
            st.info(f"Tabelas ainda não criadas ({exc.__class__.__name__}).")
