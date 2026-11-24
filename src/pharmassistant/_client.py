"""Clients de l'API PharmAssistant : PharmAssistant (synchrone) et AsyncPharmAssistant."""

from __future__ import annotations

import asyncio
import builtins
import time
from collections.abc import Mapping
from typing import Any, Callable, TypeVar

import httpx

from ._base import (
    DEFAULT_MAX_RETRIES,
    NOT_GIVEN,
    HistoryInput,
    Options,
    TimeoutInput,
    code_d_erreur,
    corps_ask,
    delai_de_reessai,
    erreur_reseau,
    lever_si_erreur,
    lire_json,
    logger,
)
from ._conversation import MAX_HISTORY_TURNS, EtatConversation
from ._models import (
    Answer,
    ConversationDeleted,
    ConversationDetail,
    ConversationSummary,
    Health,
    KeyInfo,
    RateLimit,
)
from ._streaming import AnswerStream, AsyncAnswerStream

_DOC_ASK = """
        Paramètres :

        question : la question, en français (4 000 signes au plus).
        mode : "standard" (défaut, rapide) ou "detailed" (analyse exhaustive,
            portée ask:detailed requise, plus lente).
        history : tours précédents quand VOUS portez l'historique, liste de
            {"role": "user"|"assistant", "content": "…"} ou de couples (rôle, texte).
            Exclusif de store et de conversation_id.
        conversation_id : poursuit une conversation gardée par le serveur (conv_…).
        store : True ouvre une conversation gardée par le serveur ; la réponse
            porte conversation_id. Purge après 90 jours d'inactivité.
        suggestions, patient_advice, associated_sale : False retire le bloc.
        instructions : consignes libres ajoutées à la rédaction (2 000 signes).
        citations : "list" (défaut) = références à part dans `sources` ;
            "inline" = repères [S1] dans `answer`, registre `references`,
            extraits `passages`, et aveu quand aucune source ne couvre la question.
        timeout : délai pour cet appel seulement (secondes ou httpx.Timeout).
"""


_F = TypeVar("_F", bound=Callable[..., Any])


def _doc(fonction: _F) -> _F:
    fonction.__doc__ = (fonction.__doc__ or "") + _DOC_ASK
    return fonction


class _Journal:
    @staticmethod
    def reessai(methode: str, chemin: str, tentative: int, maximum: int, delai: float,
                motif: str) -> None:
        logger.warning("%s %s : %s, nouvel essai %d/%d dans %s s", methode, chemin, motif,
                       tentative + 1, maximum, f"{delai:.1f}".replace(".", ","))

    @staticmethod
    def fin(methode: str, chemin: str, reponse: httpx.Response, debut: float) -> None:
        logger.debug("%s %s → %d en %s s (%s)", methode, chemin, reponse.status_code,
                     f"{time.monotonic() - debut:.2f}".replace(".", ","),
                     reponse.headers.get("x-request-id", "sans id"))


class PharmAssistant:
    """Client synchrone de l'API PharmAssistant.

        from pharmassistant import PharmAssistant

        client = PharmAssistant()            # clé lue dans PHARMASSISTANT_API_KEY
        reponse = client.ask("Amoxicilline et allaitement ?")
        print(reponse.answer)

    api_key : clé pa_… (défaut : PHARMASSISTANT_API_KEY).
    base_url : défaut PHARMASSISTANT_API_URL, sinon https://api.pharmassistant.fr.
    timeout : secondes ou httpx.Timeout (défaut 300 s, connexion 10 s).
    max_retries : nouveaux essais sur connexion impossible, rafale (429
        rate_limited) et 5xx, jamais décomptés (défaut 2 ; 0 pour aucun).
    default_headers : en-têtes ajoutés à chaque requête.
    http_client : httpx.Client fourni (proxy, certificats) ; non fermé par close().

    Utilisable en `with` ; sûr entre fils d'exécution.
    """

    def __init__(self, api_key: str | None = None, *, base_url: str | None = None,
                 timeout: TimeoutInput = None, max_retries: int = DEFAULT_MAX_RETRIES,
                 default_headers: Mapping[str, str] | None = None,
                 http_client: httpx.Client | None = None) -> None:
        self._opts = Options(api_key, base_url, timeout, max_retries, default_headers)
        self._http = http_client if http_client is not None else httpx.Client()
        self._possede = http_client is None
        self._sleep = time.sleep
        self.conversations = Conversations(self)

    @property
    def base_url(self) -> str:
        return self._opts.base_url

    @property
    def timeout(self) -> httpx.Timeout:
        return self._opts.timeout

    @property
    def max_retries(self) -> int:
        return self._opts.max_retries

    def with_options(self, *, timeout: TimeoutInput = NOT_GIVEN, max_retries: int | None = None,
                     default_headers: Mapping[str, str] | None = None) -> PharmAssistant:
        """Copie du client avec d'autres réglages, sur la même connexion.

            client.with_options(timeout=600).ask("…", mode="detailed")
        """
        copie = object.__new__(PharmAssistant)
        copie.__dict__.update(self.__dict__)
        copie._opts = self._opts.derive(timeout=timeout, max_retries=max_retries,
                                        default_headers=default_headers)
        copie._possede = False
        copie.conversations = Conversations(copie)
        return copie

    def _timeout(self, timeout: TimeoutInput) -> httpx.Timeout:
        return self._opts.derive(timeout=timeout).timeout if timeout is not NOT_GIVEN \
            else self._opts.timeout

    def _envoyer(self, methode: str, chemin: str, *, json: Any = None,
                 params: dict[str, Any] | None = None, flux: bool = False,
                 timeout: TimeoutInput = NOT_GIVEN, auth: bool = True) -> httpx.Response:
        requete = self._http.build_request(
            methode, self._opts.base_url + chemin, json=json, params=params,
            headers=self._opts.entetes(auth=auth, flux=flux),
            timeout=self._timeout(timeout))
        tentative = 0
        while True:
            debut = time.monotonic()
            try:
                reponse = self._http.send(requete, stream=flux)
            except httpx.TransportError as exc:
                delai = delai_de_reessai(tentative, self._opts.max_retries, methode, exc=exc)
                if delai is None:
                    raise erreur_reseau(exc) from exc
                _Journal.reessai(methode, chemin, tentative, self._opts.max_retries, delai,
                                 type(exc).__name__)
                self._sleep(delai)
                tentative += 1
                continue
            if reponse.status_code >= 400:
                if flux:
                    reponse.read()
                    reponse.close()
                code = code_d_erreur(reponse)
                delai = delai_de_reessai(tentative, self._opts.max_retries, methode,
                                         status=reponse.status_code, code=code,
                                         headers=reponse.headers)
                if delai is not None:
                    _Journal.reessai(methode, chemin, tentative, self._opts.max_retries, delai,
                                     code or f"HTTP {reponse.status_code}")
                    self._sleep(delai)
                    tentative += 1
                    continue
            _Journal.fin(methode, chemin, reponse, debut)
            return reponse

    def _json(self, methode: str, chemin: str, **kwargs: Any) -> Any:
        corps, _ = lire_json(self._envoyer(methode, chemin, **kwargs))
        return corps

    @_doc
    def ask(self, question: str, *, mode: str = "standard", history: HistoryInput | None = None,
            conversation_id: str | None = None, store: bool = False, suggestions: bool = True,
            patient_advice: bool = True, associated_sale: bool = True,
            instructions: str | None = None, citations: str = "list",
            timeout: TimeoutInput = NOT_GIVEN) -> Answer:
        """Pose une question et rend la réponse complète (Answer).

        Une réponse peut demander une précision : `reponse.needs_clarification`,
        puis `reponse.clarification.corrected_question(question, correction)`.
        """
        corps = corps_ask(question, mode=mode, history=history, conversation_id=conversation_id,
                          store=store, suggestions=suggestions, patient_advice=patient_advice,
                          associated_sale=associated_sale, instructions=instructions,
                          citations=citations)
        donnees, quota = lire_json(self._envoyer("POST", "/v1/ask", json=corps, timeout=timeout))
        reponse = Answer(donnees)
        reponse.rate_limit = quota
        return reponse

    @_doc
    def ask_stream(self, question: str, *, mode: str = "standard",
                   history: HistoryInput | None = None, conversation_id: str | None = None,
                   store: bool = False, suggestions: bool = True, patient_advice: bool = True,
                   associated_sale: bool = True, instructions: str | None = None,
                   citations: str = "list", timeout: TimeoutInput = NOT_GIVEN) -> AnswerStream:
        """Pose une question et rend la réponse en flux (AnswerStream).

            with client.ask_stream("Amoxicilline et allaitement ?") as flux:
                for texte in flux.text_stream:
                    print(texte, end="", flush=True)
                reponse = flux.get_final_answer()

        Le flux se déballe aussi en `for event, data in flux`. Les refus de
        pré-vol (clé, quota, conversation inconnue) sont levés dès l'appel.
        """
        return self._flux(corps_ask(
            question, mode=mode, history=history, conversation_id=conversation_id, store=store,
            suggestions=suggestions, patient_advice=patient_advice,
            associated_sale=associated_sale, instructions=instructions, citations=citations,
            stream=True), timeout)

    def _flux(self, corps: dict[str, Any], timeout: TimeoutInput, on_done: Any = None) -> AnswerStream:
        reponse = self._envoyer("POST", "/v1/ask", json=corps, flux=True, timeout=timeout)
        lever_si_erreur(reponse)
        return AnswerStream(reponse, rate_limit=RateLimit.from_headers(reponse.headers),
                            on_done=on_done)

    def me(self) -> KeyInfo:
        """État de la clé : plafonds, portées, consommation du jour et du mois."""
        return KeyInfo(self._json("GET", "/v1/me"))

    def health(self) -> Health:
        """Disponibilité du service (sans authentification)."""
        return Health(self._json("GET", "/v1/health", auth=False))

    def start_conversation(self, *, store: bool = False, max_history_turns: int = MAX_HISTORY_TURNS,
                           **defaults: Any) -> Conversation:
        """Ouvre une conversation : chaque ask() poursuit la précédente.

        store=False (défaut) : l'historique reste chez vous, rien n'est gardé par
        le serveur. store=True : le serveur garde la conversation (id conv_…).
        `defaults` : options d'ask appliquées à chaque tour (mode, citations…).
        """
        return Conversation(self, EtatConversation(
            store=store, conversation_id=None, history=None,
            max_history_turns=max_history_turns, defaults=defaults))

    def resume_conversation(self, conversation_id: str, **defaults: Any) -> Conversation:
        """Reprend une conversation gardée par le serveur, par son id conv_…."""
        return Conversation(self, EtatConversation(
            store=True, conversation_id=conversation_id, history=None,
            max_history_turns=MAX_HISTORY_TURNS, defaults=defaults))

    def conversation(self, conversation_id: str) -> ConversationDetail:
        """Alias de conversations.retrieve()."""
        return self.conversations.retrieve(conversation_id)

    def delete_conversation(self, conversation_id: str) -> ConversationDeleted:
        """Alias de conversations.delete()."""
        return self.conversations.delete(conversation_id)

    def close(self) -> None:
        if self._possede:
            self._http.close()

    def __enter__(self) -> PharmAssistant:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"PharmAssistant(base_url={self._opts.base_url!r})"


class Conversations:
    """Conversations gardées par le serveur : list, retrieve, delete."""

    def __init__(self, client: PharmAssistant) -> None:
        self._client = client

    def list(self, limit: int = 50) -> builtins.list[ConversationSummary]:
        """Conversations de la clé, la plus récemment active d'abord."""
        corps = self._client._json("GET", "/v1/conversations", params={"limit": limit})
        return [ConversationSummary(c) for c in corps.get("data", [])]

    def retrieve(self, conversation_id: str) -> ConversationDetail:
        """Titre, dates et tous les tours d'une conversation."""
        return ConversationDetail(self._client._json("GET", f"/v1/conversations/{conversation_id}"))

    def delete(self, conversation_id: str) -> ConversationDeleted:
        """Suppression immédiate et définitive, messages compris."""
        return ConversationDeleted(
            self._client._json("DELETE", f"/v1/conversations/{conversation_id}"))

    def __call__(self, limit: int = 50) -> builtins.list[ConversationSummary]:
        return self.list(limit)


class Conversation:
    """Conversation suivie par le client (voir PharmAssistant.start_conversation)."""

    def __init__(self, client: PharmAssistant, etat: EtatConversation) -> None:
        self._client = client
        self._etat = etat

    @property
    def id(self) -> str | None:
        """Id conv_… (store=True, après le premier tour), sinon None."""
        return self._etat.conversation_id

    @property
    def store(self) -> bool:
        return self._etat.store

    @property
    def history(self) -> list[dict[str, str]]:
        """Historique local (store=False)."""
        return list(self._etat.history)

    @property
    def last_answer(self) -> Answer | None:
        return self._etat.last_answer

    def ask(self, question: str, **options: Any) -> Answer:
        """Comme PharmAssistant.ask(), dans la suite de la conversation."""
        reponse = self._client.ask(question, **self._etat.options(options))
        self._etat.noter(question, reponse)
        return reponse

    def ask_stream(self, question: str, **options: Any) -> AnswerStream:
        """Comme PharmAssistant.ask_stream(), dans la suite de la conversation."""
        opts = self._etat.options(options)
        timeout = opts.pop("timeout", NOT_GIVEN)
        return self._client._flux(corps_ask(question, stream=True, **opts), timeout,
                                  on_done=lambda r: self._etat.noter(question, r))

    def delete(self) -> None:
        """Supprime la conversation côté serveur (store=True) et repart à zéro."""
        if self._etat.store and self._etat.conversation_id:
            self._client.conversations.delete(self._etat.conversation_id)
        self._etat.oublier()

    def reset(self) -> None:
        """Repart à zéro sans rien supprimer côté serveur."""
        self._etat.oublier()


class AsyncPharmAssistant:
    """Client asynchrone : mêmes méthodes que PharmAssistant, à attendre (await).

        async with AsyncPharmAssistant() as client:
            reponse = await client.ask("Amoxicilline et allaitement ?")
            async with await client.ask_stream("…") as flux:
                async for texte in flux.text_stream:
                    print(texte, end="")
    """

    def __init__(self, api_key: str | None = None, *, base_url: str | None = None,
                 timeout: TimeoutInput = None, max_retries: int = DEFAULT_MAX_RETRIES,
                 default_headers: Mapping[str, str] | None = None,
                 http_client: httpx.AsyncClient | None = None) -> None:
        self._opts = Options(api_key, base_url, timeout, max_retries, default_headers)
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._possede = http_client is None
        self._sleep = asyncio.sleep
        self.conversations = AsyncConversations(self)

    @property
    def base_url(self) -> str:
        return self._opts.base_url

    @property
    def timeout(self) -> httpx.Timeout:
        return self._opts.timeout

    @property
    def max_retries(self) -> int:
        return self._opts.max_retries

    def with_options(self, *, timeout: TimeoutInput = NOT_GIVEN, max_retries: int | None = None,
                     default_headers: Mapping[str, str] | None = None) -> AsyncPharmAssistant:
        """Copie du client avec d'autres réglages, sur la même connexion."""
        copie = object.__new__(AsyncPharmAssistant)
        copie.__dict__.update(self.__dict__)
        copie._opts = self._opts.derive(timeout=timeout, max_retries=max_retries,
                                        default_headers=default_headers)
        copie._possede = False
        copie.conversations = AsyncConversations(copie)
        return copie

    def _timeout(self, timeout: TimeoutInput) -> httpx.Timeout:
        return self._opts.derive(timeout=timeout).timeout if timeout is not NOT_GIVEN \
            else self._opts.timeout

    async def _envoyer(self, methode: str, chemin: str, *, json: Any = None,
                       params: dict[str, Any] | None = None, flux: bool = False,
                       timeout: TimeoutInput = NOT_GIVEN, auth: bool = True) -> httpx.Response:
        requete = self._http.build_request(
            methode, self._opts.base_url + chemin, json=json, params=params,
            headers=self._opts.entetes(auth=auth, flux=flux),
            timeout=self._timeout(timeout))
        tentative = 0
        while True:
            debut = time.monotonic()
            try:
                reponse = await self._http.send(requete, stream=flux)
            except httpx.TransportError as exc:
                delai = delai_de_reessai(tentative, self._opts.max_retries, methode, exc=exc)
                if delai is None:
                    raise erreur_reseau(exc) from exc
                _Journal.reessai(methode, chemin, tentative, self._opts.max_retries, delai,
                                 type(exc).__name__)
                await self._sleep(delai)
                tentative += 1
                continue
            if reponse.status_code >= 400:
                if flux:
                    await reponse.aread()
                    await reponse.aclose()
                code = code_d_erreur(reponse)
                delai = delai_de_reessai(tentative, self._opts.max_retries, methode,
                                         status=reponse.status_code, code=code,
                                         headers=reponse.headers)
                if delai is not None:
                    _Journal.reessai(methode, chemin, tentative, self._opts.max_retries, delai,
                                     code or f"HTTP {reponse.status_code}")
                    await self._sleep(delai)
                    tentative += 1
                    continue
            _Journal.fin(methode, chemin, reponse, debut)
            return reponse

    async def _json(self, methode: str, chemin: str, **kwargs: Any) -> Any:
        corps, _ = lire_json(await self._envoyer(methode, chemin, **kwargs))
        return corps

    @_doc
    async def ask(self, question: str, *, mode: str = "standard",
                  history: HistoryInput | None = None, conversation_id: str | None = None,
                  store: bool = False, suggestions: bool = True, patient_advice: bool = True,
                  associated_sale: bool = True, instructions: str | None = None,
                  citations: str = "list", timeout: TimeoutInput = NOT_GIVEN) -> Answer:
        """Pose une question et rend la réponse complète (Answer)."""
        corps = corps_ask(question, mode=mode, history=history, conversation_id=conversation_id,
                          store=store, suggestions=suggestions, patient_advice=patient_advice,
                          associated_sale=associated_sale, instructions=instructions,
                          citations=citations)
        donnees, quota = lire_json(await self._envoyer("POST", "/v1/ask", json=corps,
                                                       timeout=timeout))
        reponse = Answer(donnees)
        reponse.rate_limit = quota
        return reponse

    @_doc
    async def ask_stream(self, question: str, *, mode: str = "standard",
                         history: HistoryInput | None = None,
                         conversation_id: str | None = None, store: bool = False,
                         suggestions: bool = True, patient_advice: bool = True,
                         associated_sale: bool = True, instructions: str | None = None,
                         citations: str = "list",
                         timeout: TimeoutInput = NOT_GIVEN) -> AsyncAnswerStream:
        """Pose une question et rend la réponse en flux (AsyncAnswerStream)."""
        return await self._flux(corps_ask(
            question, mode=mode, history=history, conversation_id=conversation_id, store=store,
            suggestions=suggestions, patient_advice=patient_advice,
            associated_sale=associated_sale, instructions=instructions, citations=citations,
            stream=True), timeout)

    async def _flux(self, corps: dict[str, Any], timeout: TimeoutInput,
                    on_done: Any = None) -> AsyncAnswerStream:
        reponse = await self._envoyer("POST", "/v1/ask", json=corps, flux=True, timeout=timeout)
        lever_si_erreur(reponse)
        return AsyncAnswerStream(reponse, rate_limit=RateLimit.from_headers(reponse.headers),
                                 on_done=on_done)

    async def me(self) -> KeyInfo:
        """État de la clé : plafonds, portées, consommation du jour et du mois."""
        return KeyInfo(await self._json("GET", "/v1/me"))

    async def health(self) -> Health:
        """Disponibilité du service (sans authentification)."""
        return Health(await self._json("GET", "/v1/health", auth=False))

    def start_conversation(self, *, store: bool = False, max_history_turns: int = MAX_HISTORY_TURNS,
                           **defaults: Any) -> AsyncConversation:
        """Ouvre une conversation (voir PharmAssistant.start_conversation)."""
        return AsyncConversation(self, EtatConversation(
            store=store, conversation_id=None, history=None,
            max_history_turns=max_history_turns, defaults=defaults))

    def resume_conversation(self, conversation_id: str, **defaults: Any) -> AsyncConversation:
        """Reprend une conversation gardée par le serveur, par son id conv_…."""
        return AsyncConversation(self, EtatConversation(
            store=True, conversation_id=conversation_id, history=None,
            max_history_turns=MAX_HISTORY_TURNS, defaults=defaults))

    async def close(self) -> None:
        if self._possede:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncPharmAssistant:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncPharmAssistant(base_url={self._opts.base_url!r})"


class AsyncConversations:
    """Conversations gardées par le serveur : list, retrieve, delete."""

    def __init__(self, client: AsyncPharmAssistant) -> None:
        self._client = client

    async def list(self, limit: int = 50) -> builtins.list[ConversationSummary]:
        corps = await self._client._json("GET", "/v1/conversations", params={"limit": limit})
        return [ConversationSummary(c) for c in corps.get("data", [])]

    async def retrieve(self, conversation_id: str) -> ConversationDetail:
        return ConversationDetail(
            await self._client._json("GET", f"/v1/conversations/{conversation_id}"))

    async def delete(self, conversation_id: str) -> ConversationDeleted:
        return ConversationDeleted(
            await self._client._json("DELETE", f"/v1/conversations/{conversation_id}"))


class AsyncConversation:
    """Conversation suivie par le client asynchrone."""

    def __init__(self, client: AsyncPharmAssistant, etat: EtatConversation) -> None:
        self._client = client
        self._etat = etat

    @property
    def id(self) -> str | None:
        return self._etat.conversation_id

    @property
    def store(self) -> bool:
        return self._etat.store

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._etat.history)

    @property
    def last_answer(self) -> Answer | None:
        return self._etat.last_answer

    async def ask(self, question: str, **options: Any) -> Answer:
        reponse = await self._client.ask(question, **self._etat.options(options))
        self._etat.noter(question, reponse)
        return reponse

    async def ask_stream(self, question: str, **options: Any) -> AsyncAnswerStream:
        opts = self._etat.options(options)
        timeout = opts.pop("timeout", NOT_GIVEN)
        return await self._client._flux(corps_ask(question, stream=True, **opts), timeout,
                                        on_done=lambda r: self._etat.noter(question, r))

    async def delete(self) -> None:
        if self._etat.store and self._etat.conversation_id:
            await self._client.conversations.delete(self._etat.conversation_id)
        self._etat.oublier()

    def reset(self) -> None:
        self._etat.oublier()
