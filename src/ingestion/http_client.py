"""Cliente HTTP resiliente: limite de taxa, retentativas e exponential backoff com jitter.

Politica:
* Retentavel: HTTP 429 (rate limit), 500/502/503/504, timeout, queda de conexao
  e corpo que nao e JSON valido (a Steam as vezes devolve HTML de erro com 200).
* Permanente (falha na hora, sem retentar): demais 4xx, como 400/403/404.
* Espera entre tentativas: "equal jitter" -> teto = min(max, base * 2^tentativa);
  espera = teto/2 + aleatorio(0, teto/2). Se a resposta trouxer Retry-After,
  a espera nunca e menor do que ele.
* Polidez: intervalo minimo entre requisicoes (limitador simples por cliente).
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

STATUS_RETENTAVEIS = frozenset({429, 500, 502, 503, 504})


class ErroHttpPermanente(Exception):
    """Erro que nao adianta retentar (ex.: 404)."""


class RetentativasEsgotadas(Exception):
    """Todas as tentativas falharam."""


@dataclass
class EstatisticasHttp:
    requisicoes: int = 0
    retentativas: int = 0
    respostas_429: int = 0
    erros_rede: int = 0
    espera_total_s: float = 0.0
    por_status: dict[int, int] = field(default_factory=dict)


class LimitadorTaxa:
    """Garante um intervalo minimo entre requisicoes consecutivas."""

    def __init__(self, intervalo_min_s: float, relogio: Callable[[], float] = time.monotonic,
                 dormir: Callable[[float], None] = time.sleep):
        self.intervalo_min_s = intervalo_min_s
        self._relogio = relogio
        self._dormir = dormir
        self._ultima: float | None = None

    def aguardar(self) -> None:
        agora = self._relogio()
        if self._ultima is not None:
            falta = self.intervalo_min_s - (agora - self._ultima)
            if falta > 0:
                self._dormir(falta)
                agora = self._relogio()
        self._ultima = agora


def _ler_retry_after(resp: requests.Response) -> float:
    valor = resp.headers.get("Retry-After")
    if not valor:
        return 0.0
    try:
        return max(0.0, float(valor))
    except ValueError:
        try:
            alvo = parsedate_to_datetime(valor)
            return max(0.0, alvo.timestamp() - time.time())
        except (TypeError, ValueError):
            return 0.0


class ClienteHttpResiliente:
    def __init__(
        self,
        base_s: float = 1.0,
        max_espera_s: float = 60.0,
        max_retentativas: int = 6,
        timeout: tuple[float, float] = (5.0, 30.0),
        intervalo_min_s: float = 1.0,
        sessao: requests.Session | None = None,
        dormir: Callable[[float], None] = time.sleep,
        aleatorio: Callable[[], float] = random.random,
    ):
        self.base_s = base_s
        self.max_espera_s = max_espera_s
        self.max_retentativas = max_retentativas
        self.timeout = timeout
        self.sessao = sessao or requests.Session()
        self.sessao.headers.setdefault("User-Agent", "t2-fucape-pipeline-academico/1.0")
        self._dormir = dormir
        self._aleatorio = aleatorio
        self._limitador = LimitadorTaxa(intervalo_min_s, dormir=dormir)
        self.stats = EstatisticasHttp()

    def calcular_espera(self, tentativa: int) -> float:
        """Exponential backoff com equal jitter (tentativa comeca em 0)."""
        teto = min(self.max_espera_s, self.base_s * (2 ** tentativa))
        return teto / 2 + self._aleatorio() * (teto / 2)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        ultimo_erro: str = ""
        for tentativa in range(self.max_retentativas + 1):
            self._limitador.aguardar()
            self.stats.requisicoes += 1
            espera_minima = 0.0
            try:
                resp = self.sessao.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                self.stats.erros_rede += 1
                ultimo_erro = f"erro de rede: {exc.__class__.__name__}"
            else:
                status = resp.status_code
                self.stats.por_status[status] = self.stats.por_status.get(status, 0) + 1
                if status == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        ultimo_erro = "HTTP 200 com corpo que nao e JSON"
                elif status in STATUS_RETENTAVEIS:
                    if status == 429:
                        self.stats.respostas_429 += 1
                    espera_minima = _ler_retry_after(resp)
                    ultimo_erro = f"HTTP {status}"
                else:
                    raise ErroHttpPermanente(f"HTTP {status} em {url}")

            if tentativa == self.max_retentativas:
                break
            espera = max(espera_minima, self.calcular_espera(tentativa))
            self.stats.retentativas += 1
            self.stats.espera_total_s += espera
            log.warning("%s em %s; tentativa %d/%d, aguardando %.1fs",
                        ultimo_erro, url, tentativa + 1, self.max_retentativas, espera)
            self._dormir(espera)

        raise RetentativasEsgotadas(
            f"{url}: {self.max_retentativas + 1} tentativas falharam ({ultimo_erro})")
