"""Réponse en flux (Server-Sent Events) de POST /v1/ask."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Iterator
from typing import Any, Callable, NamedTuple

import httpx

from ._errors import (
    APIConnectionError,
    APITimeoutError,
    PharmAssistantError,
    erreur_d_api,
)
from ._models import Answer, RateLimit, Reference

EVENEMENTS = ("start", "status", "references", "chunk", "done", "error")

class StreamEvent(NamedTuple):
    """Un événement du flux. Se déballe en `event, data`.

    Événements : start, status (data["state"] : routing, tools_running,
    generating), references (citations="inline"), chunk (data["text"]), done
    (data = Answer complète). Un événement error lève l'exception typée.
    """

    event: str
    data: Any

    @property
    def text(self) -> str:
        """Fragment de réponse (chunk), chaîne vide sinon."""
        return self.data.get("text", "") if self.event == "chunk" else ""

    @property
    def state(self) -> str | None:
        return self.data.get("state") if self.event == "status" else None

    @property
    def answer(self) -> Answer | None:
        return self.data if self.event == "done" else None


class LecteurSSE:
    """Assemble les lignes SSE en couples (événement, données brutes)."""

    def __init__(self) -> None:
        self._evenement: str | None = None
        self._donnees: list[str] = []

    def ligne(self, ligne: str) -> tuple[str, str] | None:
        ligne = ligne.rstrip("\r")
        if not ligne:
            if not self._donnees and self._evenement is None:
                return None
            sortie = (self._evenement or "message", "\n".join(self._donnees))
            self._evenement, self._donnees = None, []
            return sortie
        if ligne.startswith(":"):
            return None
        champ, _, valeur = ligne.partition(":")
        if valeur.startswith(" "):
            valeur = valeur[1:]
        if champ == "event":
            self._evenement = valeur
        elif champ == "data":
            self._donnees.append(valeur)
        return None

    def fin(self) -> tuple[str, str] | None:
        return self.ligne("") if self._donnees else None


def decoder(evenement: str, brut: str, request_id: str | None) -> StreamEvent:
    try:
        donnees: Any = json.loads(brut) if brut else {}
    except ValueError:
        donnees = {"raw": brut}
    if evenement == "error":
        raise erreur_d_api(None, donnees, request_id=request_id)
    if evenement == "done":
        donnees = Answer(donnees)
    elif evenement == "references" and isinstance(donnees, dict):
        donnees = {**donnees, "references": [Reference(r) for r in donnees.get("references") or []]}
    return StreamEvent(evenement, donnees)


def _coupure(exc: BaseException, request_id: str | None) -> PharmAssistantError:
    if isinstance(exc, httpx.TimeoutException):
        return APITimeoutError(f"Délai dépassé pendant le flux : {exc}", code="timeout",
                               request_id=request_id)
    return APIConnectionError(f"Flux coupé : {exc}", code="stream_interrupted",
                              request_id=request_id)


class _Etat:
    def __init__(self, rate_limit: RateLimit | None,
                 on_done: Callable[[Answer], None] | None) -> None:
        self.request_id: str | None = None
        self.references: list[Reference] = []
        self.answer: Answer | None = None
        self.rate_limit = rate_limit
        self._on_done = on_done

    def noter(self, evt: StreamEvent) -> None:
        if evt.event == "start" and isinstance(evt.data, dict):
            self.request_id = evt.data.get("id")
        elif evt.event == "references":
            self.references = evt.data.get("references", [])
        elif evt.event == "done":
            evt.data.rate_limit = self.rate_limit
            self.answer = evt.data
            if self._on_done is not None:
                self._on_done(evt.data)

    def interrompu(self) -> APIConnectionError:
        return APIConnectionError("Le flux s'est arrêté avant l'événement done.",
                                  code="stream_interrupted", request_id=self.request_id)


class AnswerStream:
    """Flux d'une réponse : itérable d'événements, à fermer (ou `with`).

        with client.ask_stream("Amoxicilline et allaitement ?") as flux:
            for texte in flux.text_stream:
                print(texte, end="", flush=True)
            reponse = flux.get_final_answer()
    """

    def __init__(self, reponse: httpx.Response, *, rate_limit: RateLimit | None = None,
                 on_done: Callable[[Answer], None] | None = None) -> None:
        self.response = reponse
        self._etat = _Etat(rate_limit, on_done)
        self._iterateur = self._evenements()

    @property
    def request_id(self) -> str | None:
        return self._etat.request_id

    @property
    def references(self) -> list[Reference]:
        """Registre des sources (citations="inline"), connu avant le premier fragment."""
        return self._etat.references

    @property
    def answer(self) -> Answer | None:
        """La réponse complète, une fois l'événement done reçu."""
        return self._etat.answer

    @property
    def rate_limit(self) -> RateLimit | None:
        return self._etat.rate_limit

    def _evenements(self) -> Generator[StreamEvent, None, None]:
        lecteur = LecteurSSE()
        try:
            try:
                for ligne in self.response.iter_lines():
                    brut = lecteur.ligne(ligne)
                    if brut is not None:
                        evt = decoder(*brut, self._etat.request_id)
                        self._etat.noter(evt)
                        yield evt
                        if evt.event == "done":
                            return
                reste = lecteur.fin()
                if reste is not None:
                    evt = decoder(*reste, self._etat.request_id)
                    self._etat.noter(evt)
                    yield evt
                    if evt.event == "done":
                        return
            except httpx.HTTPError as exc:
                raise _coupure(exc, self._etat.request_id) from exc
            raise self._etat.interrompu()
        finally:
            self.response.close()

    def __iter__(self) -> Iterator[StreamEvent]:
        return self._iterateur

    def __next__(self) -> StreamEvent:
        return next(self._iterateur)

    @property
    def text_stream(self) -> Iterator[str]:
        """Les seuls fragments de texte, dans l'ordre."""
        return (evt.text for evt in self if evt.event == "chunk")

    def get_final_answer(self) -> Answer:
        """Consomme le reste du flux et rend la réponse complète."""
        for _ in self:
            pass
        if self._etat.answer is None:
            raise self._etat.interrompu()
        return self._etat.answer

    def close(self) -> None:
        self._iterateur.close()
        self.response.close()

    def __enter__(self) -> AnswerStream:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class AsyncAnswerStream:
    """Version asynchrone d'AnswerStream (`async for`, `async with`)."""

    def __init__(self, reponse: httpx.Response, *, rate_limit: RateLimit | None = None,
                 on_done: Callable[[Answer], None] | None = None) -> None:
        self.response = reponse
        self._etat = _Etat(rate_limit, on_done)
        self._iterateur = self._evenements()

    @property
    def request_id(self) -> str | None:
        return self._etat.request_id

    @property
    def references(self) -> list[Reference]:
        return self._etat.references

    @property
    def answer(self) -> Answer | None:
        return self._etat.answer

    @property
    def rate_limit(self) -> RateLimit | None:
        return self._etat.rate_limit

    async def _evenements(self) -> AsyncGenerator[StreamEvent, None]:
        lecteur = LecteurSSE()
        try:
            try:
                async for ligne in self.response.aiter_lines():
                    brut = lecteur.ligne(ligne)
                    if brut is not None:
                        evt = decoder(*brut, self._etat.request_id)
                        self._etat.noter(evt)
                        yield evt
                        if evt.event == "done":
                            return
                reste = lecteur.fin()
                if reste is not None:
                    evt = decoder(*reste, self._etat.request_id)
                    self._etat.noter(evt)
                    yield evt
                    if evt.event == "done":
                        return
            except httpx.HTTPError as exc:
                raise _coupure(exc, self._etat.request_id) from exc
            raise self._etat.interrompu()
        finally:
            await self.response.aclose()

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self._iterateur

    async def __anext__(self) -> StreamEvent:
        return await self._iterateur.__anext__()

    @property
    def text_stream(self) -> AsyncIterator[str]:
        """Les seuls fragments de texte, dans l'ordre (`async for`)."""
        return self._textes()

    async def _textes(self) -> AsyncIterator[str]:
        async for evt in self:
            if evt.event == "chunk":
                yield evt.text

    async def get_final_answer(self) -> Answer:
        async for _ in self:
            pass
        if self._etat.answer is None:
            raise self._etat.interrompu()
        return self._etat.answer

    async def close(self) -> None:
        await self._iterateur.aclose()
        await self.response.aclose()

    async def __aenter__(self) -> AsyncAnswerStream:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

