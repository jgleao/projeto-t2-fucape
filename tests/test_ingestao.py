"""Resiliencia da ingestao: backoff, Retry-After, erros permanentes e paginacao por cursor."""

import pytest
import requests

from src.ingestion.http_client import (ClienteHttpResiliente, ErroHttpPermanente,
                                       RetentativasEsgotadas)
from src.ingestion.steam_api import ResultadoPaginacao, SteamApi


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, headers=None, json_invalido=False):
        self.status_code = status
        self._corpo = corpo
        self.headers = headers or {}
        self._json_invalido = json_invalido

    def json(self):
        if self._json_invalido:
            raise ValueError("nao e json")
        return self._corpo


class SessaoFalsa:
    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.headers = {}
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append(params)
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _cliente(roteiro, **kw):
    esperas = []
    cliente = ClienteHttpResiliente(sessao=SessaoFalsa(roteiro), dormir=esperas.append,
                                    aleatorio=lambda: 0.5, intervalo_min_s=0, **kw)
    return cliente, esperas


def test_429_e_503_sao_retentados_com_backoff_exponencial():
    cliente, esperas = _cliente([RespostaFalsa(429), RespostaFalsa(503), RespostaFalsa(502),
                                 RespostaFalsa(200, {"ok": 1})], base_s=1.0)
    assert cliente.get_json("http://x") == {"ok": 1}
    # equal jitter com aleatorio=0.5: teto/2 + 0.5*teto/2 = 0.75*teto; tetos 1, 2, 4
    assert esperas == [0.75, 1.5, 3.0]
    assert cliente.stats.retentativas == 3 and cliente.stats.respostas_429 == 1


def test_retry_after_tem_prioridade_quando_maior():
    cliente, esperas = _cliente([RespostaFalsa(429, headers={"Retry-After": "30"}),
                                 RespostaFalsa(200, {"ok": 1})])
    cliente.get_json("http://x")
    assert esperas == [30.0]


def test_espera_respeita_teto_maximo():
    cliente, _ = _cliente([], base_s=1.0, max_espera_s=10.0)
    assert all(cliente.calcular_espera(t) <= 10.0 for t in range(20))
    assert cliente.calcular_espera(10) >= 5.0   # equal jitter nunca fica abaixo de teto/2


def test_erros_de_rede_e_json_invalido_sao_retentados():
    cliente, esperas = _cliente([requests.ConnectionError(), requests.Timeout(),
                                 RespostaFalsa(200, json_invalido=True), RespostaFalsa(200, [1])])
    assert cliente.get_json("http://x") == [1]
    assert len(esperas) == 3 and cliente.stats.erros_rede == 2


def test_erro_permanente_nao_e_retentado():
    cliente, esperas = _cliente([RespostaFalsa(404)])
    with pytest.raises(ErroHttpPermanente):
        cliente.get_json("http://x")
    assert esperas == []


def test_retentativas_esgotadas():
    cliente, esperas = _cliente([RespostaFalsa(500)] * 4, max_retentativas=3)
    with pytest.raises(RetentativasEsgotadas):
        cliente.get_json("http://x")
    assert len(esperas) == 3


class HttpFalso:
    """Simula a API de reviews: cada cursor aponta para uma pagina."""

    def __init__(self, paginas):
        self.paginas = paginas
        self.cursores = []

    def get_json(self, url, params=None):
        self.cursores.append(params["cursor"])
        return self.paginas[params["cursor"]]


def _review(rid, ts):
    return {"recommendationid": str(rid), "timestamp_created": ts, "review": "ok"}


def test_paginacao_por_cursor_ate_cursor_repetido():
    paginas = {
        "*": {"success": 1, "cursor": "A", "reviews": [_review(i, 1000 - i) for i in range(2)]},
        "A": {"success": 1, "cursor": "B", "reviews": [_review(i, 900 - i) for i in range(2, 4)]},
        "B": {"success": 1, "cursor": "B", "reviews": [_review(i, 800 - i) for i in range(4, 6)]},
    }
    http = HttpFalso(paginas)
    res = ResultadoPaginacao()
    lidas = list(SteamApi(http).paginas_reviews(1, por_pagina=2, max_paginas=10, resultado=res))
    assert [p.cursor for p in lidas] == ["*", "A", "B"]
    assert res.reviews == 6 and res.motivo_parada == "cursor repetido ou ausente"


def test_paginacao_para_no_watermark():
    paginas = {
        "*": {"success": 1, "cursor": "A", "reviews": [_review(1, 500), _review(2, 400)]},
        "A": {"success": 1, "cursor": "B", "reviews": [_review(3, 300), _review(4, 100)]},
        "B": {"success": 1, "cursor": "C", "reviews": [_review(5, 50), _review(6, 40)]},
    }
    res = ResultadoPaginacao()
    lidas = list(SteamApi(HttpFalso(paginas)).paginas_reviews(1, por_pagina=2, parar_antes_de_ts=200,
                                                               resultado=res))
    assert len(lidas) == 2 and res.motivo_parada == "watermark alcancado"


def test_paginacao_respeita_limite_e_pagina_vazia():
    paginas = {"*": {"success": 1, "cursor": "A", "reviews": [_review(1, 5), _review(2, 4)]},
               "A": {"success": 1, "cursor": "B", "reviews": []}}
    res = ResultadoPaginacao()
    assert len(list(SteamApi(HttpFalso(paginas)).paginas_reviews(1, por_pagina=2, resultado=res))) == 1
    assert res.motivo_parada == "pagina vazia"
    res = ResultadoPaginacao()
    assert len(list(SteamApi(HttpFalso(paginas)).paginas_reviews(1, por_pagina=2, max_paginas=1,
                                                                  resultado=res))) == 1
    assert res.motivo_parada == "limite de 1 paginas"
