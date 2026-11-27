-- =============================================================================
-- STAGING: le a camada raw (somente o que mudou desde o ultimo watermark, ou
-- tudo em full refresh), limpa, tipa, desaninha o JSON e deduplica.
-- Parametro: %(watermark)s  (timestamptz)
--
-- Robustez: todo inteiro vindo da API passa por um "clamp" para [0, 2^31-1]
-- (a Steam ja devolveu uint32 estourado, ex.: votes_funny = 4294967295) e
-- reviews sem timestamp_created ficam de fora (os checks usam o mesmo criterio).
-- =============================================================================
TRUNCATE stg.reviews;

INSERT INTO stg.reviews (
    recommendationid, app_id, steamid, autor_qtd_reviews, minutos_jogados_total,
    minutos_jogados_review, idioma, criado_em, atualizado_em, recomendado, compra_steam, recebido_gratis,
    acesso_antecipado, steam_deck, votos_uteis, votos_engracados, qtd_comentarios, score_utilidade,
    texto_original, texto_limpo, qtd_palavras, qtd_caracteres, ingerido_em)
SELECT
    x.recommendationid, x.app_id, x.steamid, x.autor_qtd_reviews,
    COALESCE(x.minutos_total, 0),
    COALESCE(x.minutos_review, x.minutos_total, 0),
    x.idioma, x.criado_em, x.atualizado_em, x.recomendado, x.compra_steam, x.recebido_gratis,
    x.acesso_antecipado, x.steam_deck,
    COALESCE(x.votos_uteis, 0), COALESCE(x.votos_engracados, 0), COALESCE(x.qtd_comentarios, 0),
    x.score_utilidade, x.texto_original, x.texto_limpo,
    CASE WHEN x.texto_limpo = '' THEN 0
         ELSE array_length(regexp_split_to_array(x.texto_limpo, '\s+'), 1) END,
    length(x.texto_limpo),
    x.ingerido_em
FROM (
    SELECT DISTINCT ON (r.recommendationid)
        r.recommendationid,
        r.app_id,
        r.last_ingested_at                                                      AS ingerido_em,
        NULLIF(r.payload -> 'author' ->> 'steamid', '')                         AS steamid,
        n.autor_qtd_reviews, n.minutos_total, n.minutos_review,
        n.votos_uteis, n.votos_engracados, n.qtd_comentarios,
        r.payload ->> 'language'                                                AS idioma,
        (to_timestamp((r.payload ->> 'timestamp_created')::BIGINT) AT TIME ZONE 'America/Sao_Paulo') AS criado_em,
        (to_timestamp(NULLIF(r.payload ->> 'timestamp_updated', '')::BIGINT) AT TIME ZONE 'America/Sao_Paulo') AS atualizado_em,
        COALESCE((r.payload ->> 'voted_up')::BOOLEAN, FALSE)                    AS recomendado,
        COALESCE((r.payload ->> 'steam_purchase')::BOOLEAN, FALSE)              AS compra_steam,
        COALESCE((r.payload ->> 'received_for_free')::BOOLEAN, FALSE)           AS recebido_gratis,
        COALESCE((r.payload ->> 'written_during_early_access')::BOOLEAN, FALSE) AS acesso_antecipado,
        COALESCE((r.payload ->> 'primarily_steam_deck')::BOOLEAN, FALSE)        AS steam_deck,
        -- weighted_vote_score vai de 0 a 1; fora disso vira NULL em vez de derrubar a carga
        CASE WHEN (r.payload ->> 'weighted_vote_score') ~ '^[0-9]+(\.[0-9]+)?$'
              AND (r.payload ->> 'weighted_vote_score')::NUMERIC < 100
             THEN (r.payload ->> 'weighted_vote_score')::NUMERIC(12, 10) END    AS score_utilidade,
        r.payload ->> 'review'                                                  AS texto_original,
        -- limpeza: remove tags BBCode ([b], [/url], [h1]...), URLs e espacos repetidos
        btrim(regexp_replace(
            regexp_replace(
                regexp_replace(COALESCE(r.payload ->> 'review', ''), '\[/?[^]]{1,30}\]', ' ', 'g'),
                'https?://\S+', ' ', 'g'),
            '\s+', ' ', 'g'))                                                   AS texto_limpo
    FROM raw.steam_reviews r
    CROSS JOIN LATERAL (
        -- inteiros com clamp em [0, 2147483647]; texto nao numerico vira NULL
        SELECT
            CASE WHEN v.reviews ~ '^[0-9]+$' THEN LEAST(v.reviews::NUMERIC, 2147483647)::INTEGER END AS autor_qtd_reviews,
            CASE WHEN v.total   ~ '^[0-9]+$' THEN LEAST(v.total::NUMERIC,   2147483647)::INTEGER END AS minutos_total,
            CASE WHEN v.na_rev  ~ '^[0-9]+$' THEN LEAST(v.na_rev::NUMERIC,  2147483647)::INTEGER END AS minutos_review,
            CASE WHEN v.uteis   ~ '^[0-9]+$' THEN LEAST(v.uteis::NUMERIC,   2147483647)::INTEGER END AS votos_uteis,
            -- votes_funny estourado (>= 2^31) e lixo da API, nao uma contagem: vira 0
            CASE WHEN v.funny   ~ '^[0-9]+$' AND v.funny::NUMERIC < 2147483647 THEN v.funny::INTEGER ELSE 0 END
                                                                                              AS votos_engracados,
            CASE WHEN v.coment  ~ '^[0-9]+$' THEN LEAST(v.coment::NUMERIC,  2147483647)::INTEGER END AS qtd_comentarios
        FROM (SELECT r.payload -> 'author' ->> 'num_reviews'        AS reviews,
                     r.payload -> 'author' ->> 'playtime_forever'   AS total,
                     r.payload -> 'author' ->> 'playtime_at_review' AS na_rev,
                     r.payload ->> 'votes_up'                       AS uteis,
                     r.payload ->> 'votes_funny'                    AS funny,
                     r.payload ->> 'comment_count'                  AS coment) v
    ) n
    WHERE r.last_ingested_at > %(watermark)s
      AND (r.payload ->> 'timestamp_created') ~ '^[0-9]+$'
    ORDER BY r.recommendationid, r.timestamp_updated DESC NULLS LAST
) x;
