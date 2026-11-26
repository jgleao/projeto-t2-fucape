# Roteiro do vídeo (máx. 10 min)

**Antes de gravar:** `docker compose up -d`, DAGs já rodadas pelo menos uma vez, painel aberto em http://localhost:8501 e o benchmark com dados reais gerado (`docker compose exec dashboard python -m scripts.benchmark`).

| Tempo | Bloco | O que mostrar | O que falar |
|---|---|---|---|
| 0:00–0:45 | Abertura | README no GitHub (diagrama de arquitetura) | Tema, a dor (feedback preso numa API sem busca) e a esteira: Steam → Airflow → Star Schema → painel com busca otimizada |
| 0:45–3:00 | **1. Airflow** | `docker compose ps` (serviços *healthy*) → Airflow UI → `dag_ingestao_raw` → Trigger → Graph (tarefas mapeadas por jogo) → log de uma tarefa (páginas, "aguardando Xs" se houve backoff) → `dag_consolidacao_dw` disparado pelo **Dataset** | Cursor + condições de parada; backoff com equal jitter + Retry-After; polidez (1 req/s, 2 jogos em paralelo); idempotência por PK + hash. Mostrar **Clear** numa tarefa e que ela grava 0 linhas novas |
| 3:00–4:45 | **2. Data Warehouse** | DBeaver/psql em `localhost:5433` → `\dt dw.*` → aba **Modelo Dimensional** do painel (granularidade, contagens, amostra da fato só com SKs) → rodar `python -m scripts.verificar_idempotencia` | Granularidade (1 linha = 1 review); SKs IDENTITY; membro -1; junk dimension; métricas aditiva/semiaditiva/não aditiva; FKs reais + 6 checks; impressão digital MD5 idêntica depois do full refresh |
| 4:45–6:00 | Visão de Negócios | Aba 1: KPIs, filtro por jogo e período, gráficos | 2–3 insights reais (ex.: jogo com menor taxa de recomendação; se quem joga mais recomenda mais) |
| 6:00–8:30 | **3. Busca + benchmark** | Aba 2: digitar "jogo trvando no servdor" → "Você quis dizer" + autocompletar → métricas Baseline vs. WAND+CL (ms, Δ%, speedup, poda, ✅ Top-K idêntico) → trocar para Block-Max WAND → Aba 3: **Rodar benchmark completo** (gráfico por consulta, tabela, escalabilidade, ortografia) | Baseline = pontua os N docs + ordena tudo. WAND: pivô, UB, salto por busca binária. Champion Lists aquecem o heap, então θ começa alto. Poda segura (prova). Ablação TAAT+heap separa o ganho do heap do ganho da poda. Cruzamento em ~10k docs |
| 8:30–9:30 | Engenharia | Aba 3: saúde dos DAGs (API do Airflow), `ingestion_log` (requisições, retentativas, 429), histórico do ETL estável; GitHub Actions verde | CI: lint, 124 testes, integração com Postgres real, import das DAGs na imagem oficial |
| 9:30–10:00 | Fechamento | — | O que faria a seguir: BMW em linguagem compilada, avaliação NDCG com consultas anotadas, SCD2 em `dim_jogo` para histórico de preço |

## Perguntas prováveis na arguição (e respostas curtas)

* **Por que o WAND é seguro?** Os UB são exatos (máximo real do termo). Todo documento antes do pivô tem score ≤ Σ UB anteriores ≤ θ, e para entrar no heap precisa de score > θ. Logo, nada que poderia entrar é pulado. O teste `test_topk_identico_ao_exaustivo` confere isso em 480 consultas × 4 algoritmos.
* **E as Champion Lists não tornam o resultado aproximado?** Não. Elas só escolhem quem é pontuado primeiro. Esses documentos são pontuados com o score **exato** e definem um θ real. Depois o WAND varre as listas completas normalmente.
* **Por que o BMW poda mais e não é o mais rápido?** Em Python cada iteração custa microssegundos; o ponteiro de bloco adiciona trabalho por pivô. Em código compilado o custo por iteração cai e a poda extra compensa.
* **Por que o WAND perde com 5 mil documentos?** O exaustivo é barato quando N é pequeno; o overhead de ordenar cursores e fazer buscas binárias domina. O custo do exaustivo cresce com N; o do WAND, quase só com K e com os termos raros.
* **Por que surrogate key se a Steam já tem ID?** Desacoplamento: IDs da fonte podem mudar, colidir entre fontes ou ser texto (join caro). A SK inteira é estável e controlada pelo DW, e permite o membro "desconhecido" (-1).
* **`minutos_jogados_total` é semiaditiva por quê?** É uma foto do estado na data da coleta. Somar entre jogadores faz sentido; somar a mesma pessoa em coletas diferentes conta o mesmo tempo duas vezes.
* **Como sabe que a carga é idempotente?** PK/UNIQUE nas chaves naturais + upsert, staging truncada, watermark que só avança após os checks; prova pelo `scripts/verificar_idempotencia.py` (MD5 de toda a fato antes e depois) e pelo teste de integração no CI.
* **Por que equal jitter e não full jitter?** O full jitter pode sortear espera ≈ 0 e martelar a API; o equal jitter garante pelo menos metade do teto e continua espalhando os clientes.
