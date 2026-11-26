"""Acesso a API publica da Steam (sem chave): reviews paginadas por cursor e detalhes do jogo.

Endpoints:
* GET https://store.steampowered.com/appreviews/{app_id}?json=1&cursor=...
  Pagina por cursor opaco; a primeira pagina usa cursor="*". filter=recent
  ordena da review mais nova para a mais antiga, o que permite parar a coleta
  ao alcancar o watermark (carga incremental).
* GET https://store.steampowered.com/api/appdetails?appids={app_id}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from src.ingestion.http_client import ClienteHttpResiliente

URL_REVIEWS = "https://store.steampowered.com/appreviews/{app_id}"
URL_DETALHES = "https://store.steampowered.com/api/appdetails"


class RespostaInvalida(Exception):
    pass


@dataclass
class PaginaReviews:
    numero: int
    cursor: str
    reviews: list[dict[str, Any]]
    resumo: dict[str, Any]


@dataclass
class ResultadoPaginacao:
    paginas: int = 0
    reviews: int = 0
    motivo_parada: str = ""


class SteamApi:
    def __init__(self, http: ClienteHttpResiliente | None = None):
        self.http = http or ClienteHttpResiliente()

    def detalhes_jogo(self, app_id: int) -> dict[str, Any]:
        """Retorna o objeto bruto {"success": bool, "data": {...}} do jogo."""
        corpo = self.http.get_json(URL_DETALHES, params={"appids": app_id, "cc": "br", "l": "english"})
        if not isinstance(corpo, dict) or str(app_id) not in corpo:
            raise RespostaInvalida(f"appdetails sem a chave {app_id}")
        return corpo[str(app_id)]

    def paginas_reviews(
        self,
        app_id: int,
        idioma: str = "brazilian",
        por_pagina: int = 100,
        max_paginas: int = 25,
        parar_antes_de_ts: int | None = None,
        resultado: ResultadoPaginacao | None = None,
    ) -> Iterator[PaginaReviews]:
        """Itera as paginas de reviews, da mais nova para a mais antiga.

        Para quando: a pagina vem vazia; o cursor se repete ou falta (a API
        devolve o mesmo cursor no fim); a review mais antiga da pagina e anterior
        ao watermark; ou atinge max_paginas.
        """
        resultado = resultado or ResultadoPaginacao()
        cursor = "*"
        vistos: set[str] = set()
        url = URL_REVIEWS.format(app_id=app_id)

        for numero in range(1, max_paginas + 1):
            corpo = self.http.get_json(url, params={
                "json": 1,
                "filter": "recent",
                "language": idioma,
                "review_type": "all",
                "purchase_type": "all",
                "num_per_page": por_pagina,
                "cursor": cursor,  # requests faz o percent-encoding do cursor
            })
            if not isinstance(corpo, dict) or corpo.get("success") != 1:
                raise RespostaInvalida(f"appreviews {app_id}: success={corpo.get('success') if isinstance(corpo, dict) else corpo!r}")

            reviews = corpo.get("reviews") or []
            if not reviews:
                resultado.motivo_parada = "pagina vazia"
                return

            resultado.paginas += 1
            resultado.reviews += len(reviews)
            yield PaginaReviews(numero, cursor, reviews, corpo.get("query_summary") or {})

            proximo = corpo.get("cursor")
            vistos.add(cursor)
            if parar_antes_de_ts is not None:
                mais_antiga = min(int(r.get("timestamp_created") or 0) for r in reviews)
                if mais_antiga < parar_antes_de_ts:
                    resultado.motivo_parada = "watermark alcancado"
                    return
            if not proximo or proximo in vistos:
                resultado.motivo_parada = "cursor repetido ou ausente"
                return
            # Uma pagina com menos de por_pagina reviews NAO encerra a coleta: a Steam
            # filtra reviews depois de paginar, entao paginas do meio podem vir incompletas.
            cursor = proximo

        resultado.motivo_parada = f"limite de {max_paginas} paginas"
