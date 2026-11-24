# Publier une version

## Source

Ce dépôt est l'unique source du paquet. Le fichier servi par l'API (`/clients/pharmassistant.py`) est un autre client, minimal et sans dépendance, qui vit dans le dépôt de l'API et ne passe pas par ici.

La version vit à un seul endroit : `src/pharmassistant/_version.py`. `pyproject.toml` la lit, le `User-Agent` l'envoie, le workflow de publication refuse un tag qui ne lui est pas égal, et un test exige sa section dans `CHANGELOG.md`.

## Vérifier en local

```bash
cd tests && PYTHONPATH=../src python -m unittest discover -s . && cd ..
uvx ruff check src tests
uvx --with httpx mypy
cd tests && PHARMASSISTANT_CONTRAT=1 PYTHONPATH=../src python -m unittest test_contrat   # réseau
```

`test_contrat` confronte le paquet au schéma OpenAPI de l'API en service (champs de requête et de réponse, valeurs permises, routes, événements du flux). Il tourne aussi chaque lundi en CI (`contrat.yml`) : rouge veut dire que l'API a évolué et que le paquet doit suivre.

## Mise en place (une seule fois)

1. PyPI, compte du titulaire : Account settings, Publishing, « Add a new pending publisher » (GitHub) avec PyPI project name `pharmassistant`, owner `Vitruves`, repository `pharmassistant-python`, workflow `publish.yml`, environment `pypi`. Le projet naît à la première publication, aucun jeton à créer.
2. Même chose sur test.pypi.org avec l'environnement `testpypi` (facultatif, pour la répétition).
3. GitHub, Settings, Environments : créer `pypi` (règle conseillée : « Required reviewers » = vous, la publication attend alors votre clic) et `testpypi`.

## Chaque version

1. Changer le paquet, monter `_version.py` (semver : correctif, ajout compatible, rupture), ajouter sa section au `CHANGELOG.md`, vérifier en local.
2. Un paramètre nouveau n'est publié qu'une fois servi par l'API en production : le paquet ne doit jamais annoncer un champ que le serveur ignore.
3. Commiter, pousser : la CI vérifie lint et types, puis teste la wheel de Python 3.9 à 3.15, et sous Windows et macOS.
4. Répétition facultative : Actions, Publication, « Run workflow » publie sur TestPyPI.
5. Release GitHub avec le tag `vX.Y.Z` (égal à `__version__`) : le workflow reteste, vérifie le tag et publie sur PyPI.

Une version publiée sur PyPI ne se remplace jamais : une erreur se corrige par la version suivante.
