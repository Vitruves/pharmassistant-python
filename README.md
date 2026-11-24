<p align="center">
  <a href="https://pharmassistant.fr">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Vitruves/pharmassistant-python/main/.github/images/logo-sombre.png">
      <img src="https://raw.githubusercontent.com/Vitruves/pharmassistant-python/main/.github/images/logo.png" alt="PharmAssistant" width="400">
    </picture>
  </a>
</p>

# pharmassistant

Client Python officiel de l'[API PharmAssistant](https://api.pharmassistant.fr/docs), l'assistant pharmaceutique pour l'officine : réponses sourcées issues des bases documentaires de référence, en JSON structuré.

- Clients synchrone et asynchrone, mêmes méthodes.
- Réponses typées, lisibles par attributs (`reponse.answer`) comme par clés (`reponse["answer"]`).
- Réponse en flux, au fil de la rédaction.
- Conversations suivies, historique chez vous ou gardé par le serveur.
- Sources citées dans le texte (`[S1]`), avec l'extrait qui porte chaque phrase.
- Erreurs typées, chacune avec son aide ; nouveaux essais automatiques quand rien n'a été décompté.
- Commande `pharmassistant` pour le terminal, et une aide intégrée par sujet.

Python 3.9 ou plus récent, une seule dépendance ([httpx](https://www.python-httpx.org)).

## Installation

```bash
pip install pharmassistant
```

## Clé d'API

La clé (`pa_…`) se retire sur le portail dont le lien vous est envoyé par email, après acceptation des [conditions d'utilisation de l'API](https://pharmassistant.fr/developpeurs). Elle n'est montrée qu'une fois ; une clé perdue se régénère depuis le portail, ce qui invalide aussitôt l'ancienne.

```bash
export PHARMASSISTANT_API_KEY=pa_votre_cle
```

Gardez-la dans une variable d'environnement ou un coffre de secrets, jamais dans le code versionné ni dans un navigateur.

## Démarrage rapide

```python
from pharmassistant import PharmAssistant

client = PharmAssistant()   # clé lue dans PHARMASSISTANT_API_KEY

reponse = client.ask("Amoxicilline et allaitement ?")
print(reponse.title)
print(reponse.answer)            # markdown, prêt à afficher
print(reponse.patient_advice)    # discours à tenir au patient
for point in reponse.key_points:
    print("✔" if point.is_positive else "✘", point.text)
```

Dans un terminal :

```bash
pharmassistant "Amoxicilline et allaitement ?"
```

## Poser une question

```python
reponse = client.ask(
    "Tramadol et sertraline ?",
    mode="detailed",          # analyse exhaustive, portée ask:detailed
    citations="inline",       # repères [S1] dans le texte
    patient_advice=False,     # sans discours patient
    instructions="Réponse brève, en trois points.",
)
```

| Paramètre | Effet |
|---|---|
| `mode` | `"standard"` (défaut, rapide) ou `"detailed"` (analyse exhaustive, plus lente, portée `ask:detailed` requise) |
| `citations` | `"list"` (défaut) : références à part dans `sources` ; `"inline"` : repères dans le texte (voir plus bas) |
| `store` | `True` : conversation gardée par le serveur, la réponse porte `conversation_id` |
| `conversation_id` | poursuit une conversation gardée (`conv_…`) |
| `history` | historique porté par vous : dicts `{"role", "content"}` ou couples `(rôle, texte)` ; exclusif de `store` et `conversation_id` |
| `suggestions`, `patient_advice`, `associated_sale` | `False` retire le bloc |
| `instructions` | consignes de rédaction, 2 000 signes au plus |
| `timeout` | délai pour cet appel seulement |

Les paramètres sont vérifiés avant tout envoi : une valeur impossible lève `ValueError` sans rien consommer.

## Lire la réponse

`ask` rend une `Answer`, qui est le JSON de l'API (un `dict`, sérialisable tel quel) lisible aussi par attributs typés.

| Champ | Contenu |
|---|---|
| `answer` | réponse en markdown, sans marqueur interne |
| `title` | titre court de l'échange |
| `key_points` | puces à polarité : `polarity` (`positive` = recommandé, `negative` = à éviter), `text` |
| `patient_advice` | discours prêt à tenir au patient |
| `associated_sale` | conseil de vente associée |
| `suggestions` | pistes d'approfondissement |
| `sources` | références par base interrogée ; `all_sources()` les donne à plat, sans doublon |
| `tools_used` | bases interrogées |
| `status` | `ok` ou `clarification_needed` (voir plus bas) |
| `conversation_id` | id `conv_…` d'une conversation gardée |
| `usage` | `elapsed_ms`, `daily_requests_used`, `daily_requests_limit` |
| `id` | identifiant de requête `req_…`, à joindre à toute demande de support |
| `rate_limit` | en-têtes de quota de la réponse : `limit`, `remaining`, `reset_at` (hors JSON) |

`reponse.to_dict()` donne une copie en dicts simples, `reponse.to_json()` le JSON.

## Demande de précision

Quand un mot de la question est ambigu, l'API ne répond pas au fond : elle demande une précision et propose des corrections.

```python
reponse = client.ask("Collyre pour l'oeille ?")
if reponse.needs_clarification:
    c = reponse.clarification
    print(c.message, c.corrections)          # ['œil', 'oreille']
    reponse = client.ask(c.corrected_question(reponse.question, c.corrections[0]))
```

`corrected_question` remplace le mot ambigu comme le fait le chat de PharmAssistant.

## Citer les sources dans le texte

Avec `citations="inline"`, chaque fait de la réponse finit par le repère de sa source (`[S1]`, `[S2][S4]`). Une question qu'aucune source ne couvre reçoit un aveu, jamais une réponse de mémoire.

```python
reponse = client.ask("Ibuprofène et grossesse ?", citations="inline")

for citation in reponse.iter_citations():      # dans l'ordre du texte
    ref = citation.reference                    # titre, url, base
    extrait = citation.passage                  # phrase source, ou fiche de données
    print(citation.n, ref.title if ref else "", extrait.quote if extrait else "")

texte_sans_reperes = reponse.answer_without_markers()
```

`references` donne le registre numéroté (`[S3]` renvoie à la référence `n = 3` ; `empty` signale une base interrogée qui n'a rien rendu). `passages` donne, repère par repère, l'extrait de prose (`quote`, `before`, `after`) ou la fiche de données (`record`, lignes `label` / `value`). Un repère dont l'extrait n'a pas été retrouvé avec assez de certitude n'a pas de passage : jamais un extrait à côté.

## Réponse en flux

```python
with client.ask_stream("Amoxicilline et allaitement ?") as flux:
    for texte in flux.text_stream:
        print(texte, end="", flush=True)
    reponse = flux.get_final_answer()    # la même Answer que ask()
```

Pour suivre chaque étape :

```python
with client.ask_stream("Amoxicilline et allaitement ?", citations="inline") as flux:
    for evenement in flux:
        if evenement.event == "status":
            print("…", evenement.state)          # routing, tools_running, generating
        elif evenement.event == "references":
            print(flux.references)               # registre, avant le premier mot
        elif evenement.event == "chunk":
            print(evenement.text, end="")
        elif evenement.event == "done":
            reponse = evenement.answer
```

Chaque événement se déballe aussi en `event, data`. Les blocs « Au comptoir » et vente associée n'arrivent pas dans le texte du flux : ils sont dans la réponse finale. Un refus avant la rédaction (clé, quota, conversation inconnue) est levé dès l'appel ; une erreur pendant la rédaction lève l'exception typée, et la requête n'est pas décomptée.

## Conversations

Historique chez vous, rien n'est gardé par le serveur :

```python
conv = client.start_conversation()
conv.ask("Amoxicilline et allaitement ?")
conv.ask("Et pendant la grossesse ?")
```

Conversation gardée par le serveur jusqu'à 90 jours après la dernière activité :

```python
conv = client.start_conversation(store=True, citations="inline")
conv.ask("Amoxicilline et allaitement ?")
identifiant = conv.id                      # conv_…, à conserver

suite = client.resume_conversation(identifiant)
suite.ask("Et chez le nourrisson de moins d'un mois ?")
suite.delete()                             # effacée aussitôt
```

Les options passées à `start_conversation` (mode, citations…) s'appliquent à chaque tour. Gestion directe :

```python
for c in client.conversations.list(limit=20):
    print(c.id, c.updated_at, c.title)
detail = client.conversations.retrieve("conv_…")
client.conversations.delete("conv_…")
```

## Client asynchrone

```python
import asyncio
from pharmassistant import AsyncPharmAssistant

async def main():
    async with AsyncPharmAssistant() as client:
        reponse = await client.ask("Amoxicilline et allaitement ?")

        flux = await client.ask_stream("Et pendant la grossesse ?")
        async with flux:
            async for texte in flux.text_stream:
                print(texte, end="")

asyncio.run(main())
```

Toutes les méthodes du client synchrone existent, à attendre. Pour plusieurs questions en parallèle, `asyncio.gather` en restant sous l'anti-rafale de la clé.

## Erreurs

Toutes les erreurs héritent de `PharmAssistantError` et portent `code` (code machine stable), `message`, `status` (HTTP), `request_id`, `details` (sur les 422) et `aide` : ce qu'il faut faire.

```
PharmAssistantError
├── ConfigurationError          clé absente ou mal formée (aussi ValueError)
├── APIConnectionError          réseau, flux coupé
│   └── APITimeoutError         délai dépassé
└── APIStatusError
    ├── AuthenticationError     401
    ├── PermissionDeniedError   403
    ├── NotFoundError           404
    │   └── ConversationNotFoundError
    ├── InvalidRequestError     422
    ├── RateLimitError          429 rafale, .retry_after
    ├── QuotaExceededError      429 plafond, .reset_at
    └── ServerError             5xx
```

```python
from pharmassistant import PharmAssistantError, QuotaExceededError

try:
    reponse = client.ask("Amoxicilline et allaitement ?")
except QuotaExceededError as e:
    print("Plafond atteint, retour à", e.reset_at)
except PharmAssistantError as e:
    print(e)          # message, aide et identifiant de requête
```

| Code | HTTP | Sens |
|---|---|---|
| `missing_api_key` | 401 | aucune clé envoyée |
| `invalid_api_key` | 401 | clé inconnue ou mal formée |
| `revoked_api_key` | 401 | clé révoquée |
| `expired_api_key` | 401 | clé périmée |
| `pharmacy_not_found` | 403 | pharmacie liée introuvable |
| `pharmacy_suspended` | 403 | pharmacie liée suspendue |
| `scope_denied` | 403 | portée manquante (`ask:detailed`) |
| `conversation_not_found` | 404 | conversation inconnue, supprimée ou purgée |
| `not_found` | 404 | adresse inconnue de l'API |
| `invalid_request` | 422 | requête refusée, détail dans `details` |
| `rate_limited` | 429 | anti-rafale, réessayé seul |
| `daily_limit_reached` | 429 | plafond journalier |
| `monthly_limit_reached` | 429 | plafond mensuel |
| `detailed_limit_reached` | 429 | sous-plafond du mode Détaillé |
| `internal_error` | 500 | erreur interne, réessayée seule |
| `generation_failed` | 502 | rédaction en échec, réessayée seule |
| `empty_response` | 502 | réponse vide, réessayée seule |
| `connection_error` | | serveur injoignable |
| `timeout` | | délai dépassé |
| `stream_interrupted` | | flux coupé avant la fin |

Détail et conduite à tenir pour chaque code : `pharmassistant.aide("daily_limit_reached")`.

## Quotas et nouveaux essais

La facturation compte des requêtes, pas des jetons, et une requête refusée ou en échec (429, 500, 502, erreur pendant le flux) n'est jamais décomptée. Le client réessaie donc seul, `max_retries` fois (2 par défaut), quand rien ne peut avoir été décompté :

- connexion impossible, avec un délai croissant (0,5 s, 1 s, 2 s…) ;
- `rate_limited`, après l'en-tête `Retry-After` (60 s au plus) ;
- 500, 502, 503, 504, avec un délai croissant.

Il ne réessaie jamais un plafond atteint, un refus 4xx, ni une question dont la lecture a été coupée (la requête a pu être décomptée).

```python
client = PharmAssistant(max_retries=0)                 # aucun nouvel essai
client.with_options(max_retries=5).ask("…")            # pour un appel
print(client.me().daily_remaining)                     # requêtes restantes aujourd'hui
```

## Configuration

```python
PharmAssistant(
    api_key=None,           # défaut : PHARMASSISTANT_API_KEY
    base_url=None,          # défaut : PHARMASSISTANT_API_URL, sinon https://api.pharmassistant.fr
    timeout=300,            # secondes ou httpx.Timeout ; connexion 10 s
    max_retries=2,
    default_headers=None,   # en-têtes ajoutés à chaque requête
    http_client=None,       # httpx.Client fourni : proxy, certificats
)
```

| Variable | Effet |
|---|---|
| `PHARMASSISTANT_API_KEY` | clé |
| `PHARMASSISTANT_API_URL` | autre adresse d'API |
| `PHARMASSISTANT_LOG` | `debug`, `info` ou `warning` : journal sur la sortie d'erreur |
| `HTTPS_PROXY`, `SSL_CERT_FILE` | proxy et certificats, lus par httpx |

Le mode Détaillé peut dépasser deux minutes : augmentez `timeout`, ou passez par le flux. Derrière un proxy d'entreprise :

```python
import httpx
client = PharmAssistant(http_client=httpx.Client(proxy="http://proxy.interne:3128"))
```

`client.with_options(timeout=600)` rend une copie réglée autrement, sur la même connexion. Le journal passe par `logging.getLogger("pharmassistant")`, muet par défaut ; la clé n'y paraît jamais. Le client est sûr entre fils d'exécution et se ferme par `close()` ou `with`.

## Ligne de commande

```bash
pharmassistant "Amoxicilline et allaitement ?"         # en flux dans un terminal
pharmassistant question -d --inline "Tramadol et sertraline ?"
echo "Ibuprofène et grossesse ?" | pharmassistant question --json
pharmassistant discussion                              # échange suivi au clavier
pharmassistant conversations                           # liste | voir ID | supprimer ID
pharmassistant cle                                     # plafonds et consommation
pharmassistant service                                 # disponibilité de l'API
pharmassistant aide flux                               # aide par sujet
```

Chaque commande a son aide (`pharmassistant question --help`). En discussion : `/aide`, `/nouvelle`, `/detaille`, `/inline`, `/sources`, `/id`, `/quitter` ; un numéro choisit une correction proposée. Sans `--conserver`, l'historique reste sur le poste.

Codes de sortie : 0 réponse rendue, 1 erreur (API, réseau, configuration), 2 commande mal formée, 3 précision demandée, 130 interruption.

## Aide intégrée

```python
import pharmassistant
pharmassistant.aide()                 # sommaire
pharmassistant.aide("citations")      # un sujet
pharmassistant.aide("scope_denied")   # un code d'erreur
help(pharmassistant.PharmAssistant.ask)
```

Sujets : demarrage, cle, questions, precision, conversations, flux, citations, erreurs, quotas, reessais, configuration, asynchrone, commande, confidentialite.

## Données patient

Les conditions d'utilisation de l'API interdisent d'y envoyer toute donnée identifiant un patient : nom, date de naissance, numéro de sécurité sociale, adresse, ordonnance nominative. Posez la question sur la situation clinique, jamais sur la personne. Traitement des données : [politique de confidentialité](https://pharmassistant.fr/privacy).

## Fichier unique sans installation

L'API sert aussi un client minimal en un fichier, sans dépendance : `curl -O https://api.pharmassistant.fr/clients/pharmassistant.py`. Le code écrit pour lui fonctionne avec ce paquet : `ask` et `ask_stream` prennent les mêmes paramètres, la réponse reste un `dict`, le flux se déballe en `event, data`, et `conversations()`, `conversation(id)`, `delete_conversation(id)` sont gardés.

## Licence

MIT, voir [LICENSE](LICENSE). L'usage du service relève des [conditions d'utilisation de l'API](https://pharmassistant.fr/developpeurs).
