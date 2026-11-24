# Erreurs, quotas et nouveaux essais

## Les exceptions

Toutes les erreurs héritent de `PharmAssistantError` :

```
PharmAssistantError
├── ConfigurationError          clé absente ou mal formée, URL invalide (aussi ValueError)
├── APIConnectionError          réseau, réponse illisible, flux coupé
│   └── APITimeoutError         délai dépassé
└── APIStatusError              l'API a refusé ou échoué
    ├── AuthenticationError     401
    ├── PermissionDeniedError   403
    ├── NotFoundError           404
    │   └── ConversationNotFoundError
    ├── InvalidRequestError     422
    ├── RateLimitError          429 anti-rafale
    ├── QuotaExceededError      429 plafond atteint
    └── ServerError             5xx
```

Chacune porte :

| Attribut | Contenu |
|---|---|
| `code` | code machine stable, voir le tableau plus bas |
| `message` | explication en français, celle de l'API |
| `status` | statut HTTP, `None` pour une erreur côté client |
| `request_id` | identifiant `req_…`, à joindre à toute demande de support |
| `details` | sur `InvalidRequestError` : le motif champ par champ |
| `aide` | ce qu'il faut faire, en une phrase |
| `headers` | en-têtes de la réponse HTTP |

Et, selon la classe : `RateLimitError.retry_after` (secondes avant de réessayer) et `QuotaExceededError.reset_at` (prochaine remise à zéro du compteur journalier, en UTC, ou `None` pour une clé sans plafond journalier). Le plafond mensuel, lui, revient le 1er du mois : distinguez-le par `code`.

`str(erreur)` assemble tout cela, prêt pour un journal :

```
[429] daily_limit_reached: Plafond journalier de la clé atteint (100 requêtes). …
Aide : Attendez minuit (heure de Paris), ou relevez le plafond depuis le portail s'il n'est pas verrouillé. Requête non décomptée.
Requête : req_9f2c4a1b6d8e3f07
```

## Attraper ce qui compte

```python
from pharmassistant import (APIConnectionError, AuthenticationError, PharmAssistantError,
                            QuotaExceededError)

try:
    reponse = client.ask("Amoxicilline et allaitement ?")
except QuotaExceededError as e:
    if e.code == "monthly_limit_reached":
        afficher("Plafond du mois atteint, retour le 1er.")
    else:
        afficher("Plafond du jour atteint, retour à minuit.")
except AuthenticationError:
    alerter_l_administrateur("Clé PharmAssistant invalide ou révoquée")
except APIConnectionError:
    afficher("PharmAssistant est injoignable, réessayez dans un instant.")
except PharmAssistantError as e:
    journal.error("PharmAssistant : %s", e)
```

## Les codes

| Code | HTTP | Classe | Sens | Décompté |
|---|---|---|---|---|
| `missing_api_key` | 401 | `AuthenticationError` | aucune clé envoyée | non |
| `invalid_api_key` | 401 | `AuthenticationError` | clé inconnue ou mal formée | non |
| `revoked_api_key` | 401 | `AuthenticationError` | clé révoquée | non |
| `expired_api_key` | 401 | `AuthenticationError` | clé périmée | non |
| `pharmacy_not_found` | 403 | `PermissionDeniedError` | pharmacie liée introuvable | non |
| `pharmacy_suspended` | 403 | `PermissionDeniedError` | pharmacie liée suspendue | non |
| `scope_denied` | 403 | `PermissionDeniedError` | portée manquante (`ask:detailed` pour le mode Détaillé) | non |
| `conversation_not_found` | 404 | `ConversationNotFoundError` | conversation inconnue, supprimée ou purgée | non |
| `not_found` | 404 | `NotFoundError` | adresse inconnue de l'API | non |
| `invalid_request` | 422 | `InvalidRequestError` | requête refusée, motif dans `details` | non |
| `rate_limited` | 429 | `RateLimitError` | anti-rafale, réessayé seul | non |
| `daily_limit_reached` | 429 | `QuotaExceededError` | plafond journalier | non |
| `monthly_limit_reached` | 429 | `QuotaExceededError` | plafond mensuel | non |
| `detailed_limit_reached` | 429 | `QuotaExceededError` | sous-plafond du mode Détaillé | non |
| `internal_error` | 500 | `ServerError` | erreur interne, réessayée seule | non |
| `generation_failed` | 502 | `ServerError` | rédaction en échec, réessayée seule | non |
| `empty_response` | 502 | `ServerError` | réponse vide, réessayée seule | non |
| `connection_error` | | `APIConnectionError` | serveur injoignable | non |
| `timeout` | | `APITimeoutError` | délai dépassé | peut-être |
| `stream_interrupted` | | `APIConnectionError` | flux coupé avant la fin | peut-être |

Conduite à tenir pour un code : `pharmassistant.aide("scope_denied")`, ou `pharmassistant aide scope_denied` dans un terminal. La liste : `pharmassistant aide codes`. Un code inconnu de cette version du paquet est classé par son statut HTTP.

## Ce qui est décompté

La facturation compte des requêtes, pas des jetons. Une requête refusée ou en échec côté serveur (401, 403, 404, 422, 429, 500, 502, événement `error` du flux) n'est jamais décomptée. Seul cas douteux : une réponse perdue en route (délai de lecture dépassé, flux coupé), que le serveur a pu achever.

## Nouveaux essais automatiques

Le client réessaie seul, `max_retries` fois (2 par défaut), quand rien ne peut avoir été décompté :

| Situation | Attente |
|---|---|
| connexion impossible (réseau, DNS) | croissante : 0,5 s, 1 s, 2 s… plafonnée à 8 s, avec un peu d'aléa |
| `rate_limited` | l'en-tête `Retry-After`, 60 s au plus |
| 500, 502, 503, 504 | croissante |
| lecture coupée sur une lecture (`me`, `conversations.list`…) | croissante |

Jamais réessayé seul : un plafond atteint, un refus 4xx, une question dont la lecture a été coupée (elle a pu être décomptée), un flux commencé.

```python
client = PharmAssistant(max_retries=0)                  # aucun nouvel essai
client.with_options(max_retries=5).ask("…")             # pour un appel
```

Chaque nouvel essai est journalisé au niveau `WARNING` sur le journal `pharmassistant`, voir [Configuration](configuration.md#journal).

## Suivre son quota

```python
reponse = client.ask("Amoxicilline et allaitement ?")
if reponse.rate_limit:
    print(reponse.rate_limit.remaining, "sur", reponse.rate_limit.limit)

etat = client.me()
print(etat.daily_remaining, etat.monthly_remaining)
print(etat.daily_detailed_used, "/", etat.daily_detailed_limit)
```

Le plafond journalier revient à minuit et le mensuel au 1er du mois, heure de Paris. Une clé sans plafond n'envoie pas d'en-tête : `rate_limit` vaut alors `None`. Une recette de suivi : [Tableau de bord de quota](recettes.md#tableau-de-bord-de-quota).
