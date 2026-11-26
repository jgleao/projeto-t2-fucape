-- =============================================================================
-- STAGING: le a camada raw (somente o que mudou desde o ultimo watermark, ou
-- tudo em full refresh), limpa, tipa, desaninha o JSON e deduplica.
-- Parametro: %(watermark)s  (timestamptz)
-- =============================================================================
TRUNCATE stg.reviews;

INSERT INTO stg.reviews
SELECT
    x.recommendationid,
    x.app_id,
    x.steamid,
    x.autor_qtd_jogos,
    x.autor_qtd_reviews,
    x.minutos_jogados_total,
    x.minutos_jogados_review,
    x.idioma,
    x.criado_em,
    x.atualizado_em,
    x.recomendado,
    x.compra_steam,
    x.recebido_gratis,
    x.acesso_antecipado,
    x.steam_deck,
    x.votos_uteis,
    x.votos_engracados,
    x.qtd_comentarios,
    x.score_utilidade,
    x.texto_original,
    x.texto_limpo,
    CASE WHEN x.texto_limpo = '' THEN 0
         ELSE array_length(regexp_split_to_array(x.texto_limpo, '\s+'), 1) END,
    length(x.texto_limpo)
FROM (
    SELECT DISTINCT ON (r.recommendationid)
        r.recommendationid,
        r.app_id,
        NULLIF(r.payload -> 'author' ->> 'steamid', '')                        AS steamid,
        NULLIF(r.payload -> 'author' ->> 'num_games_owned', '')::INTEGER       AS autor_qtd_jogos,
        NULLIF(r.payload -> 'author' ->> 'num_reviews', '')::INTEGER           AS autor_qtd_reviews,
        COALESCE(NULLIF(r.payload -> 'author' ->> 'playtime_forever', '')::INTEGER, 0)   AS minutos_jogados_total,
        COALESCE(NULLIF(r.payload -> 'author' ->> 'playtime_at_review', '')::INTEGER,
                 NULLIF(r.payload -> 'author' ->> 'playtime_forever', '')::INTEGER, 0)   AS minutos_jogados_review,
        r.payload ->> 'language'                                               AS idioma,
        (to_timestamp((r.payload ->> 'timestamp_created')::BIGINT) AT TIME ZONE 'America/Sao_Paulo') AS criado_em,
        (to_timestamp(NULLIF(r.payload ->> 'timestamp_updated', '')::BIGINT) AT TIME ZONE 'America/Sao_Paulo') AS atualizado_em,
        COALESCE((r.payload ->> 'voted_up')::BOOLEAN, FALSE)                   AS recomendado,
        COALESCE((r.payload ->> 'steam_purchase')::BOOLEAN, FALSE)             AS compra_steam,
        COALESCE((r.payload ->> 'received_for_free')::BOOLEAN, FALSE)          AS recebido_gratis,
        COALESCE((r.payload ->> 'written_during_early_access')::BOOLEAN, FALSE) AS acesso_antecipado,
        COALESCE((r.payload ->> 'primarily_steam_deck')::BOOLEAN, FALSE)       AS steam_deck,
        COALESCE(NULLIF(r.payload ->> 'votes_up', '')::INTEGER, 0)             AS votos_uteis,
        -- votes_funny as vezes vem como 4294967295 (overflow na API): trata como 0
        CASE WHEN COALESCE(NULLIF(r.payload ->> 'votes_funny', '')::BIGINT, 0) BETWEEN 0 AND 1000000
             THEN COALESCE(NULLIF(r.payload ->> 'votes_funny', '')::BIGINT, 0)::INTEGER
             ELSE 0 END                                                        AS votos_engracados,
        COALESCE(NULLIF(r.payload ->> 'comment_count', '')::INTEGER, 0)        AS qtd_comentarios,
        NULLIF(r.payload ->> 'weighted_vote_score', '')::NUMERIC(12, 10)       AS score_utilidade,
        r.payload ->> 'review'                                                 AS texto_original,
        -- limpeza: remove tags BBCode ([b], [/url], [h1]...), URLs e espacos repetidos
        btrim(regexp_replace(
            regexp_replace(
                regexp_replace(COALESCE(r.payload ->> 'review', ''), '\[/?[^]]{1,30}\]', ' ', 'g'),
                'https?://\S+', ' ', 'g'),
            '\s+', ' ', 'g'))                                                  AS texto_limpo
    FROM raw.steam_reviews r
    WHERE r.last_ingested_at > %(watermark)s
      AND r.payload ? 'timestamp_created'
    ORDER BY r.recommendationid, r.timestamp_updated DESC NULLS LAST
) x;
