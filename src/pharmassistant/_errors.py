"""Erreurs du client. Toutes héritent de PharmAssistantError et portent `aide`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, NamedTuple


class CodeErreur(NamedTuple):
    status: int | None
    sens: str
    aide: str
    decompte: bool


class PharmAssistantError(Exception):
    """Erreur du client PharmAssistant.

    Attributs : `message`, `code` (code machine stable), `status` (HTTP, None hors
    API), `request_id` (req_…, à joindre à toute demande de support), `details`
    (validation champ par champ sur les 422), `aide` (que faire).
    """

    def __init__(self, message: str, *, code: str | None = None,
                 status: int | None = None, request_id: str | None = None,
                 details: list[Any] | None = None, aide: str | None = None,
                 headers: Mapping[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.request_id = request_id
        self.details = details
        self.headers: dict[str, str] = dict(headers or {})
        connu = CODES.get(code or "")
        self.aide = aide if aide is not None else (connu.aide if connu else None)

    def __str__(self) -> str:
        tete = f"{self.code}: {self.message}" if self.code else self.message
        if self.status:
            tete = f"[{self.status}] {tete}"
        lignes = [tete]
        if self.aide:
            lignes.append(f"Aide : {self.aide}")
        if self.request_id:
            lignes.append(f"Requête : {self.request_id}")
        return "\n".join(lignes)


class ConfigurationError(PharmAssistantError, ValueError):
    """Client mal configuré : clé absente ou mal formée, URL invalide."""


class APIConnectionError(PharmAssistantError):
    """Le serveur n'a pas pu être joint, ou la réponse a été coupée."""


class APITimeoutError(APIConnectionError):
    """Délai dépassé (connexion ou lecture)."""


class APIStatusError(PharmAssistantError):
    """L'API a répondu par une erreur (statut HTTP ou événement error du flux)."""


class AuthenticationError(APIStatusError):
    """401 : clé absente, inconnue, révoquée ou expirée."""


class PermissionDeniedError(APIStatusError):
    """403 : portée manquante, pharmacie liée introuvable ou suspendue."""


class NotFoundError(APIStatusError):
    """404 : ressource inconnue pour cette clé."""


class ConversationNotFoundError(NotFoundError):
    """404 : conversation inconnue, supprimée ou purgée (90 jours d'inactivité)."""


class InvalidRequestError(APIStatusError):
    """422 : corps refusé ; `details` donne le motif champ par champ."""


class RateLimitError(APIStatusError):
    """429 rate_limited : rafale. `retry_after` (s) dit quand réessayer."""

    @property
    def retry_after(self) -> float | None:
        return _secondes(self.headers.get("retry-after"))


class QuotaExceededError(APIStatusError):
    """429 : plafond journalier, mensuel ou Détaillé atteint. Ne pas réessayer
    avant `reset_at` (minuit ou 1er du mois, heure de Paris)."""

    @property
    def reset_at(self) -> datetime | None:
        brut = self.headers.get("x-ratelimit-reset")
        if not brut or not brut.strip().isdigit():
            return None
        return datetime.fromtimestamp(int(brut), tz=timezone.utc)


class ServerError(APIStatusError):
    """5xx : échec côté serveur. La requête n'est pas décomptée."""


_A_REESSAYER_PLUS_TARD = ("Réessayez ; la requête n'est pas décomptée. Si l'erreur persiste, "
                          "écrivez à contact@pharmassistant.fr avec l'identifiant de requête.")

CODES: dict[str, CodeErreur] = {
    "missing_api_key": CodeErreur(
        401, "Aucune clé d'API n'a été envoyée.",
        "Passez api_key=\"pa_…\" au client ou définissez PHARMASSISTANT_API_KEY.", False),
    "invalid_api_key": CodeErreur(
        401, "Clé d'API inconnue ou mal formée.",
        "Vérifiez la clé copiée depuis le portail (elle commence par pa_). Une clé perdue "
        "ne se retrouve pas : régénérez-la depuis le portail.", False),
    "revoked_api_key": CodeErreur(
        401, "La clé a été révoquée.",
        "Générez une nouvelle clé depuis le portail, ou écrivez à contact@pharmassistant.fr.",
        False),
    "expired_api_key": CodeErreur(
        401, "La clé a dépassé sa date de péremption.",
        "Repoussez la péremption ou générez une nouvelle clé depuis le portail.", False),
    "pharmacy_not_found": CodeErreur(
        403, "La pharmacie liée à la clé est introuvable.",
        "Écrivez à contact@pharmassistant.fr avec l'identifiant de requête.", False),
    "pharmacy_suspended": CodeErreur(
        403, "La pharmacie liée à la clé est suspendue.",
        "Vérifiez l'abonnement de la pharmacie, ou écrivez à contact@pharmassistant.fr.", False),
    "scope_denied": CodeErreur(
        403, "La clé n'a pas la portée demandée (ask:detailed pour mode=\"detailed\").",
        "Posez la question en mode standard, ou demandez la portée ask:detailed à "
        "contact@pharmassistant.fr.", False),
    "conversation_not_found": CodeErreur(
        404, "Conversation inconnue pour cette clé : id erroné, supprimée, ou purgée après "
             "90 jours d'inactivité.",
        "Ouvrez une nouvelle conversation (store=True). Requête non décomptée.", False),
    "not_found": CodeErreur(
        404, "Adresse inconnue de l'API.",
        "Vérifiez base_url (défaut https://api.pharmassistant.fr).", False),
    "invalid_request": CodeErreur(
        422, "Requête refusée par la validation (question vide ou trop longue, history "
             "mêlé à store ou conversation_id…).",
        "Lisez error.details : chaque entrée nomme le champ fautif et la règle enfreinte.",
        False),
    "rate_limited": CodeErreur(
        429, "Trop de requêtes rapprochées sur la clé (anti-rafale par minute).",
        "Le client réessaie seul après le délai Retry-After (max_retries). Espacez les "
        "requêtes. Requête non décomptée.", False),
    "daily_limit_reached": CodeErreur(
        429, "Plafond journalier de la clé atteint.",
        "Attendez minuit (heure de Paris), ou relevez le plafond depuis le portail s'il "
        "n'est pas verrouillé. Requête non décomptée.", False),
    "monthly_limit_reached": CodeErreur(
        429, "Plafond mensuel de la clé atteint.",
        "Attendez le 1er du mois (heure de Paris), ou relevez le plafond depuis le portail "
        "s'il n'est pas verrouillé. Requête non décomptée.", False),
    "detailed_limit_reached": CodeErreur(
        429, "Sous-plafond journalier du mode Détaillé atteint.",
        "Reposez la question en mode standard, ou attendez minuit (heure de Paris). Requête "
        "non décomptée.", False),
    "internal_error": CodeErreur(500, "Erreur interne du serveur.", _A_REESSAYER_PLUS_TARD, False),
    "generation_failed": CodeErreur(
        502, "La rédaction de la réponse a échoué.", _A_REESSAYER_PLUS_TARD, False),
    "empty_response": CodeErreur(
        502, "Le moteur n'a produit aucune réponse exploitable.", _A_REESSAYER_PLUS_TARD, False),
    "connection_error": CodeErreur(
        None, "Le serveur n'a pas pu être joint (réseau, DNS, pare-feu, proxy).",
        "Vérifiez la connexion et base_url ; un proxy se règle par HTTPS_PROXY. Rien n'a été "
        "décompté.", False),
    "timeout": CodeErreur(
        None, "Délai dépassé avant la fin de la réponse.",
        "Augmentez timeout (le mode Détaillé peut dépasser deux minutes), ou passez par "
        "ask_stream. La requête a pu être décomptée : elle n'est pas réessayée seule.", True),
    "stream_interrupted": CodeErreur(
        None, "Le flux s'est arrêté avant l'événement done.",
        "Reposez la question. La requête a pu être décomptée.", True),
}

_PAR_STATUT: dict[int, type[APIStatusError]] = {
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: InvalidRequestError,
}

_PAR_CODE: dict[str, type[APIStatusError]] = {
    "conversation_not_found": ConversationNotFoundError,
    "rate_limited": RateLimitError,
    "daily_limit_reached": QuotaExceededError,
    "monthly_limit_reached": QuotaExceededError,
    "detailed_limit_reached": QuotaExceededError,
}


def classe_de(status: int | None, code: str | None) -> type[APIStatusError]:
    if code in _PAR_CODE:
        return _PAR_CODE[code]
    if status is None and code in CODES:
        status = CODES[code].status
    if status is None:
        return APIStatusError
    if status in _PAR_STATUT:
        return _PAR_STATUT[status]
    if status == 429:
        return RateLimitError
    if status >= 500:
        return ServerError
    return APIStatusError


def erreur_d_api(status: int | None, corps: Any, *, headers: Mapping[str, str] | None = None,
                 request_id: str | None = None, brut: str = "") -> APIStatusError:
    """Erreur typée depuis l'enveloppe {"error": {code, message, details}}."""
    info = corps.get("error") if isinstance(corps, dict) else None
    info = info if isinstance(info, dict) else {}
    code = info.get("code") or (f"http_{status}" if status else "api_error")
    message = info.get("message") or (brut.strip()[:300] if brut.strip() else
                                      f"Réponse HTTP {status} sans enveloppe d'erreur.")
    status = status if status is not None else (CODES[code].status if code in CODES else None)
    return classe_de(status, code)(
        message, code=code, status=status, request_id=request_id,
        details=info.get("details"), headers={k.lower(): v for k, v in (headers or {}).items()})


def _secondes(valeur: str | None) -> float | None:
    try:
        return max(0.0, float(valeur)) if valeur is not None else None
    except ValueError:
        return None
