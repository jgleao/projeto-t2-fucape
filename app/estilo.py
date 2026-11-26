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


html {font-size: 18px;}
:root {
  --tinta: #1e2a36; --suave: #6b7c8a; --fraco: #98a7b2; --marinho: #1f3247; --coral: #d9775c;
  --vidro: rgba(255,255,255,.46); --vidro-forte: rgba(255,255,255,.66); --borda: rgba(255,255,255,.75);
  --sombra: 0 10px 40px rgba(31,50,71,.07), 0 1px 2px rgba(31,50,71,.04);
}
html, body, [class*="st-"], .stMarkdown, button, input, textarea, select {
  font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif !important;
}
.num {font-variant-numeric: tabular-nums;}
/* devolve a fonte de icones do Streamlit (senao aparece o nome do icone em texto) */
[data-testid="stIconMaterial"], span.material-symbols-rounded {font-family: 'Material Symbols Rounded' !important;}

.stApp {
  background:
    radial-gradient(900px 600px at 12% 0%, rgba(255,255,255,.85), transparent 60%),
    radial-gradient(800px 600px at 100% 100%, rgba(183,207,214,.55), transparent 60%),
    linear-gradient(160deg, #eef3f3 0%, #e0eaea 45%, #c8d9dc 100%) !important;
  background-attachment: fixed !important;
}
.block-container {padding-top: 1.6rem !important; max-width: 1560px;}
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
  border-radius: 999px !important; padding: 9px 22px !important; height: auto !important; border: 0 !important;
  background: transparent; cursor: pointer; transition: background .15s ease;
}
.stTabs [data-testid="stTab"]:hover {background: rgba(255,255,255,.6);}
.stTabs [data-testid="stTab"] p {font-size: .98rem; font-weight: 500; color: var(--suave); margin: 0;}
.stTabs [data-testid="stTab"][aria-selected="true"] {background: var(--marinho) !important; box-shadow: 0 6px 18px rgba(31,50,71,.22);}
.stTabs [data-testid="stTab"][aria-selected="true"] p {color: #fff !important;}
.stTabs .react-aria-SelectionIndicator {display: none !important;}
.stTabs [role="tabpanel"] {padding-top: 1.3rem;}

/* entradas como vidro */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
  background: var(--vidro-forte) !important; border-radius: 14px !important; border-color: var(--borda) !important;
}
label p {color: var(--suave) !important; font-size: .9rem !important;}

/* containers com key "card..." viram paineis de vidro */
div[data-testid="stVerticalBlock"] {gap: .85rem;}
div[class*="st-key-card"] {
  background: var(--vidro); border: 1px solid var(--borda); border-radius: 22px; padding: 18px 20px 4px;
  backdrop-filter: blur(18px); box-shadow: var(--sombra);
}
div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden; border: 1px solid var(--borda); box-shadow: var(--sombra);}
div[data-testid="stExpander"] details {border-radius: 16px; border: 1px solid var(--borda); background: var(--vidro);}

/* ---------- componentes ---------- */
.painel {background: var(--vidro); border: 1px solid var(--borda); border-radius: 22px;
  backdrop-filter: blur(18px); box-shadow: var(--sombra);}

.topo {display: flex; justify-content: space-between; align-items: center; gap: 28px; padding: 18px 24px; margin-bottom: 6px;}
.topo .marca {display: flex; align-items: center; gap: 14px;}
.topo .logo {width: 40px; height: 40px; border-radius: 12px; background: var(--marinho); display: grid; place-items: center;
  box-shadow: 0 6px 18px rgba(31,50,71,.25);}
.topo .logo i {width: 14px; height: 14px; border-radius: 50%; border: 3px solid #fff; display: block;}
.topo h1 {font-size: 1.6rem; font-weight: 500; margin: 0; color: var(--tinta); letter-spacing: -.01em;}
.topo .sobre {font-size: .86rem; color: var(--suave); margin-top: 2px;}
.topo .meta {display: flex; gap: 10px;}
.pilula {white-space: nowrap; display: inline-flex; align-items: center; gap: 8px; padding: 9px 18px; border-radius: 999px; font-size: .9rem;
  background: var(--vidro-forte); border: 1px solid var(--borda); color: var(--tinta);}
.pilula b {font-weight: 600;}
.pilula.escura {background: var(--marinho); color: #fff; border-color: var(--marinho);}
.pilula .ponto {width: 7px; height: 7px; border-radius: 50%; background: #3f9b74;}
.pilula .ponto.off {background: var(--coral);}

.secao {margin: 6px 0 6px;}
.secao h3 {font-size: 1.15rem; font-weight: 500; margin: 0; color: var(--tinta);}
.secao span {display: block; color: var(--suave); font-size: .88rem; margin-top: 1px;}

.kpis {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 4px 26px; padding: 20px 26px; margin-bottom: 4px;}
.kpi .l {font-size: .86rem; color: var(--suave);}
.kpi .v {font-size: 2.3rem; font-weight: 300; color: var(--tinta); letter-spacing: -.02em; line-height: 1.15;
  font-variant-numeric: tabular-nums; margin-top: 4px;}
.kpi .s {font-size: .82rem; color: var(--fraco); margin-top: 2px;}
.kpi.destaque .v {color: var(--marinho); font-weight: 400;}
.kpi:first-child .v {font-size: 2.6rem;}

.comparacao {padding: 20px 26px; margin-bottom: 4px; display: grid; grid-template-columns: 1fr 240px; gap: 26px; align-items: center;}
.linha-c {display: grid; grid-template-columns: 260px 1fr 110px; align-items: center; gap: 16px; padding: 9px 0;}
.linha-c .n {font-size: .98rem; color: var(--tinta); font-weight: 500;}
.linha-c .n small {display: block; color: var(--suave); font-size: .82rem; font-weight: 400;}
.linha-c .trilho {height: 14px; border-radius: 999px; background: rgba(31,50,71,.07); overflow: hidden;}
.linha-c .trilho div {height: 100%; min-width: 4px; border-radius: 999px;}
.linha-c .base div {background: repeating-linear-gradient(135deg, #93a7b5 0 4px, #b6c5cf 4px 8px);}
.linha-c .opt div {background: var(--marinho);}
.linha-c .ms {font-size: 1.2rem; font-weight: 300; text-align: right; color: var(--tinta); font-variant-numeric: tabular-nums;}
.selo-delta {border-radius: 18px; padding: 16px 18px; background: var(--vidro-forte); border: 1px solid var(--borda);}
.selo-delta .x {font-size: 2.9rem; font-weight: 300; color: var(--tinta); letter-spacing: -.02em; line-height: 1;}
.selo-delta .t {font-size: .9rem; color: var(--suave); margin-top: 6px;}

.nota {font-size: .98rem; color: var(--tinta); padding: 11px 18px; margin: 0 0 12px; border-radius: 14px;
  background: var(--vidro-forte); border: 1px solid var(--borda);}
.nota s {color: var(--fraco);} .nota .suave {color: var(--suave);}
.auto {font-size: .88rem; color: var(--suave); margin: -4px 0 14px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;}
.auto .sug {padding: 3px 11px; border-radius: 999px; background: var(--vidro-forte); border: 1px solid var(--borda); color: var(--tinta);}
.auto .dir {margin-left: auto; color: var(--fraco);}

.lista {display: grid; gap: 10px;}
.item {display: grid; grid-template-columns: 46px 1fr; gap: 0 10px; padding: 16px 20px;}
.item.sem-pos {grid-template-columns: 1fr;}
.item .pos {width: 36px; height: 36px; border-radius: 50%; background: var(--marinho); color: #fff; font-size: .78rem;
  display: grid; place-items: center; font-variant-numeric: tabular-nums;}
.item .cab {display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;}
.item .jogo {font-weight: 600; color: var(--tinta);}
.item .rec {font-size: .84rem; color: var(--suave); padding: 2px 10px; border-radius: 999px; background: rgba(31,50,71,.06);}
.item .rec.nao {color: #a4513a; background: rgba(217,119,92,.12);}
.item .score {margin-left: auto; font-size: .86rem; color: var(--fraco); font-variant-numeric: tabular-nums;}
.item .texto {color: #2f3d4a; line-height: 1.65; font-size: 1.02rem; margin-top: 6px;}
.item .meta {color: var(--suave); font-size: .84rem; margin-top: 8px;}
.item .meta span + span::before {content: "·"; margin: 0 8px;}
mark {background: rgba(31,50,71,.12); color: var(--marinho); font-weight: 600; padding: 0 3px; border-radius: 4px;}

.vazio {padding: 26px 28px;}
.vazio h3 {margin: 0 0 4px; font-size: 1.05rem; font-weight: 500;}
.vazio p {color: var(--suave); margin: 0 0 14px; font-size: .9rem;}
.vazio ol {margin: 0; padding-left: 20px; color: var(--tinta); font-size: .9rem; line-height: 2;}

.dags {display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 4px;}
.dag {padding: 18px 22px;}
.dag .nome {font-size: 1rem; font-weight: 600; color: var(--tinta);}
.dag .estado {font-size: .84rem; margin-left: 10px; padding: 3px 10px; border-radius: 999px; background: rgba(31,50,71,.07); color: var(--suave);}
.dag .estado.success {background: rgba(63,155,116,.14); color: #2f7a5a;}
.dag .estado.failed {background: rgba(217,119,92,.16); color: #a4513a;}
.dag .estado.running, .dag .estado.queued {background: rgba(31,50,71,.12); color: var(--marinho);}
.dag .sub {font-size: .88rem; color: var(--suave); margin-top: 6px;}
.pontos {display: flex; gap: 4px; margin-top: 12px;}
.pontos i {width: 18px; height: 6px; border-radius: 4px; background: rgba(31,50,71,.12);}
.pontos i.success {background: #3f9b74;} .pontos i.failed {background: var(--coral);}
.pontos i.running, .pontos i.queued {background: var(--marinho);}

.estrela {display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; align-items: start;}
.estrela .col {display: grid; gap: 14px;}
.tabela {padding: 16px 18px; font-size: .88rem;}
.tabela h4 {margin: 0; font-size: 1rem; font-weight: 600; color: var(--tinta);}
.tabela .papel {color: var(--suave); font-size: .82rem; margin: 2px 0 8px;}
.tabela div.c {display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; border-top: 1px solid rgba(31,50,71,.06); color: #3b4a57;}
.tabela .pk {color: var(--tinta); font-weight: 600;} .tabela .fk {color: #3d7d8a; font-weight: 500;}
.tabela .t, .tabela .selo {color: var(--fraco); font-size: .8rem;}
.tabela.fato {background: rgba(31,50,71,.92); border-color: rgba(31,50,71,.92);}
.tabela.fato h4, .tabela.fato .pk, .tabela.fato div.c {color: #fff;}
.tabela.fato .papel, .tabela.fato .t, .tabela.fato .selo {color: #a9bccb;}
.tabela.fato .fk {color: #9fd3dd;} .tabela.fato div.c {border-top-color: rgba(255,255,255,.08);}
.grao {padding: 16px 24px; margin-bottom: 4px; font-size: 1.05rem; color: var(--tinta);}
.grao b {font-weight: 600;}

@media (max-width: 900px) {
  .topo {flex-direction: column; align-items: flex-start;}
  .dags, .estrela, .comparacao {grid-template-columns: 1fr;}
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
                                                           ("texto_limpo", "text"), ("qtd_palavras", "int")])
    return (f'<div class="estrela"><div class="col">{tempo}{autor}{review}</div>'
            f'<div class="col">{fato}</div><div class="col">{jogo}{perfil}</div></div>')


# ------------------------------------------------------------------ tabelas
CSS_TABELA = """
<style>
.tab-html {padding: 6px 8px; overflow-x: auto; margin-bottom: 4px;}
.tab-html table {width: 100%; border-collapse: collapse; font-size: .92rem; color: var(--tinta);}
.tab-html th {text-align: left; font-weight: 500; font-size: .8rem; color: var(--suave); padding: 12px 14px 10px;
  border-bottom: 1px solid rgba(31,50,71,.10); white-space: nowrap;}
.tab-html td {padding: 11px 14px; border-bottom: 1px solid rgba(31,50,71,.05); vertical-align: middle;}
.tab-html tr:last-child td {border-bottom: 0;}
.tab-html tbody tr:hover td {background: rgba(255,255,255,.45);}
.tab-html .dir {text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap;}
.tab-html .fraco {color: var(--fraco);}
.tab-html .forte {font-weight: 600;}
.tab-html .barra {display: flex; align-items: center; gap: 10px; min-width: 160px;}
.tab-html .barra i {flex: 1; height: 8px; border-radius: 999px; background: rgba(31,50,71,.08); position: relative; overflow: hidden;}
.tab-html .barra i b {position: absolute; inset: 0 auto 0 0; background: var(--marinho); border-radius: 999px;}
.tab-html .barra span {width: 54px; text-align: right; font-variant-numeric: tabular-nums;}
.tab-html .tag {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .8rem; background: rgba(31,50,71,.07); color: var(--suave);}
.tab-html .tag.ok {background: rgba(63,155,116,.14); color: #2f7a5a;}
.tab-html .tag.ruim {background: rgba(217,119,92,.16); color: #a4513a;}
.tab-html .camada {font-size: .78rem; color: var(--fraco); text-transform: lowercase;}
</style>
"""


def _br(v: float, casas: int) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _celula(valor, tipo: str) -> tuple[str, str]:
    """Formata um valor -> (html, classe css da celula)."""
    import json
    import math
    from datetime import date, datetime
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return '<span class="fraco">—</span>', "dir" if tipo not in ("txt", "forte") else ""
    if tipo == "int":
        return _br(float(valor), 0), "dir"
    if tipo == "ms":
        return f"{_br(float(valor), 2)} ms", "dir"
    if tipo == "num":
        return _br(float(valor), 2), "dir"
    if tipo == "x":
        return f"{_br(float(valor), 1)}×", "dir"
    if tipo == "pct100":
        return f"{_br(float(valor), 1)}%", "dir"
    if tipo == "barra":
        v = max(0.0, min(1.0, float(valor)))
        return f'<div class="barra"><i><b style="width:{v * 100:.1f}%"></b></i><span>{_br(v * 100, 1)}%</span></div>', ""
    if tipo == "data":
        if isinstance(valor, (datetime, date)):
            return valor.strftime("%d/%m/%Y %H:%M" if isinstance(valor, datetime) else "%d/%m/%Y"), "dir"
        return e(str(valor)[:16].replace("T", " ")), "dir"
    if tipo == "estado":
        classe = "ok" if str(valor) in ("sucesso", "success") else ("ruim" if str(valor) in ("erro", "failed", "falha_qualidade") else "")
        return f'<span class="tag {classe}">{e(valor)}</span>', ""
    if tipo == "bool":
        return ('<span class="tag ok">sim</span>' if valor in (True, "sim") else '<span class="tag ruim">não</span>'), ""
    if tipo == "checks":
        dados = json.loads(valor) if isinstance(valor, str) else (valor or {})
        falhas = [k for k, v in dados.items() if not k.startswith("aviso_") and v]
        avisos = [f"{k.removeprefix('aviso_').replace('_', ' ')}: {v}" for k, v in dados.items() if k.startswith("aviso_") and v]
        n = sum(1 for k in dados if not k.startswith("aviso_"))
        html = (f'<span class="tag ok">{n}/{n} ok</span>' if not falhas
                else f'<span class="tag ruim">{len(falhas)} falha(s)</span>')
        if avisos:
            html += f' <span class="fraco">· {e(", ".join(avisos))}</span>'
        return html, ""
    if tipo == "forte":
        return f'<span class="forte">{e(valor)}</span>', ""
    if tipo == "camada":
        return f'<span class="camada">{e(valor)}</span>', ""
    return e(valor), ""


def tabela(linhas, colunas: list[tuple[str, str, str]]) -> str:
    """Tabela HTML no estilo do painel. linhas = DataFrame ou lista de dicts;
    colunas = [(campo, rotulo, tipo)], tipo em: txt, forte, int, ms, num, x, pct100, barra, data, estado, bool, checks, camada."""
    registros = linhas.to_dict("records") if hasattr(linhas, "to_dict") else list(linhas)
    numericos = {"int", "ms", "num", "x", "pct100", "data"}
    cab = "".join(f'<th class="{"dir" if t in numericos else ""}">{e(r)}</th>' for _, r, t in colunas)
    corpo = []
    for reg in registros:
        celulas = []
        for campo, _, tipo in colunas:
            html, classe = _celula(reg.get(campo), tipo)
            celulas.append(f'<td class="{classe}">{html}</td>')
        corpo.append(f"<tr>{''.join(celulas)}</tr>")
    return f'<div class="painel tab-html"><table><thead><tr>{cab}</tr></thead><tbody>{"".join(corpo)}</tbody></table></div>'


# ------------------------------------------------------- destaques visuais
CSS_DESTAQUES = """
<style>
.bento {height: 262px; padding: 22px 26px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between;}
.escuro {background: linear-gradient(160deg, #24384f 0%, #1a2a3c 100%) !important; border-color: rgba(31,50,71,.9) !important;
  color: #fff; box-shadow: 0 18px 40px -14px rgba(31,50,71,.55) !important;}
.escuro .l {color: #a9bccb; font-size: .86rem;}
.escuro .v {font-size: 3.1rem; font-weight: 300; letter-spacing: -.02em; line-height: 1.05; margin-top: 6px; font-variant-numeric: tabular-nums;}
.escuro .s {color: #a9bccb; font-size: .84rem; margin-top: 4px;}

.cab-bento {display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;}
.bolinha {width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: rgba(255,255,255,.12); color: #fff; font-size: .9rem;}
.bolinha.clara {background: var(--vidro-forte); border: 1px solid var(--borda); color: var(--marinho);}
.medidor {text-align: center;}
.medidor .l {font-size: .86rem; color: var(--suave); text-align: left;}
.medidor .v {font-size: 2.6rem; font-weight: 300; color: var(--tinta); margin-top: -58px; letter-spacing: -.02em;}
.medidor .s {font-size: .84rem; color: var(--suave); margin-top: 2px;}
.mini {display: grid; grid-template-columns: 1fr 1fr; gap: 18px 22px;}
.mini .l {font-size: .82rem; color: var(--suave);}
.mini .v {font-size: 1.9rem; font-weight: 300; color: var(--tinta); letter-spacing: -.02em; font-variant-numeric: tabular-nums;}
.chip-delta {display: inline-flex; flex-direction: column; padding: 10px 16px; border-radius: 14px; min-width: 130px;
  background: var(--vidro-forte); border: 1px solid var(--borda); box-shadow: 0 8px 24px rgba(31,50,71,.08);}
.chip-delta b {font-size: 1.5rem; font-weight: 300; color: var(--tinta); letter-spacing: -.01em;}
.chip-delta span {font-size: .78rem; color: var(--suave);}
.titulo-card {display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 2px;}
.selo-delta {background: linear-gradient(160deg, #24384f 0%, #1a2a3c 100%) !important; border-color: transparent !important;
  box-shadow: 0 18px 40px -14px rgba(31,50,71,.55);}
.selo-delta .x {color: #fff !important;} .selo-delta .t {color: #a9bccb !important;}
</style>
"""


def _svg_img(svg: str, estilo: str = "") -> str:
    """st.html sanitiza <svg> embutido; como imagem (data URI) o desenho passa intacto."""
    import base64
    if "xmlns=" not in svg:
        svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    dados = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img alt="" src="data:image/svg+xml;base64,{dados}" style="{estilo}">'


def _sparkline(valores: list[float], largura: int = 320, altura: int = 64) -> str:
    if len(valores) < 2:
        return ""
    vmin, vmax = min(valores), max(valores)
    faixa = (vmax - vmin) or 1
    pts = [(i * largura / (len(valores) - 1), altura - 6 - (v - vmin) / faixa * (altura - 14)) for i, v in enumerate(valores)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M0,{altura} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{largura},{altura} Z"
    ux, uy = pts[-1]
    return _svg_img(f'<svg viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" preserveAspectRatio="none">'
            '<defs><linearGradient id="gsp" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{area}" fill="url(#gsp)"/><polyline points="{linha}" fill="none" stroke="#fff" stroke-width="2" '
            f'stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="4" fill="#fff"/></svg>',
                    f"display:block;width:100%;height:{altura}px;margin-top:12px")


def cartao_escuro(rotulo: str, valor: str, sub: str, serie: list[float], icone: str = "↗") -> str:
    return (f'<div class="painel bento escuro"><div class="cab-bento"><div><div class="l">{e(rotulo)}</div>'
            f'<div class="v">{e(valor)}</div><div class="s">{e(sub)}</div></div><div class="bolinha">{e(icone)}</div></div>'
            f'{_sparkline(serie)}</div>')


def medidor(fracao: float, rotulo: str, valor: str, sub: str) -> str:
    """Medidor semicircular (0..1)."""
    import math
    f = max(0.0, min(1.0, fracao))
    r, cx, cy = 92, 110, 108
    comprimento = math.pi * r
    arco = f"M{cx - r},{cy} A{r},{r} 0 0 1 {cx + r},{cy}"
    marcas = "".join(
        f'<line x1="{cx + (r + 10) * math.cos(math.pi * (1 - t / 10)):.1f}" y1="{cy - (r + 10) * math.sin(math.pi * (1 - t / 10)):.1f}" '
        f'x2="{cx + (r + 15) * math.cos(math.pi * (1 - t / 10)):.1f}" y2="{cy - (r + 15) * math.sin(math.pi * (1 - t / 10)):.1f}" '
        f'stroke="#98a7b2" stroke-width="1.5" stroke-linecap="round"/>' for t in range(11))
    svg = (f'<svg viewBox="0 0 220 124" width="220" height="124">{marcas}'
           f'<path d="{arco}" fill="none" stroke="rgba(31,50,71,.09)" stroke-width="14" stroke-linecap="round"/>'
           f'<path d="{arco}" fill="none" stroke="#1f3247" stroke-width="14" stroke-linecap="round" '
           f'stroke-dasharray="{comprimento * f:.1f} {comprimento:.1f}"/></svg>')
    svg = _svg_img(svg, "display:block;width:230px;height:130px;margin:4px auto 0")
    return (f'<div class="painel bento medidor"><div class="cab-bento"><div class="l">{e(rotulo)}</div>'
            f'<div class="bolinha clara">◔</div></div>{svg}<div class="v">{e(valor)}</div><div class="s">{e(sub)}</div></div>')


def mini_numeros(itens: list[tuple[str, str]]) -> str:
    celulas = "".join(f'<div><div class="l">{e(r)}</div><div class="v">{e(v)}</div></div>' for r, v in itens)
    return f'<div class="painel bento"><div class="mini">{celulas}</div></div>'


def chip_delta(valor: str, legenda: str) -> str:
    return f'<div class="chip-delta"><b>{e(valor)}</b><span>{e(legenda)}</span></div>'


def titulo_card(titulo: str, subtitulo: str, direita: str = "") -> str:
    return f'<div class="titulo-card">{secao(titulo, subtitulo)}{direita}</div>'
