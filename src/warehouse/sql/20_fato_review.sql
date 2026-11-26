-- fato_review: grao = uma review. Lookup das SKs pelas chaves naturais; membro -1
-- quando nao encontrado. UPSERT pela chave degenerada recommendationid: reexecutar
-- nunca duplica linhas nem infla metricas (apenas atualiza votos que mudaram).
INSERT INTO dw.fato_review (
    recommendationid, sk_tempo, sk_jogo, sk_autor, sk_perfil, sk_review,
    qtd_reviews, qtd_recomendacoes, qtd_nao_recomendacoes, votos_uteis, votos_engracados,
    qtd_comentarios, minutos_jogados_review, qtd_palavras, minutos_jogados_total, score_utilidade)
SELECT
    s.recommendationid,
    COALESCE(t.sk_tempo, -1),
    COALESCE(j.sk_jogo, -1),
    COALESCE(a.sk_autor, -1),
    COALESCE(p.sk_perfil, -1),
    COALESCE(r.sk_review, -1),
    1,
    CASE WHEN s.recomendado THEN 1 ELSE 0 END,
    CASE WHEN s.recomendado THEN 0 ELSE 1 END,
    s.votos_uteis,
    s.votos_engracados,
    s.qtd_comentarios,
    s.minutos_jogados_review,
    s.qtd_palavras,
    s.minutos_jogados_total,
    s.score_utilidade
FROM stg.reviews s
LEFT JOIN dw.dim_tempo  t ON t.data_completa = s.criado_em::DATE
LEFT JOIN dw.dim_jogo   j ON j.app_id = s.app_id
LEFT JOIN dw.dim_autor  a ON a.steamid = s.steamid
LEFT JOIN dw.dim_review r ON r.recommendationid = s.recommendationid
LEFT JOIN dw.dim_perfil_review p
       ON (p.recomendado, p.compra_steam, p.recebido_gratis, p.acesso_antecipado, p.steam_deck)
        = (s.recomendado, s.compra_steam, s.recebido_gratis, s.acesso_antecipado, s.steam_deck)
ON CONFLICT (recommendationid) DO UPDATE SET
    sk_tempo               = EXCLUDED.sk_tempo,
    sk_jogo                = EXCLUDED.sk_jogo,
    sk_autor               = EXCLUDED.sk_autor,
    sk_perfil              = EXCLUDED.sk_perfil,
    sk_review              = EXCLUDED.sk_review,
    qtd_recomendacoes      = EXCLUDED.qtd_recomendacoes,
    qtd_nao_recomendacoes  = EXCLUDED.qtd_nao_recomendacoes,
    votos_uteis            = EXCLUDED.votos_uteis,
    votos_engracados       = EXCLUDED.votos_engracados,
    qtd_comentarios        = EXCLUDED.qtd_comentarios,
    minutos_jogados_review = EXCLUDED.minutos_jogados_review,
    qtd_palavras           = EXCLUDED.qtd_palavras,
    minutos_jogados_total  = EXCLUDED.minutos_jogados_total,
    score_utilidade        = EXCLUDED.score_utilidade,
    carregado_em           = now()
WHERE (dw.fato_review.sk_perfil, dw.fato_review.sk_jogo, dw.fato_review.sk_autor, dw.fato_review.votos_uteis,
       dw.fato_review.votos_engracados, dw.fato_review.qtd_comentarios, dw.fato_review.minutos_jogados_total,
       dw.fato_review.score_utilidade, dw.fato_review.qtd_palavras)
      IS DISTINCT FROM
      (EXCLUDED.sk_perfil, EXCLUDED.sk_jogo, EXCLUDED.sk_autor, EXCLUDED.votos_uteis,
       EXCLUDED.votos_engracados, EXCLUDED.qtd_comentarios, EXCLUDED.minutos_jogados_total,
       EXCLUDED.score_utilidade, EXCLUDED.qtd_palavras)
RETURNING (xmax = 0) AS inserida;
