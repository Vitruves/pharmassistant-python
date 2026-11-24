# Documentation de pharmassistant

Client Python officiel de l'API PharmAssistant. Chaque page traite un sujet de bout en bout, avec des exemples prêts à copier.

## Guides

| Page | Pour |
|---|---|
| [Démarrage](demarrage.md) | installer, poser une clé, première question en trente secondes |
| [Poser une question](questions.md) | toutes les options d'`ask`, lire la réponse, demande de précision |
| [Sources et citations](citations.md) | références par base, repères `[S1]` dans le texte, extraits qui portent chaque phrase |
| [Réponse en flux](flux.md) | afficher la réponse au fil de la rédaction, suivre chaque étape |
| [Conversations](conversations.md) | poursuivre un échange, historique chez vous ou gardé par le serveur |
| [Client asynchrone](asynchrone.md) | `asyncio`, serveurs web, questions en parallèle |
| [Erreurs, quotas et nouveaux essais](erreurs.md) | chaque exception, chaque code, ce qui est décompté, ce qui est réessayé |
| [Configuration](configuration.md) | délais, proxy, certificats, journal, client httpx fourni |
| [Ligne de commande](cli.md) | la commande `pharmassistant` et son aide |

## Pour aller plus loin

| Page | Pour |
|---|---|
| [Recettes](recettes.md) | FastAPI, Django, traitement par lots, rendu HTML des citations, tableau de bord de quota |
| [Référence](reference.md) | chaque classe, méthode et attribut public |
| [Venir du fichier unique](fichier-unique.md) | passer du `curl -O` au paquet sans rien réécrire |
| [Données patient](confidentialite.md) | ce qui ne doit jamais partir vers l'API |

## Aide sans quitter le code

La même aide est intégrée au paquet :

```python
import pharmassistant
pharmassistant.aide()                  # sommaire
pharmassistant.aide("flux")            # un sujet
pharmassistant.aide("scope_denied")    # un code d'erreur
```

```bash
pharmassistant aide citations
```

Le contrat HTTP complet (routes, schémas, en-têtes) est décrit sur [api.pharmassistant.fr/docs](https://api.pharmassistant.fr/docs).
