# 🎮 Steam Reviews Intelligence

**Pipeline analítico de ponta a ponta sobre o que os jogadores brasileiros escrevem na Steam:** ingestão resiliente com Apache Airflow, Data Warehouse dimensional (Kimball) e um motor de busca BM25 com poda **WAND + Champion Lists**, **Block-Max WAND** e **correção ortográfica em 2 estágios**, cada um com benchmark *Antes vs. Depois* cronometrado em milissegundos sobre as reviews reais.

![CI](../../actions/workflows/ci.yml/badge.svg)

| | |
|---|---|
| **Aluno** | João Gilberto Leão Vieira (trabalho individual) |
| **Disciplinas** | Modelagem Informacional · Processamento de Linguagem Natural e Sistemas de Recuperação de Informação |
| **Curso** | Ciência de Dados para Negócios, FUCAPE Business School, 2026/2º bimestre |
| **Docente** | Prof. Dr. Wagner Perin |
| **Tema** | Entretenimento & Games: avaliações (reviews) em português de 16 jogos populares da Steam |

> **Destaques**
> * **39.961 reviews reais** em PT-BR na primeira carga (16 jogos × até 2.500 reviews cada), coletadas via API pública com paginação por cursor, *rate limit* e *exponential backoff* com jitter.
> * Modelo estrela com **5 dimensões** (incluindo uma *junk dimension* e membros desconhecidos `-1`), surrogate keys inteiras, FKs reais e **6 checks de qualidade** que barram a carga.
> * **3 técnicas de RI** implementadas do zero em Python puro, todas com **prova automática de segurança**: o Top-K otimizado (documentos **e** scores, com desempate idêntico) é comparado com o exaustivo em 480 consultas aleatórias e em 60 índices montados para gerar empates.
> * Idempotência **comprovada por código**: teste de integração contra Postgres real no CI e script de impressão digital (MD5) do DW antes e depois do reprocessamento.
> * **126 testes automatizados**, lint PEP 8 (ruff) e GitHub Actions que valida o `docker-compose.yml` e importa as DAGs na imagem oficial do Airflow.

---

## Sumário
1. [Contexto de negócio e declaração da dor](#1-contexto-de-negócio-e-declaração-da-dor)
2. [Arquitetura de engenharia de dados](#2-arquitetura-de-engenharia-de-dados)
3. [Modelagem dimensional](#3-modelagem-dimensional)
4. [Inteligência de recuperação de informação](#4-inteligência-de-recuperação-de-informação)
5. [Resultados experimentais e benchmark](#5-resultados-experimentais-e-benchmark)
6. [Guia passo a passo de execução](#6-guia-passo-a-passo-de-execução-how-to-run)
7. [Estrutura do repositório e qualidade de software](#7-estrutura-do-repositório-e-qualidade-de-software)

---

## 1. Contexto de negócio e declaração da dor

O Brasil é um dos maiores mercados de games do mundo, e a **review da Steam é o principal termômetro público de um jogo**: o percentual de avaliações positivas aparece na página de compra e influencia diretamente a conversão. Para um estúdio, uma publicadora ou um time de *community management*, essas reviews são o maior acervo gratuito de feedback qualitativo do mercado.

**A dor:** esse feedback existe em volume (milhares de textos por jogo), mas está **preso numa API paginada, sem histórico e sem busca**. Hoje um analista não consegue responder com rapidez:

* "A taxa de recomendação do nosso jogo está caindo mês a mês? E a dos concorrentes?"
* "Jogadores com mais horas de jogo são mais críticos ou mais fãs?"
* "Onde estão as reclamações de **travamento**, **servidor** ou **otimização**?", sem ler milhares de reviews e mesmo quando o jogador escreve "trvando" ou "servdor".

**Objetivos estratégicos do produto:**

| Objetivo | Como o projeto entrega |
|---|---|
| Histórico confiável e incremental | DAG 1 coleta diariamente e preserva o payload bruto (bronze); o DW guarda tudo com idempotência |
| Métricas de satisfação comparáveis | Star Schema com taxa de recomendação, horas jogadas e votos úteis por jogo, tempo, perfil de jogador e origem da cópia |
| Descoberta de problemas em texto livre | Busca BM25 com Top-K em cerca de 1 ms, tolerante a erros de digitação |
| Operação de nível produção | Airflow conteinerizado, retentativas, checks de qualidade, auditoria de ingestão e CI |

---

## 2. Arquitetura de engenharia de dados

```mermaid
flowchart TD
    subgraph S1["Fonte externa"]
        API["APIs públicas da Steam (sem chave)<br>IUserReviewsService/GetAppReviews (cursor) · /api/appdetails"]
    end
    subgraph S2["Ambiente conteinerizado · docker compose"]
        subgraph AF["Apache Airflow 2.10 · webserver · scheduler · triggerer · Postgres de metadados"]
            D1["DAG 1 · dag_ingestao_raw<br>cursor · rate limit · backoff + jitter · Retry-After"]
            D2["DAG 2 · dag_consolidacao_dw<br>limpeza · tipagem · SKs · star schema · 6 checks"]
        end
        subgraph ST["Postgres 16 · volume persistente dw-pgdata"]
            RAW["raw.* (bronze)<br>JSONB original + sha256"]
            DW[("dw.* Star Schema<br>5 dimensões SK + fato")]
        end
    end
    subgraph S3["Aplicação de consumo · Streamlit"]
        UI["Visão de Negócios<br>KPIs e gráficos SQL"]
        subgraph NLP["Motor de busca (PLN & RI)"]
            BM["Baseline<br>BM25 exaustivo · Levenshtein força-bruta"]
            OPT["Otimizado<br>WAND + Champion Lists · Block-Max WAND<br>Trie + k-gramas + Levenshtein"]
            BEN["Benchmark<br>ms · Δ% · speedup · poda % · memória"]
        end
    end
    API -->|"extração com cursor + backoff"| D1
    D1 -->|"UPSERT idempotente"| RAW
    D1 -.->|"Dataset: raw/steam_reviews"| D2
    RAW -->|"leitura incremental (watermark)"| D2
    D2 -->|"UPSERT por chave natural"| DW
    DW -->|"SQL analítico"| UI
    DW -->|"dim_review: texto limpo"| NLP
    BM --> BEN
    OPT --> BEN
    BEN -->|"Antes vs. Depois"| UI
```

### 2.1 Resiliência da ingestão (DAG 1)

| Mecanismo | Implementação |
|---|---|
| **Paginação por cursor** | `IUserReviewsService/GetAppReviews` (o endpoint que substituiu o `/appreviews`, descontinuado pela Valve): `cursor=*` → `cursor` devolvido pela API, com o filtro *Recent* (mais novas primeiro). Para em página vazia, **cursor repetido**, watermark alcançado ou limite de páginas. Uma página incompleta no meio **não** encerra a coleta, porque a Steam filtra depois de paginar. |
| **HTTP 429 (rate limit)** | Retentativa com **exponential backoff + equal jitter**: `teto = min(60s, 1s·2ⁿ)`, `espera = teto/2 + U(0, teto/2)`. Se vier `Retry-After`, a espera nunca é menor que ele. |
| **Instabilidade** | 500/502/503/504, timeout, queda de conexão e "200 com HTML" são retentados (até 6×). |
| **Erros permanentes** | 400/403/404 falham na hora (não adianta insistir). |
| **Polidez** | ≥ 1 s entre requisições, no máximo 2 jogos em paralelo, User-Agent identificado. |
| **Retry do Airflow** | `retries=3`, `retry_exponential_backoff=True` (1 → 15 min). |
| **Falha parcial** | Mapeamento dinâmico (1 tarefa por jogo). A tarefa final (`ALL_DONE`) publica o Dataset se ao menos um jogo deu certo. |
| **Cobertura sem lacunas** | `raw.coleta_estado` por jogo: uma carga inicial interrompida continua em modo inicial no retry, e o watermark incremental **só avança se a janela inteira foi coberta**. Se o limite de páginas chegar antes do watermark, ele fica onde estava e a próxima execução recobre a janela. |
| **Dados sujos** | NUL e surrogates removidos antes do JSONB; inteiros com *clamp* em 2³¹−1 (a API já devolveu uint32 estourado); review sem data fica fora e é contada como aviso. |
| **Auditoria** | `raw.ingestion_log`: páginas, requisições, retentativas, 429 recebidos e motivo da parada, por jogo e execução. |

### 2.2 Idempotência em ambos os DAGs

| Camada | Garantia |
|---|---|
| Raw | `PK (recommendationid)` + `ON CONFLICT DO UPDATE ... WHERE payload_hash IS DISTINCT FROM` → *Clear/Retry* com o mesmo lote grava **0 linhas**. |
| Staging | `TRUNCATE` + reload a cada execução. |
| Dimensões | `UNIQUE` na chave natural + upsert: a SK de uma entidade nunca muda. |
| Fato | `UNIQUE (recommendationid)` + upsert: grão 1 review = 1 linha, então reprocessar **não infla métricas**. |
| Watermark | Avança só depois dos checks de qualidade (`GREATEST`), e uma falha no meio reprocessa a mesma janela. |

**Prova:** `python -m scripts.verificar_idempotencia` compara a impressão digital do DW (contagens, somas e **MD5 de todas as linhas da fato**) antes e depois de reprocessar a raw inteira. O teste `tests/test_integracao_dw.py` repete a prova no CI contra um Postgres real. Detalhes em [`docs/arquitetura.md`](docs/arquitetura.md).

### 2.3 Encadeamento

O DAG 2 é agendado por **Dataset** (`schedule=[RAW_REVIEWS_DATASET]`): ele roda **assim que o DAG 1 publica dados novos**, sem janela de tempo chutada.

---

## 3. Modelagem dimensional

> **Granularidade da fato `dw.fato_review`:** *cada linha representa UMA review publicada por um jogador sobre um jogo na Steam, na data em que a review foi criada.*

```mermaid
erDiagram
    DIM_TEMPO ||--o{ FATO_REVIEW : "sk_tempo"
    DIM_JOGO ||--o{ FATO_REVIEW : "sk_jogo"
    DIM_AUTOR ||--o{ FATO_REVIEW : "sk_autor"
    DIM_PERFIL_REVIEW ||--o{ FATO_REVIEW : "sk_perfil"
    DIM_REVIEW ||--|| FATO_REVIEW : "sk_review"
    FATO_REVIEW {
        bigint sk_fato PK
        int sk_tempo FK
        int sk_jogo FK
        int sk_autor FK
        int sk_perfil FK
        int sk_review FK
        string recommendationid "degenerada"
        int qtd_reviews "aditiva"
        int qtd_recomendacoes "aditiva"
        int votos_uteis "aditiva"
        int minutos_jogados_review "aditiva"
        int minutos_jogados_total "semiaditiva"
        decimal score_utilidade "nao aditiva"
    }
    DIM_TEMPO {
        int sk_tempo PK
        date data_completa
        int ano
        int trimestre
        int mes
        string nome_mes
        string dia_semana
        bool fim_de_semana
    }
    DIM_JOGO {
        int sk_jogo PK
        int app_id "NK"
        string nome_jogo
        string genero_principal
        string desenvolvedor
        decimal preco_base_brl
        date data_lancamento
    }
    DIM_AUTOR {
        int sk_autor PK
        string steamid "NK"
        int qtd_reviews_escritas
        string perfil_avaliador
    }
    DIM_PERFIL_REVIEW {
        int sk_perfil PK
        bool recomendado
        bool compra_steam
        bool recebido_gratis
        bool acesso_antecipado
        bool steam_deck
    }
    DIM_REVIEW {
        int sk_review PK
        string recommendationid "NK"
        string texto_limpo
        int qtd_palavras
    }
```

### Dicionário resumido

| Métrica | Tipo | Uso |
|---|---|---|
| `qtd_reviews`, `qtd_recomendacoes`, `qtd_nao_recomendacoes` | **Aditivas** | Volume e taxa de recomendação (`Σrec / Σreviews`) em qualquer corte |
| `votos_uteis`, `votos_engracados`, `qtd_comentarios`, `qtd_palavras` | **Aditivas** | Engajamento da comunidade |
| `minutos_jogados_review` | **Aditiva** | Experiência do autor ao escrever |
| `minutos_jogados_total` | **Semiaditiva** | Foto na data da coleta: não somar entre coletas |
| `score_utilidade` | **Não aditiva** | Média, nunca soma |

| Dimensão | Papel |
|---|---|
| `dim_tempo` | Calendário completo (dia, mês, trimestre, semestre, dia da semana, fim de semana) |
| `dim_jogo` | Jogo (SCD1): gênero, desenvolvedora, publicadora, preço em BRL, lançamento |
| `dim_autor` | Jogador (SCD1): reviews escritas e experiência como avaliador, em faixas |
| `dim_perfil_review` | ***Junk dimension***: 5 flags → 32 combinações pré-populadas |
| `dim_review` | Texto limpo (sem BBCode e URLs): corpus do motor de busca |

Todas as dimensões têm **surrogate key inteira** (`IDENTITY`) desacoplada da chave natural da Steam, além de um **membro desconhecido `-1`**. A fato tem **FOREIGN KEYs reais** para cada dimensão. Dicionário completo e decisões em [`docs/modelo_dimensional.md`](docs/modelo_dimensional.md).

---

## 4. Inteligência de recuperação de informação

O corpus é o `texto_limpo` da `dim_review`. O pré-processamento normaliza (minúsculas, sem acentos), remove stopwords do português e reduz plurais (etapa de plural inspirada no RSLP: *jogos → jogo*, *missões → missão*, *bons → bom*). O modelo de ranqueamento é o **BM25** (k₁ = 1,2; b = 0,75).

### 4.1 Linha de base (Antes)

**BM25 exaustivo:** para cada consulta, aloca um acumulador para **cada um dos N documentos da base**, soma as contribuições BM25 de todas as postagens dos termos e **ordena os N documentos** antes de cortar o Top-K. Custo: `O(postagens + N log N)` de tempo e `O(N)` de memória por consulta. Para isolar de onde vem o ganho, o benchmark também mede uma **ablação** (*TAAT + heap*: pontua todas as postagens mas extrai o Top-K com heap).

### 4.2 Técnica principal: WAND + Champion Lists + Min-Heap Top-K (Opção 2)

1. **Índice com limites exatos.** Na indexação, cada termo `t` guarda `UB(t) = max_d BM25(t,d)` e sua **Champion List**, os r = 64 documentos de maior impacto.
2. **Aquecimento do heap.** Antes de varrer as listas, o algoritmo soma as Champion Lists dos termos da consulta, pontua **exatamente** os 3K melhores candidatos e enche o **Min-Heap Top-K**. O limiar θ (o K-ésimo melhor score) já nasce alto.
3. **WAND (*Weak AND*, DAAT).** Os cursores ficam ordenados por `doc_id`. Somando os `UB` na ordem, o primeiro cursor que faz a soma passar de θ é o **pivô**. Se o primeiro cursor já está no pivô, o documento é pontuado por completo; senão, os cursores anteriores **saltam direto** até o pivô por busca binária, sem calcular score de nada no caminho.
4. **Segurança.** Todo documento antes do pivô tem score ≤ Σ UB anteriores ≤ θ, ou seja, nunca entraria no heap. Como θ vem de scores exatos de documentos reais, o **Top-K é idêntico ao exaustivo**, e os testes verificam isso.

**Variante avançada, Block-Max WAND** (Ding & Suel, 2011): as postagens são divididas em blocos de 64 com o score máximo de cada bloco. Achado o pivô, se a soma dos máximos **dos blocos** que o contêm não passa de θ, o algoritmo salta o intervalo inteiro, mesmo quando o UB global permitiria.

### 4.3 Técnica adicional: busca tolerante a erros em 2 estágios (Opção 3)

* **Estágio 1a, Trie:** autocompletar em `O(|P|)`. Cada nó guarda, já pré-calculadas, as 8 palavras mais frequentes abaixo dele.
* **Estágio 1b, índice de bigramas de caracteres** (`$tr, tr, ra, ...`): seleciona candidatos que compartilham k-gramas e filtra por **Jaccard ≥ 0,3** e diferença de tamanho ≤ 2.
* **Estágio 2, matriz de Levenshtein** (programação dinâmica) **apenas nos candidatos**. Ranqueia por (distância, frequência).
* **Baseline:** a mesma matriz de Levenshtein contra **todo o vocabulário**.
* No painel, a consulta "jogo trvando no servdor" vira **"Você quis dizer: jogo travando no servidor"** antes de ir para o BM25.

---

## 5. Resultados experimentais e benchmark

Método: média de 7 execuções com `time.perf_counter()`, 1 aquecimento, coletor de lixo desligado durante a medição, K = 10, mesmo índice e mesmas consultas para todos os algoritmos. `Δ% = (T_baseline − T_otimizado) / T_baseline × 100`; `Speedup = T_baseline / T_otimizado`; `Poda = % dos documentos candidatos (que contêm algum termo) que não precisaram ser pontuados`.

**Corpus:** as reviews reais do Data Warehouse. Das 39.961 reviews coletadas, 26.699 têm 3 palavras ou mais e entram no índice: 26.832 termos, 464.284 postagens, 20,5 termos por review em média. Medido dentro do container do painel (Python 3.12.16), em 2026-11-27. As tabelas completas estão em [`docs/resultados_benchmark.md`](docs/resultados_benchmark.md) e são regeneradas por `docker compose exec dashboard python -m scripts.benchmark`; o painel repete a medição ao vivo.

### 5.1 Ranqueamento Top-K: BM25 exaustivo vs. poda dinâmica

| Consulta | Candidatos | Exaustivo (ms) | TAAT+heap (ms) | WAND (ms) | **WAND + CL (ms)** | BMW (ms) | Δ% | Speedup | Poda | Top-K = |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| jogo travando muito | 17.642 | 5,79 | 5,00 | 5,72 | **0,11** | 0,12 | 98,1% | 51× | 99,8% | ✅ |
| servidor lag multiplayer | 257 | 1,27 | 0,07 | 0,19 | **0,14** | 0,18 | 88,7% | 8,8× | 84,0% | ✅ |
| cheater hacker banido | 232 | 1,00 | 0,11 | 0,32 | **0,21** | 0,27 | 79,4% | 4,9× | 36,6% | ✅ |
| preco caro promocao | 471 | 1,29 | 0,23 | 0,48 | **0,38** | 0,61 | 70,8% | 3,4× | 72,2% | ✅ |
| otimizacao ruim fps baixo | 861 | 1,37 | 0,22 | 0,47 | **0,46** | 0,68 | 66,5% | 3,0× | 82,8% | ✅ |
| bugs crash fechando sozinho | 719 | 1,19 | 0,18 | 0,33 | **0,47** | 0,51 | 60,5% | 2,5× | 91,8% | ✅ |
| jogar com amigos | 3.701 | 2,25 | 1,10 | 1,76 | **1,33** | 2,02 | 40,9% | 1,7× | 86,5% | ✅ |
| musica trilha sonora incrivel | 2.343 | 2,20 | 0,89 | 1,49 | **1,44** | 2,91 | 34,4% | 1,5× | 81,6% | ✅ |
| vale a pena comprar | 1.820 | 1,86 | 0,75 | 1,21 | **1,25** | 1,55 | 33,2% | 1,5× | 69,6% | ✅ |
| melhor jogo que ja joguei | 16.737 | 5,63 | 4,75 | 4,30 | **4,14** | 7,05 | 26,5% | 1,4× | 92,8% | ✅ |
| graficos lindos mundo aberto | 2.861 | 2,06 | 0,95 | 1,61 | **1,71** | 2,38 | 17,1% | 1,2× | 80,9% | ✅ |
| historia emocionante personagens | 3.614 | 2,23 | 1,14 | 2,54 | **2,32** | 0,78 | -4,1% | 1,0× | 71,4% | ✅ |

| Algoritmo | Tempo médio | Δ% | Speedup | Poda | Memória/consulta |
|---|---:|---:|---:|---:|---:|
| BM25 exaustivo (baseline) | 2,35 ms | — | 1,0× | 0% | 1.583 KB |
| TAAT + heap (ablação) | 1,28 ms | 45,3% | 1,83× | 0% | — |
| WAND clássico | 1,70 ms | 27,5% | 1,38× | 83,3% | 2 KB |
| **WAND + Champion Lists** | **1,16 ms** | **50,4%** | **2,02×** | **90,6%** | **14 KB** |
| Block-Max WAND | 1,59 ms | 32,3% | 1,48× | 93,6% | 14 KB |

### 5.2 Correção ortográfica: 2 estágios vs. Levenshtein força-bruta

| Métrica | Força bruta | 2 estágios |
|---|---:|---:|
| Tempo médio por palavra | 226,0 ms | **2,80 ms** |
| Candidatos avaliados com Levenshtein | 15.617 (vocabulário inteiro) | 8 a 194 |
| Δ% / Speedup | — | **98,8% / 81×** |
| Mesma sugestão que a força bruta | — | **100%** (12/12) |
| Autocompletar por prefixo (Trie) | — | 0,0006 ms |

### 5.3 Escalabilidade (prefixos do corpus real)

| Documentos | Exaustivo | WAND + CL | Block-Max | Speedup WAND + CL | Poda |
|---:|---:|---:|---:|---:|---:|
| 5.000 | 0,33 ms | 0,47 ms | 0,62 ms | 0,70× | 74,6% |
| 10.000 | 0,69 ms | 0,89 ms | 1,13 ms | 0,78× | 78,0% |
| 20.000 | 1,47 ms | 0,86 ms | 0,99 ms | 1,72× | 89,5% |
| 26.699 | 2,48 ms | 1,41 ms | 1,46 ms | 1,76× | 90,6% |

### 5.4 Interpretação

* **Ganho médio de 2,0×, sem perder nada.** O WAND + Champion Lists responde em 1,16 ms contra 2,35 ms do exaustivo (50,4% menos tempo), pontuando só 9,4% dos candidatos. O Top-K é **idêntico** ao exaustivo (mesmos documentos, mesma ordem, mesmos scores) nas 12 consultas. A memória por consulta cai de 1.583 KB para 14 KB.
* **O ganho depende muito da consulta.** Em "jogo travando muito" são 17.642 candidatos e o WAND aquecido resolve em 0,11 ms (**51×**, 99,8% de poda): um termo raro com limite alto deixa os termos frequentes sem chance de entrar no Top-K sozinhos, e quase tudo é saltado. Em "historia emocionante personagens" os termos têm frequência e limites parecidos, nenhum domina, e o WAND + CL empata com o exaustivo (0,96×); nessa consulta o Block-Max WAND, que usa limites locais por bloco, é o melhor (0,78 ms). O WAND + CL vence o baseline em 11 das 12 consultas.
* **A ablação mostra de onde vem o ganho.** Só trocar a ordenação total por um heap (TAAT + heap) já dá 1,83×, porque elimina o `O(N log N)` e a memória `O(N)`. O WAND clássico poda 83,3% dos documentos, mas fica em 1,38×, abaixo da ablação: em Python puro cada passo do WAND (ordenar cursores, achar o pivô, busca binária) custa mais que somar uma postagem, e as reviews são curtas (20 termos), então as listas são pequenas. As Champion Lists resolvem o início frio (θ = 0) e levam a 2,02×.
* **Block-Max WAND poda mais (93,6%) e não é o mais rápido na média (1,48×).** O ponteiro de bloco acrescenta trabalho por pivô. É o trade-off clássico entre o custo da poda e as avaliações economizadas; em linguagem compilada, onde cada passo custa nanossegundos, a poda extra tende a compensar.
* **Há um ponto de cruzamento.** Com 5.000 documentos o WAND + CL perde (0,70×) e com 10.000 ainda perde (0,78×); a partir de 20.000 passa a ganhar (1,72×) e a poda sobe de 74,6% para 90,6%. O custo do exaustivo cresce com N; o do WAND depende mais de K e dos termos raros. A base atual está logo acima do cruzamento, e o ganho deve crescer conforme a coleta diária acumular reviews.
* **Correção ortográfica: 81× com a mesma resposta.** O índice de bigramas com Jaccard reduz os candidatos de 15.617 palavras para 8 a 194, e o Levenshtein roda só neles: 226 ms viram 2,8 ms, com a **mesma sugestão** da força bruta em 12 de 12 palavras. Isso viabiliza o "Você quis dizer" a cada busca.
* **Limitações.** Os tempos são de Python puro numa máquina de uso geral, com o Airflow e o Postgres rodando ao lado, e variam alguns décimos de milissegundo entre execuções; as razões entre algoritmos são o resultado estável. As 12 consultas são um conjunto fixo escolhido para cobrir termos frequentes, médios e raros, não uma amostra de consultas de usuários.

---

## 6. Guia passo a passo de execução (*How-to-Run*)

**Pré-requisitos:** Docker Desktop (com ≥ 4 GB de RAM para o Docker) e Git. Python 3.12+ só é preciso para rodar testes e scripts fora dos containers.

```bash
# 1. Clonar
git clone <url-deste-repositorio> projeto-t2-fucape
cd projeto-t2-fucape

# 2. (opcional) ajustar parâmetros: cp .env.example .env

# 3. Subir tudo: Postgres x2, Airflow (init, webserver, scheduler, triggerer) e o painel
docker compose up -d
docker compose ps          # aguarde os serviços ficarem "healthy" (~1-2 min)
```

| Serviço | Endereço | Login |
|---|---|---|
| Airflow | http://localhost:8080 | `airflow` / `airflow` |
| Painel Streamlit | http://localhost:8501 | — |
| Data Warehouse (Postgres) | `localhost:5433`, banco `dw` | `dw` / `dw` |

```text
# 4. Disparar os DAGs
Airflow → DAGs → ative (toggle) dag_ingestao_raw e dag_consolidacao_dw
Airflow → dag_ingestao_raw → ▶ Trigger DAG
  ↳ coleta os 16 jogos (~5 min na primeira carga: 400 páginas a 1 req/s, 2 jogos em paralelo)
  ↳ ao terminar, publica o Dataset e o dag_consolidacao_dw dispara sozinho

# 5. Abrir o painel: http://localhost:8501 → "Recarregar dados"
```

```bash
# 6. Benchmark com as reviews reais (gera docs/resultados_benchmark.md e .json)
docker compose exec dashboard python -m scripts.benchmark

# 7. Prova de idempotência (reprocessa a raw inteira e compara a impressão digital do DW)
docker compose exec dashboard python -m scripts.verificar_idempotencia

# 8. Explorar o Star Schema
docker compose exec dw-postgres psql -U dw -d dw -c "\dt dw.*"
docker compose exec dw-postgres psql -U dw -d dw -c "SELECT * FROM dw.fato_review LIMIT 5;"

# 9. Testes (unitários; a integração roda num banco *_teste separado)
pip install -r requirements.txt
python -m pytest
docker compose exec dw-postgres createdb -U dw dw_teste
RODAR_INTEGRACAO=1 DW_DB=dw_teste python -m pytest tests/test_integracao_dw.py -v

# Parar (mantém os dados) / apagar tudo, inclusive os volumes
docker compose down
docker compose down -v
```

**Painel sem Docker** (com o DW de pé): `pip install -r requirements.txt && streamlit run app/app.py`. Sem banco, a aba de busca usa um corpus sintético para demonstração.

### Solução de problemas

| Sintoma | Causa e solução |
|---|---|
| Logs do DAG 1 com `erro de rede: SSLError ... aguardando Xs` em todas as tentativas | A rede tem um firewall que intercepta HTTPS (ex.: Fortinet em rede corporativa ou universitária) e reemite o certificado da Steam. O pipeline trata corretamente como erro retentável, com backoff, mas não desliga a verificação TLS de propósito. Rode numa rede sem inspeção (doméstica ou roteador do celular) e use **Clear** na execução com falha. |
| `docker compose ps` com Airflow reiniciando | Docker com pouca memória: reserve ≥ 4 GB em Docker Desktop → Settings → Resources. |
| Painel diz "DW vazio" | Os DAGs ainda não rodaram. Depois da carga, clique em **Recarregar dados** na barra lateral. |

---

## 7. Estrutura do repositório e qualidade de software

```text
projeto-t2-fucape/
├── README.md                        # este relatório
├── docker-compose.yml               # Airflow (webserver, scheduler, triggerer, init) + 2 Postgres + painel
├── requirements.txt · pytest.ini · .env.example · .gitignore
├── .github/workflows/ci.yml         # lint + testes + integração com Postgres + import das DAGs
├── dags/
│   ├── dag_ingestao_raw.py          # DAG 1: cursor, backoff, mapeamento dinâmico, Dataset
│   └── dag_consolidacao_dw.py       # DAG 2: staging → dimensões → fato → checks → watermark
├── src/
│   ├── config.py · db.py · datasets.py
│   ├── ingestion/
│   │   ├── http_client.py           # rate limit + exponential backoff com jitter + Retry-After
│   │   ├── steam_api.py             # paginação por cursor e condições de parada
│   │   └── raw_store.py             # upserts idempotentes na camada bronze
│   ├── warehouse/
│   │   ├── loader.py                # orquestra a carga, dim_jogo, checks de qualidade
│   │   └── sql/                     # DDL do star schema + SQL de staging, dimensões e fato
│   └── search_engine/
│       ├── text.py                  # normalização, stopwords, redução de plural
│       ├── index.py                 # índice invertido BM25 + UB + blocos + champion lists
│       ├── baseline.py              # BM25 exaustivo (Antes) + ablação TAAT+heap
│       ├── optimized.py             # WAND · WAND+Champion Lists · Block-Max WAND (Depois)
│       ├── spelling.py              # Trie + k-gramas/Jaccard + Levenshtein (2 estágios)
│       ├── benchmark.py             # perf_counter, tracemalloc, Δ%, speedup, poda
│       └── motor.py · corpus.py · sintetico.py
├── app/
│   ├── app.py                       # painel: Negócios · Busca · Engenharia & Benchmark · Modelo
│   └── consultas.py                 # SQL analítico sobre o star schema
├── scripts/
│   ├── benchmark.py                 # gera docs/resultados_benchmark.{md,json}
│   └── verificar_idempotencia.py    # prova de idempotência por impressão digital do DW
├── tests/                           # 126 testes (busca, ortografia, ingestão, transformação, integração)
└── docs/
    ├── arquitetura.md               # diagramas e decisões de engenharia
    ├── modelo_dimensional.md        # granularidade, DER, dicionário de dados
    ├── resultados_benchmark.md      # tabelas completas geradas pelo script
    └── roteiro_video.md             # roteiro da apresentação de 10 minutos
```

**Qualidade:** código modular por responsabilidade, PEP 8 verificado com `ruff`, docstrings explicando cada decisão, 126 testes automatizados (incluindo prova de poda segura e de idempotência contra Postgres real) e CI no GitHub Actions a cada push.

### Referências
* Broder, A. et al. *Efficient query evaluation using a two-level retrieval process* (WAND). CIKM, 2003.
* Ding, S.; Suel, T. *Faster top-k document retrieval using block-max indexes*. SIGIR, 2011.
* Manning, C.; Raghavan, P.; Schütze, H. *Introduction to Information Retrieval*, cap. 3 (tolerant retrieval) e cap. 7 (champion lists, heaps).
* Robertson, S.; Zaragoza, H. *The Probabilistic Relevance Framework: BM25 and Beyond*, 2009.
* Kimball, R.; Ross, M. *The Data Warehouse Toolkit*, 3ª ed. (junk dimensions, degenerate dimensions, surrogate keys).
* AWS Architecture Blog. *Exponential Backoff And Jitter*.
