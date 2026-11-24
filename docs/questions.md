# Poser une question

`client.ask(question, **options)` envoie une question et rend une [`Answer`](#lire-la-réponse) complète. Pour recevoir le texte au fil de la rédaction, voir [Réponse en flux](flux.md) : `ask_stream` prend exactement les mêmes options.

## Les options

```python
reponse = client.ask(
    "Tramadol et sertraline ?",
    mode="detailed",
    citations="inline",
    patient_advice=False,
    associated_sale=False,
    suggestions=False,
    timeout=600,
)
```

| Option | Défaut | Effet |
|---|---|---|
| `mode` | `"standard"` | `"detailed"` : analyse exhaustive, entité par entité, plus lente ; exige la portée `ask:detailed` sur la clé et compte sur un éventuel sous-plafond Détaillé |
| `citations` | `"list"` | `"inline"` : repères `[S1]` dans le texte, registre et extraits ; voir [Sources et citations](citations.md) |
| `store` | `False` | `True` : la conversation est gardée par le serveur, la réponse porte `conversation_id` ; voir [Conversations](conversations.md) |
| `conversation_id` | `None` | poursuit une conversation gardée (`conv_…`) |
| `history` | `None` | historique porté par vous ; exclusif de `store` et de `conversation_id` |
| `suggestions` | `True` | `False` : sans pistes d'approfondissement |
| `patient_advice` | `True` | `False` : sans discours patient, le champ reste `None` |
| `associated_sale` | `True` | `False` : sans conseil de vente associée, le champ reste `None` |
| `timeout` | celui du client | délai pour cet appel seulement, en secondes ou `httpx.Timeout` |

La question elle-même fait 4 000 signes au plus. Les options sont vérifiées avant tout envoi : une valeur impossible (mode inconnu, `history` mêlé à `store`, question vide) lève `ValueError` sans rien consommer. Seules les options qui diffèrent du défaut partent dans la requête.

`history` accepte des dicts ou des couples :

```python
reponse = client.ask(
    "Et chez l'enfant ?",
    history=[
        ("user", "Posologie du paracétamol ?"),
        ("assistant", "Chez l'adulte, …"),
    ],
)
```

Le plus souvent, [`start_conversation`](conversations.md) tient cet historique à votre place.

## Lire la réponse

Une `Answer` est le JSON de l'API, tel quel : un `dict`, sérialisable avec `json.dumps`. Chaque champ se lit aussi par attribut, avec son type pour l'éditeur.

```python
reponse["answer"] == reponse.answer     # True
```

| Champ | Type | Contenu |
|---|---|---|
| `answer` | `str` ou `None` | réponse en markdown, sans marqueur interne ; `None` sur une demande de précision |
| `title` | `str` ou `None` | titre court de l'échange |
| `key_points` | liste de `KeyPoint` | puces à polarité : `polarity` (`positive` = recommandé, `negative` = à éviter), `text`, `is_positive` |
| `patient_advice` | `str` ou `None` | discours prêt à tenir au patient (« Au comptoir ») |
| `associated_sale` | `str` ou `None` | conseil de vente associée |
| `suggestions` | liste de `str` | pistes d'approfondissement, à reposer telles quelles |
| `sources` | dict base → liste de `SourceRef` | références par base interrogée |
| `tools_used` | liste de `str` | bases interrogées |
| `citations` | `str` | modèle de citation suivi : `list` ou `inline` |
| `references`, `passages` | listes | registre et extraits, en `citations="inline"` |
| `status` | `str` | `ok` ou `clarification_needed` |
| `clarification` | `Clarification` ou `None` | voir plus bas |
| `conversation_id` | `str` ou `None` | id `conv_…` d'une conversation gardée |
| `mode`, `question`, `created_at` | `str` | rappel de la requête, horodatage ISO 8601 heure de Paris |
| `usage` | `Usage` | `elapsed_ms`, `daily_requests_used`, `daily_requests_limit` |
| `id` | `str` | identifiant de requête `req_…`, à joindre à toute demande de support |

Et, hors du JSON :

| Attribut ou méthode | Rend |
|---|---|
| `rate_limit` | en-têtes de quota de la réponse HTTP : `limit`, `remaining`, `reset_at` (ou `None` pour une clé sans plafond) |
| `needs_clarification` | `True` sur une demande de précision |
| `all_sources()` | toutes les références à plat, sans doublon |
| `iter_citations()`, `reference(n)`, `answer_without_markers()` | voir [Sources et citations](citations.md) |
| `to_dict()`, `to_json()` | copie en dicts simples, JSON indenté |

## Les puces à polarité

Dans `answer`, les puces sont déjà réécrites en `✔` et `✘` lisibles. `key_points` en donne la version structurée, pour un affichage maison :

```python
for point in reponse.key_points:
    couleur = "vert" if point.is_positive else "rouge"
    print(f"[{couleur}] {point.text}")
```

## Demande de précision

Quand un mot de la question est ambigu, l'API ne répond pas au fond : `status` vaut `clarification_needed`, `answer` vaut `None`, et `clarification` propose des corrections.

```python
reponse = client.ask("Collyre pour l'oeille ?")

if reponse.needs_clarification:
    c = reponse.clarification
    print(c.message)                       # à montrer à l'utilisateur
    print(c.corrections)                   # ['œil', 'oreille']
    choix = c.corrections[0]
    reponse = client.ask(c.corrected_question(reponse.question, choix))
```

`corrected_question` remplace le mot ambigu comme le fait le chat de PharmAssistant : première occurrence sans égard à la casse, sinon mot à mot sans égard aux accents, sinon correction ajoutée entre parenthèses. Dans une [conversation](conversations.md), la demande de précision fait partie de l'historique : la question corrigée la suit naturellement.

## Les pistes d'approfondissement

Chaque piste est une question complète, prête à être reposée :

```python
for piste in reponse.suggestions:
    print("→", piste)

suite = client.ask(reponse.suggestions[0])
```

## Sauvegarder une réponse

```python
import json

with open("reponse.json", "w", encoding="utf-8") as f:
    f.write(reponse.to_json())

from pharmassistant import Answer
relue = Answer(json.load(open("reponse.json", encoding="utf-8")))
print(relue.title)
```
