"""Prova de idempotencia da carga analitica (para a demonstracao em video).

1. Tira uma "impressao digital" do DW: contagens de cada tabela, somas das metricas
   aditivas da fato e um hash MD5 de todas as linhas da fato (ordenadas pela chave natural).
2. Reexecuta a consolidacao inteira em FULL REFRESH (reprocessa toda a camada raw).
3. Tira a impressao digital de novo e compara: tem que ser identica.

Uso: python -m scripts.verificar_idempotencia
"""

from __future__ import annotations

import json

from src.db import transacao
from src.warehouse import loader

SQL_DIGITAL = """
SELECT
  (SELECT count(*) FROM raw.steam_reviews)      AS raw_reviews,
  (SELECT count(*) FROM dw.dim_tempo)           AS dim_tempo,
  (SELECT count(*) FROM dw.dim_jogo)            AS dim_jogo,
  (SELECT count(*) FROM dw.dim_autor)           AS dim_autor,
  (SELECT count(*) FROM dw.dim_perfil_review)   AS dim_perfil_review,
  (SELECT count(*) FROM dw.dim_review)          AS dim_review,
  (SELECT count(*) FROM dw.fato_review)         AS fato_linhas,
  (SELECT sum(qtd_reviews) FROM dw.fato_review) AS soma_qtd_reviews,
  (SELECT sum(votos_uteis) FROM dw.fato_review) AS soma_votos_uteis,
  (SELECT sum(minutos_jogados_review) FROM dw.fato_review) AS soma_minutos,
  (SELECT md5(string_agg(concat_ws('|', recommendationid, sk_tempo, sk_jogo, sk_autor, sk_perfil, sk_review,
                                   qtd_reviews, qtd_recomendacoes, votos_uteis, minutos_jogados_review),
                         ',' ORDER BY recommendationid)) FROM dw.fato_review) AS hash_fato
"""


def impressao_digital() -> dict:
    with transacao() as conn, conn.cursor() as cur:
        cur.execute(SQL_DIGITAL)
        colunas = [c[0] for c in cur.description]
        return dict(zip(colunas, (str(v) for v in cur.fetchone())))


def main() -> None:
    antes = impressao_digital()
    print("ANTES  :", json.dumps(antes, indent=2))
    loader.executar_tudo(run_id="prova_idempotencia", full_refresh=True)
    depois = impressao_digital()
    print("DEPOIS :", json.dumps(depois, indent=2))
    diferencas = {k: (antes[k], depois[k]) for k in antes if antes[k] != depois[k]}
    if diferencas:
        print("\nDIFERENCAS ENCONTRADAS:", diferencas)
        raise SystemExit(1)
    print("\nOK: reprocessar toda a camada raw nao alterou nenhuma linha nem metrica do DW (idempotente).")


if __name__ == "__main__":
    main()
