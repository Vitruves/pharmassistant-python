# Démarrage

## Installer

```bash
pip install pharmassistant
```

Python 3.9 ou plus récent. Une seule dépendance, [httpx](https://www.python-httpx.org). Le paquet installe aussi la commande [`pharmassistant`](cli.md).

## Obtenir une clé

La clé (`pa_…`) se retire sur le portail dont le lien vous est envoyé par email, après acceptation des [conditions d'utilisation de l'API](https://pharmassistant.fr/developpeurs). Pour en obtenir une : [contact@pharmassistant.fr](mailto:contact@pharmassistant.fr).

Elle n'est montrée qu'une fois. Une clé perdue se régénère depuis le portail, ce qui invalide aussitôt l'ancienne.

## Poser la clé

Le client la lit dans la variable d'environnement `PHARMASSISTANT_API_KEY` :

```bash
export PHARMASSISTANT_API_KEY=pa_votre_cle
```

Vous pouvez aussi la passer au constructeur, lue depuis votre propre configuration :

```python
import os
from pharmassistant import PharmAssistant

client = PharmAssistant(api_key=os.environ["MA_CLE_PHARMASSISTANT"])
```

Jamais dans le code versionné, jamais dans un navigateur ni une application mobile : la clé donne accès au quota de votre intégration. Une clé absente ou mal formée lève [`ConfigurationError`](erreurs.md#les-exceptions) dès la création du client, avant tout appel réseau.

## Première question

```python
from pharmassistant import PharmAssistant

client = PharmAssistant()

reponse = client.ask("Amoxicilline et allaitement ?")

print(reponse.title)
print(reponse.answer)              # markdown, prêt à afficher
print(reponse.patient_advice)      # discours à tenir au patient
for point in reponse.key_points:
    print("✔" if point.is_positive else "✘", point.text)
for source in reponse.all_sources():
    print(source.title, source.url)
```

Tous les champs de la réponse sont décrits dans [Poser une question](questions.md#lire-la-réponse).

## Vérifier sa clé

```python
etat = client.me()
print(etat.name, etat.daily_requests_used, "/", etat.daily_limit)
print("Reste aujourd'hui :", etat.daily_remaining)
```

Ou dans un terminal :

```bash
pharmassistant cle
```

## Fermer le client

Le client garde ses connexions ouvertes pour aller plus vite d'une question à l'autre. Créez-en un seul pour toute l'application et fermez-le à la fin, ou utilisez `with` :

```python
with PharmAssistant() as client:
    reponse = client.ask("Ibuprofène et grossesse ?")
```

Il est sûr entre fils d'exécution : un seul client peut servir tout un serveur web.

## Et ensuite

- Afficher la réponse au fil de l'eau : [Réponse en flux](flux.md).
- Enchaîner les questions : [Conversations](conversations.md).
- Gérer proprement les plafonds et les pannes : [Erreurs, quotas et nouveaux essais](erreurs.md).
- Intégrer dans FastAPI ou Django : [Recettes](recettes.md).
