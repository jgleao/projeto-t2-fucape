-- dim_autor (SCD tipo 1): um registro por steamid com os atributos mais recentes.
INSERT INTO dw.dim_autor (steamid, qtd_reviews_escritas, perfil_avaliador)
SELECT DISTINCT ON (s.steamid)
    s.steamid,
    s.autor_qtd_reviews,
    CASE WHEN s.autor_qtd_reviews IS NULL THEN 'Não informado'
         WHEN s.autor_qtd_reviews <= 1  THEN '1. Primeira review'
         WHEN s.autor_qtd_reviews < 10  THEN '2. Ocasional (2-9)'
         WHEN s.autor_qtd_reviews < 50  THEN '3. Frequente (10-49)'
         ELSE '4. Veterano (50+)' END
FROM stg.reviews s
WHERE s.steamid IS NOT NULL
ORDER BY s.steamid, s.atualizado_em DESC NULLS LAST
ON CONFLICT (steamid) DO UPDATE SET
    qtd_reviews_escritas = EXCLUDED.qtd_reviews_escritas,
    perfil_avaliador     = EXCLUDED.perfil_avaliador,
    atualizado_em        = now()
WHERE dw.dim_autor.qtd_reviews_escritas IS DISTINCT FROM EXCLUDED.qtd_reviews_escritas;
