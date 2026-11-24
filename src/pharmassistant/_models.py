"""Objets renvoyés par l'API.

Chaque objet est un dict (le JSON reçu, tel quel) lisible aussi par attributs :
`reponse["answer"]` et `reponse.answer` donnent la même valeur.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, NamedTuple

_REPERE = re.compile(r"\[S(\d+)\]")
_REPERES_COLLES = re.compile(r"(?:\[S\d+\])+")


class APIObject(dict[str, Any]):
    """Objet JSON de l'API : dict, plus des attributs typés."""

    _imbriques: ClassVar[dict[str, Callable[[Any], Any]]] = {}

    def __init__(self, data: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(data or {}, **kwargs)
        for cle, conv in self._imbriques.items():
            valeur = dict.get(self, cle)
            if valeur is not None:
                self[cle] = conv(valeur)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict.__repr__(self)})"

    def to_dict(self) -> dict[str, Any]:
        """Copie en dict et listes simples, sérialisable telle quelle."""
        return json.loads(json.dumps(self, ensure_ascii=False))

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self, ensure_ascii=False, indent=indent)


def _liste(cls: Callable[[Any], Any]) -> Callable[[Any], list[Any]]:
    return lambda valeurs: [cls(v) for v in valeurs]


class SourceRef(APIObject):
    """Référence d'une base interrogée (citations="list")."""

    @property
    def title(self) -> str:
        return self.get("title", "")

    @property
    def url(self) -> str | None:
        return self.get("url")


class Reference(APIObject):
    """Source numérotée du registre (citations="inline") : [S3] ↔ n = 3."""

    @property
    def n(self) -> int:
        return self["n"]

    @property
    def tool(self) -> str:
        return self.get("tool", "")

    @property
    def title(self) -> str:
        return self.get("title", "")

    @property
    def url(self) -> str | None:
        return self.get("url")

    @property
    def empty(self) -> bool:
        """True : la base a été interrogée et n'a rien rendu."""
        return bool(self.get("empty", False))

    @property
    def query(self) -> str | None:
        return self.get("query")

    @property
    def marker(self) -> str:
        return f"[S{self.n}]"


class RecordLine(APIObject):
    """Ligne « libellé : valeur » d'une fiche de données."""

    @property
    def label(self) -> str:
        return self.get("label", "")

    @property
    def value(self) -> str:
        return self.get("value", "")

    @property
    def cited(self) -> bool:
        return bool(self.get("cited", False))


class Passage(APIObject):
    """Extrait de source qui porte la phrase d'un repère (citations="inline").

    Prose (`quote`, avec `before` et `after`) ou fiche de données (`record`)."""

    _imbriques = {"record": _liste(RecordLine)}

    @property
    def index(self) -> int:
        """Rang du repère dans answer, 0 pour le premier."""
        return self["index"]

    @property
    def n(self) -> int:
        return self["n"]

    @property
    def quote(self) -> str | None:
        return self.get("quote")

    @property
    def before(self) -> str | None:
        return self.get("before")

    @property
    def after(self) -> str | None:
        return self.get("after")

    @property
    def record(self) -> list[RecordLine] | None:
        return self.get("record")

    @property
    def record_title(self) -> str | None:
        return self.get("record_title")

    @property
    def is_record(self) -> bool:
        return self.get("record") is not None


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if unicodedata.category(c) != "Mn")


class Clarification(APIObject):
    """Mot ambigu qui bloque le routage, et ses corrections proposées."""

    @property
    def word(self) -> str:
        return self.get("word", "")

    @property
    def corrections(self) -> list[str]:
        return list(self.get("corrections") or [])

    @property
    def message(self) -> str:
        return self.get("message", "")

    def corrected_question(self, question: str, correction: str) -> str:
        """La question reformulée avec `correction` à la place du mot ambigu.

        Même règle que le chat : première occurrence sans égard à la casse, sinon
        mot à mot sans égard aux accents, sinon correction ajoutée entre parenthèses.
        """
        if not question.strip():
            return correction
        exact = re.compile(re.escape(self.word), re.IGNORECASE) if self.word else None
        if exact is not None and exact.search(question):
            return exact.sub(lambda _m: correction, question, count=1)
        cible = _sans_accents(self.word).lower()
        morceaux = re.split(r"(\s+)", question)
        for i, morceau in enumerate(morceaux):
            if cible and re.sub(r"[^a-zç]", "", _sans_accents(morceau).lower()) == cible:
                morceaux[i] = correction
                return "".join(morceaux)
        return f"{question} ({correction})"


class KeyPoint(APIObject):
    """Puce à polarité : positive = recommandé, negative = à éviter."""

    @property
    def polarity(self) -> str:
        return self.get("polarity", "")

    @property
    def text(self) -> str:
        return self.get("text", "")

    @property
    def is_positive(self) -> bool:
        return self.polarity == "positive"


class Usage(APIObject):
    @property
    def elapsed_ms(self) -> int:
        return self.get("elapsed_ms", 0)

    @property
    def daily_requests_used(self) -> int:
        return self.get("daily_requests_used", 0)

    @property
    def daily_requests_limit(self) -> int | None:
        """None : clé sans plafond journalier."""
        return self.get("daily_requests_limit")


class RateLimit(NamedTuple):
    """En-têtes X-RateLimit-* : plafond journalier, restant, remise à zéro."""

    limit: int
    remaining: int
    reset_at: datetime | None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> RateLimit | None:
        bas = {k.lower(): v for k, v in headers.items()}
        try:
            limite = int(bas["x-ratelimit-limit"])
            restant = int(bas["x-ratelimit-remaining"])
        except (KeyError, ValueError):
            return None
        reset = bas.get("x-ratelimit-reset", "")
        quand = (datetime.fromtimestamp(int(reset), tz=timezone.utc)
                 if reset.strip().isdigit() else None)
        return cls(limite, restant, quand)


class Citation(NamedTuple):
    """Un repère [Sn] de la réponse (rank : 0 pour le premier), avec sa référence
    et son extrait."""

    rank: int
    n: int
    reference: Reference | None
    passage: Passage | None
    start: int
    end: int


def _sources(valeur: Mapping[str, Any]) -> dict[str, list[SourceRef]]:
    return {base: [SourceRef(r) for r in refs] for base, refs in valeur.items()}


class Answer(APIObject):
    """Réponse de POST /v1/ask (objet pharmassistant.answer).

    `rate_limit` (hors JSON) donne les en-têtes de quota de la réponse HTTP.
    """

    _imbriques = {
        "key_points": _liste(KeyPoint),
        "clarification": Clarification,
        "sources": _sources,
        "references": _liste(Reference),
        "passages": _liste(Passage),
        "usage": Usage,
    }

    def __init__(self, data: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(data, **kwargs)
        self.rate_limit: RateLimit | None = None

    @property
    def id(self) -> str:
        """Identifiant de requête (req_…), à joindre à toute demande de support."""
        return self.get("id", "")

    @property
    def object(self) -> str:
        return self.get("object", "pharmassistant.answer")

    @property
    def created_at(self) -> str:
        return self.get("created_at", "")

    @property
    def status(self) -> str:
        """ok, ou clarification_needed (answer vaut alors None)."""
        return self.get("status", "")

    @property
    def mode(self) -> str:
        return self.get("mode", "standard")

    @property
    def question(self) -> str:
        return self.get("question", "")

    @property
    def title(self) -> str | None:
        return self.get("title")

    @property
    def answer(self) -> str | None:
        """Réponse en markdown, sans marqueur interne."""
        return self.get("answer")

    @property
    def key_points(self) -> list[KeyPoint]:
        return self.get("key_points") or []

    @property
    def patient_advice(self) -> str | None:
        """Discours prêt à tenir au patient (« Au comptoir »)."""
        return self.get("patient_advice")

    @property
    def associated_sale(self) -> str | None:
        return self.get("associated_sale")

    @property
    def clarification(self) -> Clarification | None:
        return self.get("clarification")

    @property
    def suggestions(self) -> list[str]:
        return self.get("suggestions") or []

    @property
    def tools_used(self) -> list[str]:
        return self.get("tools_used") or []

    @property
    def sources(self) -> dict[str, list[SourceRef]]:
        return self.get("sources") or {}

    @property
    def citations(self) -> str:
        return self.get("citations", "list")

    @property
    def references(self) -> list[Reference]:
        return self.get("references") or []

    @property
    def passages(self) -> list[Passage]:
        return self.get("passages") or []

    @property
    def conversation_id(self) -> str | None:
        return self.get("conversation_id")

    @property
    def usage(self) -> Usage:
        return self.get("usage") or Usage()

    @property
    def needs_clarification(self) -> bool:
        return self.status == "clarification_needed"

    @property
    def request_id(self) -> str:
        return self.id

    def reference(self, n: int) -> Reference | None:
        """La référence numéro n du registre, ou None."""
        return next((r for r in self.references if r.n == n), None)

    def iter_citations(self) -> Iterator[Citation]:
        """Les repères [Sn] de la réponse, dans l'ordre du texte."""
        passages = {p.index: p for p in self.passages}
        for index, trouve in enumerate(_REPERE.finditer(self.answer or "")):
            n = int(trouve.group(1))
            yield Citation(index, n, self.reference(n), passages.get(index),
                           trouve.start(), trouve.end())

    def answer_without_markers(self) -> str | None:
        """La réponse sans ses repères [Sn]."""
        if self.answer is None:
            return None
        return _REPERES_COLLES.sub("", self.answer)

    def all_sources(self) -> list[SourceRef]:
        """Toutes les références, toutes bases confondues, sans doublon."""
        vues, sortie = set(), []
        for refs in self.sources.values():
            for ref in refs:
                cle = ref.url or ref.title
                if cle not in vues:
                    vues.add(cle)
                    sortie.append(ref)
        return sortie


class KeyInfo(APIObject):
    """État de la clé (GET /v1/me) : plafonds, portées, consommation."""

    @property
    def id(self) -> str:
        return self.get("id", "")

    @property
    def name(self) -> str:
        return self.get("name", "")

    @property
    def key_hint(self) -> str:
        return self.get("key_hint", "")

    @property
    def pharmacy_slug(self) -> str | None:
        return self.get("pharmacy_slug")

    @property
    def daily_limit(self) -> int | None:
        return self.get("daily_limit")

    @property
    def monthly_limit(self) -> int | None:
        return self.get("monthly_limit")

    @property
    def daily_detailed_limit(self) -> int | None:
        return self.get("daily_detailed_limit")

    @property
    def limits_locked(self) -> bool:
        return bool(self.get("limits_locked", False))

    @property
    def scopes(self) -> list[str] | None:
        """None : toutes les portées."""
        return self.get("scopes")

    @property
    def active(self) -> bool:
        return bool(self.get("active", False))

    @property
    def expires_at(self) -> str | None:
        return self.get("expires_at")

    @property
    def created_at(self) -> str:
        return self.get("created_at", "")

    @property
    def last_used_at(self) -> str | None:
        return self.get("last_used_at")

    @property
    def daily_requests_used(self) -> int:
        return self.get("daily_requests_used", 0)

    @property
    def daily_detailed_used(self) -> int:
        return self.get("daily_detailed_used", 0)

    @property
    def month_requests_used(self) -> int:
        return self.get("month_requests_used", 0)

    @property
    def daily_remaining(self) -> int | None:
        """None : pas de plafond journalier."""
        if self.daily_limit is None:
            return None
        return max(0, self.daily_limit - self.daily_requests_used)

    @property
    def monthly_remaining(self) -> int | None:
        if self.monthly_limit is None:
            return None
        return max(0, self.monthly_limit - self.month_requests_used)

    def has_scope(self, scope: str) -> bool:
        return self.scopes is None or scope in self.scopes


class ConversationSummary(APIObject):
    @property
    def id(self) -> str:
        return self.get("id", "")

    @property
    def title(self) -> str | None:
        return self.get("title")

    @property
    def message_count(self) -> int:
        return self.get("message_count", 0)

    @property
    def created_at(self) -> str | None:
        return self.get("created_at")

    @property
    def updated_at(self) -> str | None:
        """Dernière activité ; purge après 90 jours sans activité."""
        return self.get("updated_at")


class ConversationMessage(APIObject):
    @property
    def role(self) -> str:
        return self.get("role", "")

    @property
    def content(self) -> str:
        return self.get("content", "")

    @property
    def created_at(self) -> str | None:
        return self.get("created_at")


class ConversationDetail(APIObject):
    _imbriques = {"messages": _liste(ConversationMessage)}

    @property
    def id(self) -> str:
        return self.get("id", "")

    @property
    def object(self) -> str:
        return self.get("object", "pharmassistant.conversation")

    @property
    def title(self) -> str | None:
        return self.get("title")

    @property
    def created_at(self) -> str | None:
        return self.get("created_at")

    @property
    def updated_at(self) -> str | None:
        return self.get("updated_at")

    @property
    def messages(self) -> list[ConversationMessage]:
        return self.get("messages") or []


class ConversationDeleted(APIObject):
    @property
    def id(self) -> str:
        return self.get("id", "")

    @property
    def object(self) -> str:
        return self.get("object", "pharmassistant.conversation")

    @property
    def deleted(self) -> bool:
        return bool(self.get("deleted", False))


class Health(APIObject):
    @property
    def status(self) -> str:
        return self.get("status", "")

    @property
    def service(self) -> str:
        return self.get("service", "")

    @property
    def version(self) -> str:
        return self.get("version", "")
