"""Client Python officiel de l'API PharmAssistant.

    from pharmassistant import PharmAssistant

    client = PharmAssistant()                    # clé : PHARMASSISTANT_API_KEY
    reponse = client.ask("Amoxicilline et allaitement ?")
    print(reponse.answer)

Aide intégrée : pharmassistant.aide() ; documentation : https://api.pharmassistant.fr/docs
"""

from ._aide import aide, texte_d_aide
from ._base import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT
from ._client import (
                      AsyncConversation,
                      AsyncConversations,
                      AsyncPharmAssistant,
                      Conversation,
                      Conversations,
                      PharmAssistant,
)
from ._errors import (
                      CODES,
                      APIConnectionError,
                      APIStatusError,
                      APITimeoutError,
                      AuthenticationError,
                      ConfigurationError,
                      ConversationNotFoundError,
                      InvalidRequestError,
                      NotFoundError,
                      PermissionDeniedError,
                      PharmAssistantError,
                      QuotaExceededError,
                      RateLimitError,
                      ServerError,
)
from ._models import (
                      Answer,
                      APIObject,
                      Citation,
                      Clarification,
                      ConversationDeleted,
                      ConversationDetail,
                      ConversationMessage,
                      ConversationSummary,
                      Health,
                      KeyInfo,
                      KeyPoint,
                      Passage,
                      RateLimit,
                      RecordLine,
                      Reference,
                      SourceRef,
                      Usage,
)
from ._streaming import AnswerStream, AsyncAnswerStream, StreamEvent
from ._version import __version__

__all__ = [
                      "CODES",
                      "DEFAULT_BASE_URL",
                      "DEFAULT_MAX_RETRIES",
                      "DEFAULT_TIMEOUT",
                      "APIConnectionError",
                      "APIObject",
                      "APIStatusError",
                      "APITimeoutError",
                      "Answer",
                      "AnswerStream",
                      "AsyncAnswerStream",
                      "AsyncConversation",
                      "AsyncConversations",
                      "AsyncPharmAssistant",
                      "AuthenticationError",
                      "Citation",
                      "Clarification",
                      "ConfigurationError",
                      "Conversation",
                      "ConversationDeleted",
                      "ConversationDetail",
                      "ConversationMessage",
                      "ConversationNotFoundError",
                      "ConversationSummary",
                      "Conversations",
                      "Health",
                      "InvalidRequestError",
                      "KeyInfo",
                      "KeyPoint",
                      "NotFoundError",
                      "Passage",
                      "PermissionDeniedError",
                      "PharmAssistant",
                      "PharmAssistantError",
                      "QuotaExceededError",
                      "RateLimit",
                      "RateLimitError",
                      "RecordLine",
                      "Reference",
                      "ServerError",
                      "SourceRef",
                      "StreamEvent",
                      "Usage",
                      "__version__",
                      "aide",
                      "texte_d_aide",
]
