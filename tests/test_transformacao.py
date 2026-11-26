from datetime import date
from decimal import Decimal

from src.ingestion.raw_store import hash_payload
from src.warehouse.loader import _parse_data_lancamento, transformar_detalhes


def test_hash_do_payload_e_estavel_e_ignora_ordem_das_chaves():
    assert hash_payload({"a": 1, "b": [1, 2]}) == hash_payload({"b": [1, 2], "a": 1})
    assert hash_payload({"a": 1}) != hash_payload({"a": 2})


def test_datas_de_lancamento_da_steam():
    assert _parse_data_lancamento("26 Feb, 2016") == date(2016, 2, 26)
    assert _parse_data_lancamento("Feb 26, 2016") == date(2016, 2, 26)
    assert _parse_data_lancamento("Coming soon") is None
    assert _parse_data_lancamento(None) is None


def test_desaninhamento_de_appdetails():
    objeto = {"success": True, "data": {
        "name": "Stardew Valley", "type": "game", "is_free": False,
        "developers": ["ConcernedApe"], "publishers": ["ConcernedApe"],
        "genres": [{"id": "23", "description": "Indie"}, {"id": "28", "description": "Simulation"}],
        "price_overview": {"currency": "BRL", "initial": 2499, "final": 2499},
        "release_date": {"coming_soon": False, "date": "26 Feb, 2016"},
        "short_description": " Uma fazenda. ",
    }}
    linha = transformar_detalhes(413150, objeto)
    assert linha[0] == 413150 and linha[1] == "Stardew Valley"
    assert linha[5] == "Indie" and linha[6] == "Indie, Simulacao"
    assert linha[8] == Decimal("24.99") and linha[9] == date(2016, 2, 26) and linha[10] == 2016
    assert linha[11] == "Uma fazenda."


def test_jogo_sem_detalhes_vira_placeholder():
    linha = transformar_detalhes(999, {"success": False})
    assert linha[0] == 999 and linha[1] == "App 999" and all(v is None for v in linha[2:])
