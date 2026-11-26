-- dim_review (SCD tipo 1): texto da review, corpus indexado pelo motor de busca.
INSERT INTO dw.dim_review (recommendationid, idioma, texto_original, texto_limpo, qtd_palavras, faixa_tamanho)
SELECT
    s.recommendationid,
    s.idioma,
    s.texto_original,
    s.texto_limpo,
    s.qtd_palavras,
    CASE WHEN s.qtd_palavras = 0   THEN '0. Sem texto'
         WHEN s.qtd_palavras < 10  THEN '1. Curta (<10 palavras)'
         WHEN s.qtd_palavras < 50  THEN '2. Media (10-49)'
         WHEN s.qtd_palavras < 200 THEN '3. Longa (50-199)'
         ELSE '4. Muito longa (200+)' END
FROM stg.reviews s
ON CONFLICT (recommendationid) DO UPDATE SET
    idioma         = EXCLUDED.idioma,
    texto_original = EXCLUDED.texto_original,
    texto_limpo    = EXCLUDED.texto_limpo,
    qtd_palavras   = EXCLUDED.qtd_palavras,
    faixa_tamanho  = EXCLUDED.faixa_tamanho,
    atualizado_em  = now()
WHERE dw.dim_review.texto_original IS DISTINCT FROM EXCLUDED.texto_original;
