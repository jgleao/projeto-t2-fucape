-- dim_tempo: gera o calendario completo (dia a dia) cobrindo os meses das reviews
-- em staging. ON CONFLICT DO NOTHING -> idempotente; datas ja existentes mantem a SK.
WITH limites AS (
    SELECT date_trunc('month', min(criado_em))::DATE AS inicio,
           (date_trunc('month', max(criado_em)) + INTERVAL '1 month - 1 day')::DATE AS fim
    FROM stg.reviews
)
INSERT INTO dw.dim_tempo (data_completa, ano, semestre, trimestre, mes, nome_mes, ano_mes, dia,
                          dia_semana_num, dia_semana, fim_de_semana, semana_ano)
SELECT
    g.d::DATE,
    EXTRACT(YEAR FROM g.d)::INTEGER,
    CASE WHEN EXTRACT(MONTH FROM g.d) <= 6 THEN 1 ELSE 2 END,
    EXTRACT(QUARTER FROM g.d)::INTEGER,
    EXTRACT(MONTH FROM g.d)::INTEGER,
    (ARRAY['Janeiro','Fevereiro','Marco','Abril','Maio','Junho','Julho','Agosto',
           'Setembro','Outubro','Novembro','Dezembro'])[EXTRACT(MONTH FROM g.d)::INTEGER],
    to_char(g.d, 'YYYY-MM'),
    EXTRACT(DAY FROM g.d)::INTEGER,
    EXTRACT(ISODOW FROM g.d)::INTEGER,
    (ARRAY['Segunda-feira','Terca-feira','Quarta-feira','Quinta-feira','Sexta-feira',
           'Sabado','Domingo'])[EXTRACT(ISODOW FROM g.d)::INTEGER],
    EXTRACT(ISODOW FROM g.d) IN (6, 7),
    EXTRACT(WEEK FROM g.d)::INTEGER
FROM limites l
CROSS JOIN LATERAL generate_series(l.inicio, l.fim, INTERVAL '1 day') AS g(d)
WHERE l.inicio IS NOT NULL
ON CONFLICT (data_completa) DO NOTHING;
