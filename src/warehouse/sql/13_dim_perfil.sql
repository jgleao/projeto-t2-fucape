-- dim_perfil_review (junk dimension): pre-popula as 32 combinacoes possiveis das
-- 5 flags. ON CONFLICT DO NOTHING -> idempotente e com SKs estaveis.
INSERT INTO dw.dim_perfil_review (recomendado, compra_steam, recebido_gratis, acesso_antecipado, steam_deck,
                                  desc_recomendacao, desc_aquisicao, desc_fase_jogo, desc_plataforma)
SELECT r.v, c.v, g.v, a.v, d.v,
       CASE WHEN r.v THEN 'Recomendado' ELSE 'Nao recomendado' END,
       CASE WHEN g.v THEN 'Recebido gratis' WHEN c.v THEN 'Comprado na Steam' ELSE 'Outra origem (key)' END,
       CASE WHEN a.v THEN 'Acesso antecipado' ELSE 'Versao lancada' END,
       CASE WHEN d.v THEN 'Steam Deck' ELSE 'PC / outros' END
FROM (VALUES (TRUE), (FALSE)) r(v)
CROSS JOIN (VALUES (TRUE), (FALSE)) c(v)
CROSS JOIN (VALUES (TRUE), (FALSE)) g(v)
CROSS JOIN (VALUES (TRUE), (FALSE)) a(v)
CROSS JOIN (VALUES (TRUE), (FALSE)) d(v)
ORDER BY 1 DESC, 2 DESC, 3, 4, 5
ON CONFLICT (recomendado, compra_steam, recebido_gratis, acesso_antecipado, steam_deck) DO NOTHING;
