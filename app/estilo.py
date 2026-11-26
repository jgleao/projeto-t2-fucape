"""Identidade visual do painel: vidro fosco claro sobre fundo prata-azulado.

Paineis translucidos com borda branca suave, numeros grandes em peso fino,
pilulas azul-marinho para estados ativos e graficos quase monocromaticos.
"""

from __future__ import annotations

from html import escape

# Paleta dos graficos: marinho (principal), aco (secundario), coral (negativo), petroleo (4a serie)
MARINHO, ACO, CORAL, PETROLEO = "#1f3247", "#93a7b5", "#d9775c", "#3d7d8a"
TEXTO_SUAVE, GRADE = "#6b7c8a", "#c3d0d8"
FONTE = "Manrope, Segoe UI, Helvetica Neue, Arial, sans-serif"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&display=swap');


:root {
  --tinta: #1e2a36; --suave: #6b7c8a; --fraco: #98a7b2; --marinho: #1f3247; --coral: #d9775c;
  --vidro: rgba(255,255,255,.46); --vidro-forte: rgba(255,255,255,.66); --borda: rgba(255,255,255,.75);
  --sombra: 0 10px 40px rgba(31,50,71,.07), 0 1px 2px rgba(31,50,71,.04);
}
html, body, [class*="st-"], .stMarkdown, button, input, textarea, select {
  font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif !important;
}
.num {font-variant-numeric: tabular-nums;}

.stApp {
  background:
    radial-gradient(900px 600px at 12% 0%, rgba(255,255,255,.85), transparent 60%),
    radial-gradient(800px 600px at 100% 100%, rgba(183,207,214,.55), transparent 60%),
    linear-gradient(160deg, #eef2f4 0%, #e3eaee 45%, #d3dfe4 100%) !important;
  background-attachment: fixed !important;
}
.block-container {padding-top: 1.6rem !important; max-width: 1320px;}
header[data-testid="stHeader"] {background: transparent !important;}
.stAppDeployButton, #MainMenu, footer {display: none !important;}

section[data-testid="stSidebar"] {
  background: rgba(255,255,255,.38) !important; backdrop-filter: blur(22px);
  border-right: 1px solid var(--borda);
}
.stButton button {
  border-radius: 999px !important; border: 0 !important; background: var(--marinho) !important;
  color: #fff !important; font-weight: 500; padding: .5rem 1.2rem;
  box-shadow: 0 6px 18px rgba(31,50,71,.22);
}
.stButton button p {color: #fff !important;}

/* abas em pilula: ativa em marinho (Streamlit >= 1.50 usa react-aria: role=tablist / data-testid=stTab) */
.stTabs > div:first-child {border: 0 !important; box-shadow: none !important; overflow: visible !important;}
.stTabs [role="tablist"] {
  gap: 4px; background: var(--vidro); border: 1px solid var(--borda); border-radius: 999px;
  padding: 5px; width: fit-content; max-width: 100%; backdrop-filter: blur(18px); box-shadow: var(--sombra);
}
.stTabs [data-testid="stTab"] {
  border-radius: 999px !important; padding: 7px 18px !important; height: auto !important; border: 0 !important;
  background: transparent; cursor: pointer; transition: background .15s ease;
}
.stTabs [data-testid="stTab"]:hover {background: rgba(255,255,255,.6);}
.stTabs [data-testid="stTab"] p {font-size: .88rem; font-weight: 500; color: var(--suave); margin: 0;}
.stTabs [data-testid="stTab"][aria-selected="true"] {background: var(--marinho) !important; box-shadow: 0 6px 18px rgba(31,50,71,.22);}
.stTabs [data-testid="stTab"][aria-selected="true"] p {color: #fff !important;}
.stTabs .react-aria-SelectionIndicator {display: none !important;}
.stTabs [role="tabpanel"] {padding-top: 1.3rem;}

/* entradas como vidro */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
  background: var(--vidro-forte) !important; border-radius: 14px !important; border-color: var(--borda) !important;
}
label p {color: var(--suave) !important; font-size: .8rem !important;}

/* containers com key "card..." viram paineis de vidro */
div[class*="st-key-card"] {
  background: var(--vidro); border: 1px solid var(--borda); border-radius: 22px; padding: 20px 22px 10px;
  backdrop-filter: blur(18px); box-shadow: var(--sombra);
}
div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden; border: 1px solid var(--borda); box-shadow: var(--sombra);}
div[data-testid="stExpander"] details {border-radius: 16px; border: 1px solid var(--borda); background: var(--vidro);}

/* ---------- componentes ---------- */
.painel {background: var(--vidro); border: 1px solid var(--borda); border-radius: 22px;
  backdrop-filter: blur(18px); box-shadow: var(--sombra);}

.topo {display: flex; justify-content: space-between; align-items: center; gap: 28px; padding: 22px 26px; margin-bottom: 18px;}
.topo .marca {display: flex; align-items: center; gap: 14px;}
.topo .logo {width: 40px; height: 40px; border-radius: 12px; background: var(--marinho); display: grid; place-items: center;
  box-shadow: 0 6px 18px rgba(31,50,71,.25);}
.topo .logo i {width: 14px; height: 14px; border-radius: 50%; border: 3px solid #fff; display: block;}
.topo h1 {font-size: 1.45rem; font-weight: 500; margin: 0; color: var(--tinta); letter-spacing: -.01em;}
.topo .sobre {font-size: .78rem; color: var(--suave); margin-top: 2px;}
.topo .meta {display: flex; gap: 10px;}
.pilula {display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 999px; font-size: .82rem;
  background: var(--vidro-forte); border: 1px solid var(--borda); color: var(--tinta);}
.pilula b {font-weight: 600;}
.pilula.escura {background: var(--marinho); color: #fff; border-color: var(--marinho);}
.pilula .ponto {width: 7px; height: 7px; border-radius: 50%; background: #3f9b74;}
.pilula .ponto.off {background: var(--coral);}

.secao {margin: 4px 0 12px;}
.secao h3 {font-size: 1.02rem; font-weight: 500; margin: 0; color: var(--tinta);}
.secao span {display: block; color: var(--fraco); font-size: .8rem; margin-top: 1px;}

.kpis {display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 4px 26px; padding: 22px 26px; margin-bottom: 16px;}
.kpi .l {font-size: .74rem; color: var(--suave);}
.kpi .v {font-size: 2.1rem; font-weight: 300; color: var(--tinta); letter-spacing: -.02em; line-height: 1.15;
  font-variant-numeric: tabular-nums; margin-top: 4px;}
.kpi .s {font-size: .74rem; color: var(--fraco); margin-top: 2px;}
.kpi.destaque .v {color: var(--marinho); font-weight: 400;}
.kpi:first-child .v {font-size: 2.4rem;}

.comparacao {padding: 22px 26px; margin-bottom: 16px; display: grid; grid-template-columns: 1fr 200px; gap: 26px; align-items: center;}
.linha-c {display: grid; grid-template-columns: 220px 1fr 96px; align-items: center; gap: 16px; padding: 9px 0;}
.linha-c .n {font-size: .88rem; color: var(--tinta); font-weight: 500;}
.linha-c .n small {display: block; color: var(--fraco); font-size: .74rem; font-weight: 400;}
.linha-c .trilho {height: 10px; border-radius: 999px; background: rgba(31,50,71,.07); overflow: hidden;}
.linha-c .trilho div {height: 100%; min-width: 4px; border-radius: 999px;}
.linha-c .base div {background: repeating-linear-gradient(135deg, #93a7b5 0 4px, #b6c5cf 4px 8px);}
.linha-c .opt div {background: var(--marinho);}
.linha-c .ms {font-size: 1.05rem; font-weight: 300; text-align: right; color: var(--tinta); font-variant-numeric: tabular-nums;}
.selo-delta {border-radius: 18px; padding: 16px 18px; background: var(--vidro-forte); border: 1px solid var(--borda);}
.selo-delta .x {font-size: 2.4rem; font-weight: 300; color: var(--tinta); letter-spacing: -.02em; line-height: 1;}
.selo-delta .t {font-size: .8rem; color: var(--suave); margin-top: 6px;}

.nota {font-size: .88rem; color: var(--tinta); padding: 11px 18px; margin: 0 0 12px; border-radius: 14px;
  background: var(--vidro-forte); border: 1px solid var(--borda);}
.nota s {color: var(--fraco);} .nota .suave {color: var(--suave);}
.auto {font-size: .78rem; color: var(--suave); margin: -4px 0 14px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;}
.auto .sug {padding: 3px 11px; border-radius: 999px; background: var(--vidro-forte); border: 1px solid var(--borda); color: var(--tinta);}
.auto .dir {margin-left: auto; color: var(--fraco);}

.lista {display: grid; gap: 10px;}
.item {display: grid; grid-template-columns: 46px 1fr; gap: 0 10px; padding: 16px 20px;}
.item.sem-pos {grid-template-columns: 1fr;}
.item .pos {width: 32px; height: 32px; border-radius: 50%; background: var(--marinho); color: #fff; font-size: .78rem;
  display: grid; place-items: center; font-variant-numeric: tabular-nums;}
.item .cab {display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;}
.item .jogo {font-weight: 600; color: var(--tinta);}
.item .rec {font-size: .76rem; color: var(--suave); padding: 2px 10px; border-radius: 999px; background: rgba(31,50,71,.06);}
.item .rec.nao {color: #a4513a; background: rgba(217,119,92,.12);}
.item .score {margin-left: auto; font-size: .78rem; color: var(--fraco); font-variant-numeric: tabular-nums;}
.item .texto {color: #3b4a57; line-height: 1.6; font-size: .92rem; margin-top: 6px;}
.item .meta {color: var(--fraco); font-size: .76rem; margin-top: 8px;}
.item .meta span + span::before {content: "·"; margin: 0 8px;}
mark {background: rgba(31,50,71,.12); color: var(--marinho); font-weight: 600; padding: 0 3px; border-radius: 4px;}

.vazio {padding: 26px 28px;}
.vazio h3 {margin: 0 0 4px; font-size: 1.05rem; font-weight: 500;}
.vazio p {color: var(--suave); margin: 0 0 14px; font-size: .9rem;}
.vazio ol {margin: 0; padding-left: 20px; color: var(--tinta); font-size: .9rem; line-height: 2;}

.dags {display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;}
.dag {padding: 18px 22px;}
.dag .nome {font-size: .92rem; font-weight: 600; color: var(--tinta);}
.dag .estado {font-size: .76rem; margin-left: 10px; padding: 3px 10px; border-radius: 999px; background: rgba(31,50,71,.07); color: var(--suave);}
.dag .estado.success {background: rgba(63,155,116,.14); color: #2f7a5a;}
.dag .estado.failed {background: rgba(217,119,92,.16); color: #a4513a;}
.dag .estado.running, .dag .estado.queued {background: rgba(31,50,71,.12); color: var(--marinho);}
.dag .sub {font-size: .8rem; color: var(--suave); margin-top: 6px;}
.pontos {display: flex; gap: 4px; margin-top: 12px;}
.pontos i {width: 18px; height: 6px; border-radius: 4px; background: rgba(31,50,71,.12);}
.pontos i.success {background: #3f9b74;} .pontos i.failed {background: var(--coral);}
.pontos i.running, .pontos i.queued {background: var(--marinho);}

.estrela {display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;}
.tabela {padding: 14px 16px; font-size: .8rem;}
.tabela h4 {margin: 0; font-size: .9rem; font-weight: 600; color: var(--tinta);}
.tabela .papel {color: var(--fraco); font-size: .74rem; margin: 2px 0 8px;}
.tabela div.c {display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; border-top: 1px solid rgba(31,50,71,.06); color: #3b4a57;}
.tabela .pk {color: var(--tinta); font-weight: 600;} .tabela .fk {color: #3d7d8a; font-weight: 500;}
.tabela .t, .tabela .selo {color: var(--fraco); font-size: .72rem;}
.tabela.fato {grid-column: 2; grid-row: 1 / span 2; background: rgba(31,50,71,.92); border-color: rgba(31,50,71,.92);}
.tabela.fato h4, .tabela.fato .pk, .tabela.fato div.c {color: #fff;}
.tabela.fato .papel, .tabela.fato .t, .tabela.fato .selo {color: #a9bccb;}
.tabela.fato .fk {color: #9fd3dd;} .tabela.fato div.c {border-top-color: rgba(255,255,255,.08);}
.tabela.baixo {grid-column: 2;}
.grao {padding: 16px 22px; margin-bottom: 16px; font-size: .95rem; color: var(--tinta);}
.grao b {font-weight: 600;}

@media (max-width: 900px) {
  .topo {flex-direction: column; align-items: flex-start;}
  .dags, .estrela, .comparacao {grid-template-columns: 1fr;}
  .tabela.fato, .tabela.baixo {grid-column: auto; grid-row: auto;}
  .linha-c {grid-template-columns: 1fr 80px;} .linha-c .trilho {grid-column: 1 / -1; grid-row: 2;}
}
</style>
"""


def e(valor) -> str:
    return escape(str(valor), quote=True)


def secao(titulo: str, subtitulo: str = "") -> str:
    sub = f"<span>{e(subtitulo)}</span>" if subtitulo else ""
    return f'<div class="secao"><h3>{e(titulo)}</h3>{sub}</div>'


def kpis(itens: list[tuple], destaque: int | None = None) -> str:
    """Painel de numeros grandes. itens = [(rotulo, valor, sub), ...]"""
    celulas = []
    for i, item in enumerate(itens):
        rotulo, valor, sub = (list(item) + [""])[:3]
        classe = "kpi destaque" if i == destaque else "kpi"
        celulas.append(f'<div class="{classe}"><div class="l">{e(rotulo)}</div><div class="v">{e(valor)}</div>'
                       f'<div class="s">{e(sub)}</div></div>')
    return f'<div class="painel kpis">{"".join(celulas)}</div>'


def duelo(nome_base: str, ms_base: float, nome_opt: str, ms_opt: float, speedup: float, delta: float,
          detalhe_base: str = "", detalhe_opt: str = "") -> str:
    maior = max(ms_base, ms_opt, 1e-9)
    fator = f"{speedup:.0f}×" if speedup >= 10 else f"{speedup:.1f}×".replace(".", ",")
    texto = (f"mais rápido · {abs(delta):.1f}% menos tempo" if speedup >= 1
             else f"mais lento · {abs(delta):.1f}% a mais").replace(".", ",")
    linha = ('<div class="linha-c"><div class="n">{n}<small>{d}</small></div>'
             '<div class="trilho {c}"><div style="width:{w:.1f}%"></div></div><div class="ms">{ms} ms</div></div>')
    fmt = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
    return ('<div class="painel comparacao"><div>'
            + linha.format(n=e(nome_base), d=e(detalhe_base), c="base", w=100 * ms_base / maior, ms=fmt(ms_base))
            + linha.format(n=e(nome_opt), d=e(detalhe_opt), c="opt", w=100 * ms_opt / maior, ms=fmt(ms_opt))
            + f'</div><div class="selo-delta"><div class="x">{fator}</div><div class="t">{e(texto)}</div></div></div>')


def estado_vazio() -> str:
    return """<div class="painel vazio"><h3>O Data Warehouse ainda está vazio</h3>
<p>Os gráficos aparecem quando o pipeline terminar de coletar as reviews da Steam.</p>
<ol><li>Abra o Airflow em <b>localhost:8080</b> (usuário e senha <b>airflow</b>).</li>
<li>Dispare <b>dag_ingestao_raw</b>; a <b>dag_consolidacao_dw</b> roda em seguida, disparada pelo Dataset.</li>
<li>Clique em <b>Recarregar dados</b> na barra lateral.</li></ol></div>"""


def _col(nome: str, tipo: str, marca: str = "") -> str:
    classe = {"PK": "pk", "FK": "fk"}.get(marca, "")
    direita = {"A": "aditiva", "SA": "semiaditiva", "NA": "não aditiva"}.get(marca)
    direita = f'<span class="selo">{direita}</span>' if direita else f'<span class="t">{e(tipo)}</span>'
    prefixo = f"{marca} " if marca in ("PK", "FK") else ""
    return f'<div class="c"><span class="{classe}">{prefixo}{e(nome)}</span>{direita}</div>'


def diagrama_estrela() -> str:
    def tab(nome, papel, colunas, classe=""):
        return (f'<div class="painel tabela {classe}"><h4>{e(nome)}</h4><div class="papel">{e(papel)}</div>'
                + "".join(_col(*c) for c in colunas) + "</div>")
    fato = tab("fato_review", "grão: uma linha por review", [
        ("sk_fato", "bigint", "PK"), ("sk_tempo", "int", "FK"), ("sk_jogo", "int", "FK"), ("sk_autor", "int", "FK"),
        ("sk_perfil", "int", "FK"), ("sk_review", "int", "FK"), ("recommendationid", "degenerada"),
        ("qtd_reviews", "", "A"), ("qtd_recomendacoes", "", "A"), ("votos_uteis", "", "A"),
        ("minutos_jogados_review", "", "A"), ("qtd_palavras", "", "A"), ("minutos_jogados_total", "", "SA"),
        ("score_utilidade", "", "NA")], "fato")
    tempo = tab("dim_tempo", "calendário", [("sk_tempo", "int", "PK"), ("data_completa", "date"),
                                             ("ano, trimestre, mês", "int"), ("dia_semana", "text")])
    jogo = tab("dim_jogo", "SCD tipo 1 · chave natural app_id", [
        ("sk_jogo", "int", "PK"), ("nome_jogo", "text"), ("genero_principal", "text"), ("preco_base_brl", "numeric")])
    autor = tab("dim_autor", "SCD tipo 1 · chave natural steamid", [
        ("sk_autor", "int", "PK"), ("qtd_jogos_possuidos", "int"), ("faixa_biblioteca", "text"),
        ("perfil_avaliador", "text")])
    perfil = tab("dim_perfil_review", "junk dimension · 32 combinações", [
        ("sk_perfil", "int", "PK"), ("recomendado", "bool"), ("compra_steam, gratis", "bool"),
        ("acesso_antecipado, deck", "bool")])
    review = tab("dim_review", "texto · corpus da busca", [("sk_review", "int", "PK"), ("recommendationid", "NK"),
                                                           ("texto_limpo", "text"), ("qtd_palavras", "int")], "baixo")
    return f'<div class="estrela">{tempo}{fato}{jogo}{autor}{perfil}{review}</div>'
