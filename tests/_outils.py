import json
from typing import Any, Callable, Optional, Union

import httpx

from pharmassistant import AsyncPharmAssistant, PharmAssistant

CLE = "pa_test_0123456789"
URL = "https://api.test"


def reponse_ask(**champs: Any) -> dict[str, Any]:
    base = {
        "id": "req_0001", "object": "pharmassistant.answer",
        "created_at": "2026-11-24T10:42:07+01:00", "status": "ok", "mode": "standard",
        "question": "Amoxicilline et allaitement ?", "title": "Amoxicilline et allaitement",
        "answer": "Compatible.[S1] Surveiller le nourrisson.[S1][S2]",
        "key_points": [{"polarity": "positive", "text": "Compatible"},
                       {"polarity": "negative", "text": "Pas de surdosage"}],
        "patient_advice": "Vous pouvez allaiter.", "associated_sale": "Probiotique ?",
        "clarification": None, "suggestions": ["Et pendant la grossesse ?"],
        "tools_used": ["lecrat_search"],
        "sources": {"lecrat_search": [{"title": "CRAT : amoxicilline", "url": "https://crat/a"}],
                    "lactmed_search": [{"title": "CRAT : amoxicilline", "url": "https://crat/a"},
                                       {"title": "LactMed", "url": None}]},
        "citations": "list",
        "references": [{"n": 1, "tool": "lecrat_search", "title": "CRAT", "url": "https://crat/a",
                        "empty": False, "query": None},
                       {"n": 2, "tool": "lactmed_search", "title": "", "url": None,
                        "empty": True, "query": "amoxicillin"}],
        "passages": [{"index": 0, "n": 1, "quote": "passe peu dans le lait", "before": "",
                      "after": "", "record": None, "record_title": None},
                     {"index": 2, "n": 2, "quote": None, "before": None, "after": None,
                      "record": [{"label": "Dose", "value": "faible", "cited": True}],
                      "record_title": "Fiche"}],
        "conversation_id": None,
        "usage": {"elapsed_ms": 4200, "daily_requests_used": 12, "daily_requests_limit": 100},
    }
    base.update(champs)
    return base


def clarification(**champs: Any) -> dict[str, Any]:
    return reponse_ask(status="clarification_needed", answer=None, title=None,
                       question="Collyre pour l'oeille ?",
                       clarification={"word": "oeille", "corrections": ["œil", "oreille"],
                                      "message": "Vouliez-vous dire :"}, **champs)


def erreur(status: int, code: str, message: str = "Refus.", **entetes: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message}},
                          headers={"x-request-id": "req_err", **entetes})


def sse(*evenements: Any) -> bytes:
    morceaux = []
    for evenement, donnees in evenements:
        morceaux.append(f"event: {evenement}\ndata: {json.dumps(donnees, ensure_ascii=False)}\n\n")
    return "".join(morceaux).encode("utf-8")


def flux_complet(reponse: Optional[dict[str, Any]] = None) -> bytes:
    reponse = reponse or reponse_ask()
    return sse(("start", {"id": "req_0001", "object": "pharmassistant.answer.stream"}),
               ("status", {"state": "routing"}),
               ("chunk", {"text": "Compa"}), ("chunk", {"text": "tible."}),
               ("done", reponse))


Gestionnaire = Union[Callable[[httpx.Request], httpx.Response], list[Any]]


class Serveur:
    """Faux serveur : rejoue des réponses dans l'ordre et garde les requêtes."""

    def __init__(self, *reponses: Any) -> None:
        self.reponses = list(reponses)
        self.requetes: list[httpx.Request] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        suivante = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        if isinstance(suivante, BaseException):
            raise suivante
        if callable(suivante) and not isinstance(suivante, httpx.Response):
            return suivante(requete)
        if isinstance(suivante, httpx.Response):
            return httpx.Response(suivante.status_code, headers=suivante.headers,
                                  content=suivante.content)
        if isinstance(suivante, bytes):
            return httpx.Response(200, content=suivante,
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=suivante, headers={"x-request-id": "req_0001"})

    def corps(self, i: int = -1) -> dict[str, Any]:
        return json.loads(self.requetes[i].content or b"{}")


def client(serveur: Serveur, **options: Any) -> PharmAssistant:
    c = PharmAssistant(CLE, base_url=URL,
                       http_client=httpx.Client(transport=httpx.MockTransport(serveur)), **options)
    c.attentes = []  # type: ignore[attr-defined]
    c._sleep = c.attentes.append  # type: ignore[attr-defined]
    return c


def client_async(serveur: Serveur, **options: Any) -> AsyncPharmAssistant:
    c = AsyncPharmAssistant(CLE, base_url=URL,
                            http_client=httpx.AsyncClient(transport=httpx.MockTransport(serveur)),
                            **options)
    c.attentes = []  # type: ignore[attr-defined]

    async def dormir(delai: float) -> None:
        c.attentes.append(delai)  # type: ignore[attr-defined]

    c._sleep = dormir  # type: ignore[assignment]
    return c
