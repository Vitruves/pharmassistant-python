# Référence

Tout ce qui s'importe depuis `pharmassistant`. Les guides en donnent l'usage ; ici, chaque nom avec sa signature. La même information est dans les docstrings : `help(pharmassistant.PharmAssistant.ask)`.

## Clients

### `PharmAssistant`

```text
PharmAssistant(api_key=None, *, base_url=None, timeout=None, max_retries=2,
               default_headers=None, http_client=None)
```

| Membre | Rend |
|---|---|
| `ask(question, *, mode="standard", history=None, conversation_id=None, store=False, suggestions=True, patient_advice=True, associated_sale=True, citations="list", timeout=…)` | [`Answer`](#answer) |
| `ask_stream(question, …mêmes options…)` | [`AnswerStream`](#answerstream) |
| `me()` | [`KeyInfo`](#keyinfo) |
| `health()` | [`Health`](#autres-objets), sans authentification |
| `conversations.list(limit=50)` | liste de [`ConversationSummary`](#autres-objets) |
| `conversations.retrieve(conversation_id)` | [`ConversationDetail`](#autres-objets) |
| `conversations.delete(conversation_id)` | [`ConversationDeleted`](#autres-objets) |
| `start_conversation(*, store=False, max_history_turns=12, **options)` | [`Conversation`](#conversation-et-asyncconversation) |
| `resume_conversation(conversation_id, **options)` | [`Conversation`](#conversation-et-asyncconversation), gardée par le serveur |
| `with_options(*, timeout=…, max_retries=None, default_headers=None)` | copie du client, mêmes connexions |
| `base_url`, `timeout`, `max_retries` | réglages en vigueur |
| `close()`, `with` | ferme les connexions (sauf un `http_client` fourni) |
| `conversations(limit=50)`, `conversation(id)`, `delete_conversation(id)` | alias hérités du [fichier unique](fichier-unique.md) |

Guides : [Poser une question](questions.md), [Configuration](configuration.md).

### `AsyncPharmAssistant`

Mêmes arguments (avec `httpx.AsyncClient`) et mêmes membres, à attendre, à l'exception des alias du fichier unique. `ask_stream` rend un [`AsyncAnswerStream`](#asyncanswerstream). `start_conversation` et `resume_conversation` rendent une `AsyncConversation`. Guide : [Client asynchrone](asynchrone.md).

### `Conversation` et `AsyncConversation`

| Membre | Rend |
|---|---|
| `ask(question, **options)` | `Answer`, dans la suite de l'échange |
| `ask_stream(question, **options)` | flux, la conversation se met à jour à `done` |
| `id` | `conv_…` (gardée par le serveur), sinon `None` |
| `store` | `True` si gardée par le serveur |
| `history` | historique local (copie) |
| `last_answer` | dernière `Answer` |
| `delete()` | efface côté serveur et repart à zéro |
| `reset()` | repart à zéro sans rien effacer |

Guide : [Conversations](conversations.md).

## Réponses

Tous les objets de réponse héritent d'`APIObject`, un `dict` lisible par attributs, avec `to_dict()` et `to_json(*, indent=2)`.

### `Answer`

| Attribut | Type |
|---|---|
| `id`, `request_id` | `str` (`req_…`) |
| `object`, `created_at`, `status`, `mode`, `question`, `citations` | `str` |
| `title`, `answer`, `patient_advice`, `associated_sale`, `conversation_id` | `str` ou `None` |
| `key_points` | `list[KeyPoint]` |
| `suggestions`, `tools_used` | `list[str]` |
| `sources` | `dict[str, list[SourceRef]]` |
| `references` | `list[Reference]` |
| `passages` | `list[Passage]` |
| `clarification` | `Clarification` ou `None` |
| `usage` | `Usage` |
| `rate_limit` | `RateLimit` ou `None` (hors JSON) |
| `needs_clarification` | `bool` |

| Méthode | Rend |
|---|---|
| `all_sources()` | `list[SourceRef]`, sans doublon |
| `reference(n)` | `Reference` ou `None` |
| `iter_citations()` | itérateur de `Citation` |
| `answer_without_markers()` | `str` ou `None` |

Guides : [Lire la réponse](questions.md#lire-la-réponse), [Sources et citations](citations.md).

### Objets de la réponse

| Classe | Attributs |
|---|---|
| `KeyPoint` | `polarity`, `text`, `is_positive` |
| `SourceRef` | `title`, `url` |
| `Reference` | `n`, `tool`, `title`, `url`, `empty`, `query`, `marker` (`"[Sn]"`) |
| `Passage` | `index`, `n`, `quote`, `before`, `after`, `record`, `record_title`, `is_record` |
| `RecordLine` | `label`, `value`, `cited` |
| `Clarification` | `word`, `corrections`, `message`, `corrected_question(question, correction)` |
| `Usage` | `elapsed_ms`, `daily_requests_used`, `daily_requests_limit` |
| `Citation` (tuple) | `rank`, `n`, `reference`, `passage`, `start`, `end` |
| `RateLimit` (tuple) | `limit`, `remaining`, `reset_at` |

### `KeyInfo`

`id`, `name`, `key_hint`, `pharmacy_slug`, `daily_limit`, `monthly_limit`, `daily_detailed_limit`, `limits_locked`, `scopes`, `active`, `expires_at`, `created_at`, `last_used_at`, `daily_requests_used`, `daily_detailed_used`, `month_requests_used` ; calculés : `daily_remaining`, `monthly_remaining` (`None` sans plafond) ; `has_scope(scope)`. Un plafond `None` veut dire illimité, `scopes` à `None` veut dire toutes les portées.

### Autres objets

| Classe | Attributs |
|---|---|
| `ConversationSummary` | `id`, `title`, `message_count`, `created_at`, `updated_at` |
| `ConversationDetail` | `id`, `object`, `title`, `created_at`, `updated_at`, `messages` |
| `ConversationMessage` | `role`, `content`, `created_at` |
| `ConversationDeleted` | `id`, `object`, `deleted` |
| `Health` | `status`, `service`, `version` |

## Flux

### `AnswerStream`

| Membre | Rend |
|---|---|
| itération, `next()` | `StreamEvent` |
| `text_stream` | itérateur des seuls fragments de texte |
| `get_final_answer()` | `Answer`, après avoir consommé le reste |
| `request_id` | après `start` |
| `references` | après `references` (`citations="inline"`) |
| `answer` | après `done` |
| `rate_limit` | en-têtes de quota |
| `response` | la `httpx.Response` sous-jacente |
| `close()`, `with` | ferme la connexion |

### `AsyncAnswerStream`

Mêmes membres : `async for`, `async with`, `text_stream` à parcourir avec `async for`, `await get_final_answer()`, `await close()`.

### `StreamEvent`

Tuple `(event, data)`, avec `text` (chunk), `state` (status), `answer` (done). Guide : [Réponse en flux](flux.md).

## Erreurs

`PharmAssistantError` et ses sous-classes : `ConfigurationError`, `APIConnectionError`, `APITimeoutError`, `APIStatusError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ConversationNotFoundError`, `InvalidRequestError`, `RateLimitError`, `QuotaExceededError`, `ServerError`. Attributs : `code`, `message`, `status`, `request_id`, `details`, `aide`, `headers` ; `RateLimitError.retry_after`, `QuotaExceededError.reset_at`.

`CODES` : dict code → `(status, sens, aide, decompte)`, pour chaque code connu.

Guide : [Erreurs, quotas et nouveaux essais](erreurs.md).

## Aide et constantes

| Nom | Rôle |
|---|---|
| `aide(sujet=None)` | affiche l'aide : sommaire, sujet ou code d'erreur |
| `texte_d_aide(sujet=None)` | le même texte, en chaîne ; `KeyError` sur un sujet inconnu |
| `DEFAULT_BASE_URL` | `https://api.pharmassistant.fr` |
| `DEFAULT_TIMEOUT` | `httpx.Timeout(300.0, connect=10.0)` |
| `DEFAULT_MAX_RETRIES` | `2` |
| `__version__` | version du paquet |
