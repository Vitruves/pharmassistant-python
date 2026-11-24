"""Socle commun aux clients synchrone et asynchrone : configuration, corps des
requêtes, politique de réessai, lecture des réponses."""

from __future__ import annotations

import logging
import os
import platform
import random
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Union

import httpx

from ._errors import (
    APIConnectionError,
    APITimeoutError,
    ConfigurationError,
    PharmAssistantError,
    erreur_d_api,
)
from ._models import RateLimit
from ._version import __version__

DEFAULT_BASE_URL = "https://api.pharmassistant.fr"
DEFAULT_TIMEOUT = httpx.Timeout(300.0, connect=10.0)
DEFAULT_MAX_RETRIES = 2
ENV_API_KEY = "PHARMASSISTANT_API_KEY"
ENV_BASE_URL = "PHARMASSISTANT_API_URL"
ENV_LOG = "PHARMASSISTANT_LOG"
KEY_PREFIX = "pa_"
RETRY_AFTER_MAX = 60.0
BACKOFF_INITIAL = 0.5
BACKOFF_MAX = 8.0

MODES = ("standard", "detailed")
CITATIONS = ("list", "inline")

logger = logging.getLogger("pharmassistant")
logger.addHandler(logging.NullHandler())
NOT_GIVEN: Any = object()

HistoryInput = Iterable[Union[Mapping[str, Any], Sequence[str]]]
TimeoutInput = Union[float, httpx.Timeout, None]


def user_agent() -> str:
    return (f"pharmassistant-python/{__version__} (python {platform.python_version()}; "
            f"httpx {httpx.__version__})")


def masquer(cle: str | None) -> str:
    if not cle:
        return "(aucune)"
    return cle[:7] + "…" if len(cle) > 10 else "pa_…"


def configurer_journal() -> None:
    niveau = os.environ.get(ENV_LOG, "").strip().upper()
    deja = any(not isinstance(h, logging.NullHandler) for h in logger.handlers)
    if niveau in ("DEBUG", "INFO", "WARNING") and not deja:
        gestionnaire = logging.StreamHandler()
        gestionnaire.setFormatter(logging.Formatter("[pharmassistant] %(levelname)s %(message)s"))
        logger.addHandler(gestionnaire)
        logger.setLevel(niveau)


def resoudre_cle(api_key: str | None) -> str:
    cle = (api_key if api_key is not None else os.environ.get(ENV_API_KEY, "")).strip()
    if not cle:
        raise ConfigurationError(
            "Clé d'API absente.", code="missing_api_key",
            aide=f"Passez api_key=\"pa_…\" au client ou définissez {ENV_API_KEY}. La clé se "
                 "retire sur le portail dont le lien vous a été envoyé par email.")
    if not cle.startswith(KEY_PREFIX):
        raise ConfigurationError(
            f"Clé d'API mal formée ({masquer(cle)}) : une clé commence par {KEY_PREFIX}.",
            code="invalid_api_key",
            aide="Copiez la clé entière depuis le portail, sans guillemets ni espaces.")
    return cle


def resoudre_url(base_url: str | None) -> str:
    url = (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip("/")
    if not url.startswith(("https://", "http://")):
        raise ConfigurationError(f"URL de base invalide : {url!r}.",
                                 aide="Exemple : https://api.pharmassistant.fr")
    return url


def resoudre_timeout(timeout: TimeoutInput) -> httpx.Timeout:
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, httpx.Timeout):
        return timeout
    return httpx.Timeout(float(timeout), connect=min(10.0, float(timeout)))


def normaliser_historique(history: HistoryInput | None) -> list[dict[str, str]]:
    tours: list[dict[str, str]] = []
    for tour in history or []:
        if isinstance(tour, Mapping):
            role, contenu = tour.get("role"), tour.get("content")
        else:
            role, contenu = tour
        if role not in ("user", "assistant"):
            raise ValueError(f"Rôle d'historique invalide : {role!r} (user ou assistant).")
        if not isinstance(contenu, str) or not contenu.strip():
            raise ValueError("Chaque tour d'historique porte un texte non vide.")
        tours.append({"role": role, "content": contenu})
    return tours


def corps_ask(question: str, *, mode: str = "standard", history: HistoryInput | None = None,
              conversation_id: str | None = None, store: bool = False,
              suggestions: bool = True, patient_advice: bool = True,
              associated_sale: bool = True,
              citations: str = "list", stream: bool = False) -> dict[str, Any]:
    """Corps de POST /v1/ask ; seuls les champs hors défaut sont envoyés."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("La question est vide.")
    if mode not in MODES:
        raise ValueError(f"mode={mode!r} : attendu {' ou '.join(MODES)}.")
    if citations not in CITATIONS:
        raise ValueError(f"citations={citations!r} : attendu {' ou '.join(CITATIONS)}.")
    tours = normaliser_historique(history)
    if tours and (conversation_id or store):
        raise ValueError("history est exclusif de conversation_id et de store : soit vous "
                         "portez l'historique, soit le serveur garde la conversation.")
    corps: dict[str, Any] = {"question": question}
    if mode != "standard":
        corps["mode"] = mode
    if tours:
        corps["history"] = tours
    if conversation_id:
        corps["conversation_id"] = conversation_id
    if store and not conversation_id:
        corps["store"] = True
    for champ, valeur in (("suggestions", suggestions), ("patient_advice", patient_advice),
                          ("associated_sale", associated_sale)):
        if not valeur:
            corps[champ] = False
    if citations != "list":
        corps["citations"] = citations
    if stream:
        corps["stream"] = True
    return corps


def delai_backoff(tentative: int) -> float:
    base = min(BACKOFF_MAX, BACKOFF_INITIAL * 2.0 ** tentative)
    return base * random.uniform(0.75, 1.0)


def delai_de_reessai(tentative: int, max_retries: int, methode: str, *,
                     status: int | None = None, code: str | None = None,
                     headers: Mapping[str, str] | None = None,
                     exc: BaseException | None = None) -> float | None:
    """Délai avant le prochain essai, ou None pour ne pas réessayer.

    Réessayés : connexion impossible (rien n'est parti), rafale (Retry-After),
    5xx (jamais décomptés). Jamais une lecture coupée sur POST : la requête a pu
    être décomptée.
    """
    if tentative >= max_retries:
        return None
    if exc is not None:
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
            return delai_backoff(tentative)
        if methode == "GET" and isinstance(exc, (httpx.ReadTimeout, httpx.ReadError,
                                                 httpx.RemoteProtocolError)):
            return delai_backoff(tentative)
        return None
    if status == 429:
        if code != "rate_limited":
            return None
        bas = {k.lower(): v for k, v in (headers or {}).items()}
        try:
            attente = float(bas.get("retry-after", ""))
        except ValueError:
            attente = delai_backoff(tentative)
        return min(RETRY_AFTER_MAX, max(0.0, attente))
    if status in (500, 502, 503, 504):
        return delai_backoff(tentative)
    return None


def erreur_reseau(exc: BaseException) -> PharmAssistantError:
    if isinstance(exc, httpx.TimeoutException) and not isinstance(exc, httpx.ConnectTimeout):
        return APITimeoutError(f"Délai dépassé : {exc}", code="timeout")
    return APIConnectionError(f"Connexion impossible : {exc}", code="connection_error")


def code_d_erreur(reponse: httpx.Response) -> str | None:
    try:
        corps = reponse.json()
    except ValueError:
        return None
    info = corps.get("error") if isinstance(corps, dict) else None
    return info.get("code") if isinstance(info, dict) else None


def lever_si_erreur(reponse: httpx.Response) -> None:
    if reponse.status_code < 400:
        return
    try:
        corps: Any = reponse.json()
    except ValueError:
        corps = None
    raise erreur_d_api(reponse.status_code, corps, headers=reponse.headers,
                       request_id=reponse.headers.get("x-request-id"), brut=reponse.text)


def lire_json(reponse: httpx.Response) -> tuple[Any, RateLimit | None]:
    lever_si_erreur(reponse)
    try:
        corps = reponse.json()
    except ValueError:
        raise APIConnectionError(
            f"Réponse illisible (HTTP {reponse.status_code}, {reponse.headers.get('content-type')}).",
            code="invalid_response", request_id=reponse.headers.get("x-request-id"),
            aide="Vérifiez base_url : un proxy ou un portail captif répond peut-être à la place "
                 "de l'API.") from None
    return corps, RateLimit.from_headers(reponse.headers)


class Options:
    """Réglages résolus d'un client, partagés par with_options()."""

    def __init__(self, api_key: str | None, base_url: str | None, timeout: TimeoutInput,
                 max_retries: int, default_headers: Mapping[str, str] | None) -> None:
        configurer_journal()
        self.api_key = resoudre_cle(api_key)
        self.base_url = resoudre_url(base_url)
        self.timeout = resoudre_timeout(timeout)
        if max_retries < 0:
            raise ValueError("max_retries doit être positif ou nul.")
        self.max_retries = max_retries
        self.default_headers = dict(default_headers or {})

    def entetes(self, *, auth: bool = True, flux: bool = False) -> dict[str, str]:
        entetes = {"User-Agent": user_agent(),
                   "Accept": "text/event-stream" if flux else "application/json"}
        entetes.update(self.default_headers)
        if auth:
            entetes["X-API-Key"] = self.api_key
        return entetes

    def derive(self, *, timeout: Any = NOT_GIVEN, max_retries: int | None = None,
               default_headers: Mapping[str, str] | None = None) -> Options:
        neuf = object.__new__(Options)
        neuf.__dict__.update(self.__dict__)
        if timeout is not NOT_GIVEN:
            neuf.timeout = resoudre_timeout(timeout)
        if max_retries is not None:
            if max_retries < 0:
                raise ValueError("max_retries doit être positif ou nul.")
            neuf.max_retries = max_retries
        if default_headers is not None:
            neuf.default_headers = {**self.default_headers, **default_headers}
        return neuf

