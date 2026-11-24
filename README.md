<p align="center">
  <a href="https://pharmassistant.fr">
    <img src="https://raw.githubusercontent.com/Vitruves/pharmassistant-python/main/.github/images/monogramme.png" alt="PharmAssistant" width="96">
  </a>
</p>

<h1 align="center">pharmassistant</h1>

<p align="center">
  Client Python officiel de l'API <a href="https://pharmassistant.fr">PharmAssistant</a>, l'assistant pharmaceutique de l'officine.
</p>

<p align="center">
  <a href="https://pypi.org/project/pharmassistant/"><img src="https://img.shields.io/pypi/v/pharmassistant?color=17693F" alt="Version sur PyPI"></a>
  <a href="https://pypi.org/project/pharmassistant/"><img src="https://img.shields.io/pypi/pyversions/pharmassistant?color=17693F" alt="Versions de Python"></a>
  <a href="https://github.com/Vitruves/pharmassistant-python/actions/workflows/ci.yml"><img src="https://github.com/Vitruves/pharmassistant-python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Vitruves/pharmassistant-python/blob/main/LICENSE"><img src="https://img.shields.io/badge/licence-MIT-17693F" alt="Licence MIT"></a>
</p>

<p align="center">
  <a href="https://github.com/Vitruves/pharmassistant-python/blob/main/docs/README.md">Documentation</a> ·
  <a href="https://github.com/Vitruves/pharmassistant-python/blob/main/docs/reference.md">Référence</a> ·
  <a href="https://github.com/Vitruves/pharmassistant-python/blob/main/docs/recettes.md">Recettes</a> ·
  <a href="https://api.pharmassistant.fr/docs">API HTTP</a>
</p>

---

PharmAssistant répond aux questions du comptoir à partir des bases documentaires de référence, et cite ses sources. Ce paquet en fait quelques lignes de Python : réponses typées, flux, conversations, citations dans le texte, erreurs qui disent quoi faire.

```bash
pip install pharmassistant
```

```python
from pharmassistant import PharmAssistant

client = PharmAssistant()                  # clé lue dans PHARMASSISTANT_API_KEY

reponse = client.ask("Amoxicilline et allaitement ?")

print(reponse.answer)                      # markdown, prêt à afficher
print(reponse.patient_advice)              # discours à tenir au patient
for source in reponse.all_sources():
    print("·", source.title, source.url)
```

Python 3.9 ou plus récent, une seule dépendance ([httpx](https://www.python-httpx.org)). La clé se demande à [contact@pharmassistant.fr](mailto:contact@pharmassistant.fr) : voir [Démarrage](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/demarrage.md).

## En un coup d'œil

### Des réponses typées

Chaque réponse est le JSON de l'API, lisible par attributs avec la complétion de l'éditeur : titre, réponse markdown, points clés à polarité, discours patient, vente associée, pistes, sources, quota.

```python
for point in reponse.key_points:
    print("✔" if point.is_positive else "✘", point.text)
print(reponse.usage.daily_requests_used, "questions posées aujourd'hui")
```

→ [Poser une question](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/questions.md)

### Des sources citées phrase par phrase

```python
reponse = client.ask("Ibuprofène et grossesse ?", citations="inline")

for c in reponse.iter_citations():                       # [S1], [S2]… dans l'ordre du texte
    titre = c.reference.title if c.reference else ""
    print(c.n, titre, "→", c.passage.quote if c.passage else "")
```

Chaque repère renvoie à sa source et à l'extrait qui porte la phrase. Sans source, l'API le dit au lieu de répondre de mémoire.

→ [Sources et citations](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/citations.md)

### La réponse au fil de la rédaction

```python
with client.ask_stream("Tramadol et sertraline ?") as flux:
    for texte in flux.text_stream:
        print(texte, end="", flush=True)
    reponse = flux.get_final_answer()
```

→ [Réponse en flux](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/flux.md)

### Des échanges suivis

```python
conv = client.start_conversation()
conv.ask("Amoxicilline et allaitement ?")
conv.ask("Et pendant la grossesse ?")              # tient compte de la question précédente
```

Historique chez vous, ou gardé par le serveur et repris plus tard (`store=True`).

→ [Conversations](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/conversations.md)

### Des erreurs qui disent quoi faire

```python
from pharmassistant import PharmAssistantError, QuotaExceededError

try:
    reponse = client.ask("Amoxicilline et allaitement ?")
except QuotaExceededError as e:
    print(e.aide)              # « Attendez minuit (heure de Paris), ou relevez le plafond… »
except PharmAssistantError as e:
    print(e.code, e.request_id)
```

Rafales, pannes passagères et coupures réseau sont réessayées seules, jamais ce qui a pu être décompté.

→ [Erreurs, quotas et nouveaux essais](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/erreurs.md)

### Asynchrone

```python
from pharmassistant import AsyncPharmAssistant

async with AsyncPharmAssistant() as client:
    reponse = await client.ask("Amoxicilline et allaitement ?")
```

→ [Client asynchrone](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/asynchrone.md), et les recettes [FastAPI et Django](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/recettes.md)

### Une aide intégrée, et une commande pour essayer

```python
import pharmassistant
pharmassistant.aide("citations")           # aussi : un code d'erreur, ou aide() pour le sommaire
```

```bash
pharmassistant "Amoxicilline et allaitement ?"
pharmassistant aide
```

→ [Ligne de commande](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/cli.md)

## Documentation

| Guide | Pour |
|---|---|
| [Démarrage](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/demarrage.md) | installer, poser la clé, première question |
| [Poser une question](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/questions.md) | options, champs de la réponse, demande de précision |
| [Sources et citations](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/citations.md) | références par base, repères `[S1]`, extraits |
| [Réponse en flux](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/flux.md) | texte au fil de l'eau, étapes, erreurs en cours de flux |
| [Conversations](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/conversations.md) | historique local ou gardé par le serveur |
| [Client asynchrone](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/asynchrone.md) | `asyncio`, questions en parallèle |
| [Erreurs, quotas et nouveaux essais](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/erreurs.md) | chaque exception et chaque code |
| [Configuration](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/configuration.md) | délais, proxy, certificats, journal |
| [Ligne de commande](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/cli.md) | la commande `pharmassistant` |
| [Recettes](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/recettes.md) | FastAPI, Django, lots, rendu HTML, tests sans réseau |
| [Référence](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/reference.md) | chaque classe, méthode et attribut |
| [Venir du fichier unique](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/fichier-unique.md) | passer du `curl -O` au paquet |

## Données patient

Les conditions d'utilisation de l'API interdisent d'y envoyer toute donnée identifiant un patient. Posez la question sur la situation clinique, jamais sur la personne : voir [Données patient](https://github.com/Vitruves/pharmassistant-python/blob/main/docs/confidentialite.md).

## Licence

MIT, voir [LICENSE](https://github.com/Vitruves/pharmassistant-python/blob/main/LICENSE). L'usage du service relève des [conditions d'utilisation de l'API](https://pharmassistant.fr/developpeurs).
