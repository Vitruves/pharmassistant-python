"""État d'une conversation suivie par le client, commun au synchrone et à l'asynchrone."""

from __future__ import annotations

from typing import Any

from ._models import Answer

MAX_HISTORY_TURNS = 12


class EtatConversation:
    def __init__(self, *, store: bool, conversation_id: str | None,
                 history: list[dict[str, str]] | None, max_history_turns: int,
                 defaults: dict[str, Any]) -> None:
        if conversation_id and not store:
            raise ValueError("Une conversation reprise par son id est gardée par le serveur "
                             "(store=True).")
        if history and store:
            raise ValueError("history ne sert qu'aux conversations locales (store=False).")
        interdits = {"history", "conversation_id", "store"} & set(defaults)
        if interdits:
            raise ValueError(f"{', '.join(sorted(interdits))} : géré par la conversation.")
        self.store = store
        self.conversation_id = conversation_id
        self.history: list[dict[str, str]] = list(history or [])
        self.max_history_turns = max_history_turns
        self.defaults = defaults
        self.last_answer: Answer | None = None

    def options(self, options: dict[str, Any]) -> dict[str, Any]:
        interdits = {"history", "conversation_id", "store"} & set(options)
        if interdits:
            raise ValueError(f"{', '.join(sorted(interdits))} : géré par la conversation.")
        sortie = {**self.defaults, **options}
        if self.store:
            if self.conversation_id:
                sortie["conversation_id"] = self.conversation_id
            else:
                sortie["store"] = True
        elif self.history:
            sortie["history"] = list(self.history)
        return sortie

    def noter(self, question: str, reponse: Answer) -> None:
        self.last_answer = reponse
        if self.store:
            self.conversation_id = reponse.conversation_id or self.conversation_id
            return
        texte = reponse.answer_without_markers() if reponse.answer is not None else (
            reponse.clarification.message if reponse.clarification else "")
        if not texte:
            return
        self.history += [{"role": "user", "content": question},
                         {"role": "assistant", "content": texte}]
        self.history = self.history[-2 * self.max_history_turns:]

    def oublier(self) -> None:
        self.conversation_id = None
        self.history = []
        self.last_answer = None
