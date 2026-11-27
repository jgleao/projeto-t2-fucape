# Roteiro do vídeo (máx. 10 min)

## Antes de gravar

1. `docker compose up -d` e conferir `docker compose ps` (tudo *healthy*).
2. Abas abertas no navegador: o repositório no GitHub, o Airflow (http://localhost:8080, `airflow` / `airflow`) e o painel (http://localhost:8501).
3. Um terminal aberto na pasta do projeto.
4. O DW já está carregado (159.961 reviews). Não precisa coletar de novo: no vídeo, o *Trigger* da DAG 1 roda em modo incremental e termina em cerca de 1 minuto.

## Roteiro

| Tempo | Bloco | O que mostrar | O que falar |
|---|---|---|---|
| 0:00–0:40 | Abertura | README no GitHub: diagrama de arquitetura e prints do painel | Tema: o que jogadores brasileiros escrevem sobre 16 jogos da Steam. A dor: esse feedback está preso numa API paginada, sem histórico e sem busca. A esteira: Steam → Airflow → Star Schema → painel com busca otimizada |
| 0:40–3:00 | **1. Airflow** | Terminal: `docker compose ps`. Airflow → `dag_ingestao_raw` → **Trigger DAG** → aba *Graph* (uma tarefa por jogo, mapeamento dinâmico) → log de um `coletar_reviews_jogo` (páginas lidas, "watermark alcancado") → `dag_consolidacao_dw` aparece sozinha, disparada pelo **Dataset** → abrir a execução dela, tudo verde | Paginação por cursor e condições de parada. Backoff exponencial com equal jitter, respeitando `Retry-After`. Polidez: 1 requisição por segundo e 2 jogos em paralelo. Carga incremental: cada jogo guarda o estado da cobertura e para ao alcançar o watermark. Idempotência: upsert pela chave natural, só grava se o hash do payload mudou. Contar que a Valve descontinuou o endpoint antigo `/appreviews` e que o pipeline usa o `IUserReviewsService/GetAppReviews` |
| 3:00–4:40 | **2. Data Warehouse** | Terminal: `docker compose exec dw-postgres psql -U dw -d dw -c "\dt dw.*"` → painel, aba **Modelo Dimensional** (`?aba=modelo`): granularidade, diagrama, volume por camada, amostra da fato → terminal: `docker compose exec dashboard python -m scripts.verificar_idempotencia` | Granularidade: uma linha da fato é uma review. Surrogate keys inteiras (IDENTITY) em todas as dimensões, membro desconhecido −1, *junk dimension* de flags, dimensão de texto separada da fato. Métricas aditivas, semiaditiva e não aditiva. FKs reais e 6 checks de qualidade. No script: a impressão digital MD5 da fato é idêntica antes e depois de reprocessar tudo |
| 4:40–5:50 | Visão de Negócios | Painel, aba 1 (`?aba=negocios`): cartão de total, medidor, tendência, ranking por jogo; filtrar por um jogo | Três achados reais (abaixo) |
| 5:50–8:20 | **3. Busca e benchmark** | Aba 2 (`?aba=busca`): a consulta "jogo travando muito no servdor" já vem preenchida → mostrar a correção para "servidor", a comparação baseline vs. WAND + CL, a taxa de poda e "Top-K igual ao exaustivo: sim" → trocar o algoritmo para Block-Max WAND → digitar "melhor jogo que ja joguei" para mostrar um caso em que o ganho é pequeno → aba 3 (`?aba=engenharia`): **Rodar benchmark completo** e mostrar o gráfico por consulta, a tabela, a escalabilidade e a correção ortográfica | Baseline: pontua todos os documentos da base e ordena tudo. WAND: limite superior por termo, pivô, salto por busca binária. Champion Lists aquecem o heap, então o limiar já começa alto. A poda é segura: o Top-K é idêntico. A ablação TAAT + heap separa o ganho do heap do ganho da poda. Números finais (abaixo) |
| 8:20–9:30 | Engenharia | Aba 3: saúde das DAGs (API do Airflow), auditoria da ingestão (requisições, retentativas, HTTP 429), histórico de cargas da DAG 2 → GitHub → *Actions* com o CI verde | CI a cada push: lint, 126 testes, integração contra um Postgres real e import das DAGs na imagem oficial do Airflow |
| 9:30–10:00 | Fechamento | — | Próximos passos: reduzir o custo por pivô nas consultas só com termos frequentes, avaliação de qualidade com NDCG, SCD tipo 2 na `dim_jogo` para histórico de preço |

## Números para citar (base final)

* **Dados:** 159.961 reviews reais em português, 16 jogos, de julho de 2021 a novembro de 2026; 147.975 autores distintos.
* **Coleta:** 3 execuções da DAG 1, todas com sucesso (carga inicial, incremental e histórico aprofundado), 2.000+ requisições sem nenhum HTTP 429. Na incremental, os 16 jogos pararam no watermark: 1 review nova e 15 alteradas.
* **Idempotência:** MD5 da fato idêntico depois de reprocessar as 159.961 linhas.
* **Busca (105.957 reviews indexadas, 12 consultas, K = 10):**
  * BM25 exaustivo 9,05 ms → WAND + Champion Lists 3,87 ms: **2,3× mais rápido, 57% menos tempo, 93,2% de poda**, Top-K idêntico nas 12 consultas.
  * Melhor caso: "jogo travando muito", 94× (69.763 candidatos, 99,9% de poda). Pior caso: "graficos lindos mundo aberto", 1,4×.
  * Memória por consulta: de 6,3 MB para 15 KB.
  * Escala: perde com 5 mil e 10 mil documentos, ganha a partir de 20 mil e chega a 2,35× com 106 mil.
* **Correção ortográfica:** 471 ms → 4,9 ms (**96×**), mesma sugestão da força bruta em 12 de 12 palavras.

## Achados de negócio (reais)

* **Jogos competitivos online são os menos recomendados:** Dota 2 (82,6%) e Counter-Strike 2 (85,5%), contra 99,1% do Hades e 98,8% do Baldur's Gate 3.
* **Quem jogou menos de 2 horas recomenda bem menos** (80,1%). A recomendação sobe até a faixa de 50 a 200 horas (97,2%) e **cai de novo entre quem tem mais de 200 horas** (90,7%): o veterano é mais crítico.
* **Avaliadores veteranos** (50 ou mais reviews escritas) recomendam menos (92,5%) que os ocasionais (95,5%).
* Ressalva a mencionar: a coleta traz as 10 mil reviews mais recentes de cada jogo, então a comparação entre anos não representa o histórico completo.

## Perguntas prováveis na arguição (e respostas curtas)

* **Por que o WAND é seguro?** Os limites superiores são exatos (o máximo real do termo). Todo documento antes do pivô tem score menor ou igual à soma dos limites anteriores, que não alcança o limiar θ do heap. Logo, nada que poderia entrar no Top-K é pulado. Os testes comparam documentos e scores com o exaustivo em 480 consultas aleatórias e em 60 índices montados para gerar empates.
* **E as Champion Lists não tornam o resultado aproximado?** Não. Elas só escolhem quem é pontuado primeiro. Esses documentos recebem o score **exato** e definem um θ real; depois o WAND varre as listas completas normalmente.
* **Por que o ganho médio é só 2,3×?** Em Python puro, cada passo do WAND (ordenar cursores, achar o pivô, busca binária) custa bem mais que somar uma postagem, e as reviews são curtas (20 termos em média). Com um termo raro na consulta o ganho passa de 90×; só com termos frequentes ele fica perto de 1,4×, mesmo podando mais de 85% dos documentos.
* **Por que o Block-Max WAND poda mais e não é o mais rápido?** O ponteiro de bloco acrescenta trabalho por pivô. Ele vence quando os limites globais enganam e os locais não, como em "historia emocionante personagens" (1,5 ms contra 3,9 ms). Em código compilado a poda extra tende a compensar.
* **Por que o WAND perde com 5 mil ou 10 mil documentos?** O exaustivo é barato quando N é pequeno, e o custo fixo do WAND domina. O custo do exaustivo cresce com N; o do WAND depende mais de K e dos termos raros.
* **O que mudou na API da Steam?** A Valve descontinuou `store.steampowered.com/appreviews` (hoje redireciona para a loja). O substituto, `IUserReviewsService/GetAppReviews`, recebe os filtros como enums num JSON e não devolve mais `num_games_owned`; por isso a `dim_autor` não tem tamanho de biblioteca.
* **Por que surrogate key se a Steam já tem ID?** Desacoplamento: IDs da fonte podem mudar, colidir entre fontes ou ser texto (join caro). A SK inteira é estável, controlada pelo DW e permite o membro "desconhecido" (−1).
* **`minutos_jogados_total` é semiaditiva por quê?** É uma foto do estado na data da coleta. Somar entre jogadores faz sentido; somar a mesma pessoa em coletas diferentes conta o mesmo tempo duas vezes.
* **Como sabe que a carga é idempotente?** Chaves naturais com PK/UNIQUE e upsert, staging truncada a cada execução e watermark que só avança depois dos checks. As provas: o script `scripts/verificar_idempotencia.py` (MD5 de toda a fato antes e depois) e o teste de integração no CI.
* **Por que equal jitter e não full jitter?** O full jitter pode sortear espera perto de zero e martelar a API; o equal jitter garante pelo menos metade do teto e ainda espalha as tentativas.
* **A coleta incremental pode perder reviews?** Não. O watermark só avança quando a janela inteira foi coberta. Se o limite de páginas chegar antes do watermark, ele fica onde estava e a próxima execução recobre a janela.
