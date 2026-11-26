"""Configuracao central, lida de variaveis de ambiente com valores padrao."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Jogos populares com grande volume de reviews em portugues (app_id da Steam).
JOGOS_PADRAO: dict[int, str] = {
    730: "Counter-Strike 2",
    570: "Dota 2",
    271590: "Grand Theft Auto V",
    1174180: "Red Dead Redemption 2",
    292030: "The Witcher 3: Wild Hunt",
    1091500: "Cyberpunk 2077",
    1245620: "ELDEN RING",
    1086940: "Baldur's Gate 3",
    413150: "Stardew Valley",
    105600: "Terraria",
    367520: "Hollow Knight",
    1145360: "Hades",
    227300: "Euro Truck Simulator 2",
    252490: "Rust",
    381210: "Dead by Daylight",
    990080: "Hogwarts Legacy",
}


def _env_int(nome: str, padrao: int) -> int:
    valor = os.getenv(nome, "").strip()
    return int(valor) if valor else padrao


def app_ids_configurados() -> list[int]:
    """Lista de jogos a coletar: STEAM_APP_IDS (csv) ou a lista padrao."""
    bruto = os.getenv("STEAM_APP_IDS", "").strip()
    if not bruto:
        return list(JOGOS_PADRAO)
    return [int(parte) for parte in bruto.split(",") if parte.strip()]


@dataclass(frozen=True)
class ConfigColeta:
    idioma: str = os.getenv("STEAM_IDIOMA", "brazilian")
    reviews_por_pagina: int = 100  # maximo aceito pela API
    max_paginas_inicial: int = _env_int("STEAM_MAX_PAGINAS_INICIAL", 25)
    max_paginas_incremental: int = _env_int("STEAM_MAX_PAGINAS_INCREMENTAL", 5)
    # Sobreposicao da janela incremental: reprocessa 2 dias antes do watermark
    # para capturar edicoes recentes. Como a carga e um upsert, isso nao duplica.
    sobreposicao_segundos: int = 2 * 24 * 3600


@dataclass(frozen=True)
class ConfigBanco:
    host: str = os.getenv("DW_HOST", "localhost")
    port: int = _env_int("DW_PORT", 5433)
    dbname: str = os.getenv("DW_DB", "dw")
    user: str = os.getenv("DW_USER", "dw")
    password: str = os.getenv("DW_PASSWORD", "dw")

    def dsn(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }
