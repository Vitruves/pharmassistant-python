# Ligne de commande

Le paquet installe la commande `pharmassistant`, aussi lançable par `python -m pharmassistant`. Elle sert à essayer l'API, à vérifier une clé, ou à interroger PharmAssistant depuis un script shell.

```bash
export PHARMASSISTANT_API_KEY=pa_votre_cle
pharmassistant "Amoxicilline et allaitement ?"
```

## Commandes

| Commande | Effet |
|---|---|
| `pharmassistant "question"` | pose la question (raccourci de `question`) |
| `pharmassistant question [options] QUESTION` | pose une question, en flux dans un terminal |
| `pharmassistant discussion` | échange suivi au clavier |
| `pharmassistant conversations [liste \| voir ID \| supprimer ID]` | conversations gardées par le serveur |
| `pharmassistant cle` | plafonds, portées et consommation de la clé |
| `pharmassistant service` | disponibilité de l'API |
| `pharmassistant aide [sujet \| code]` | aide détaillée |

Chaque commande a son aide : `pharmassistant question --help`. Les noms anglais marchent aussi : `ask`, `chat`, `me`, `health`, `help`.

## Poser une question

```bash
pharmassistant question -d --inline "Tramadol et sertraline ?"
pharmassistant question --sans-patient --sans-vente "Ibuprofène et grossesse ?"
echo "Paracétamol et alcool ?" | pharmassistant question
pharmassistant question --json "Amoxicilline et allaitement ?" > reponse.json
```

| Option | Effet |
|---|---|
| `-d`, `--detaille` | réponse détaillée (portée `ask:detailed`) |
| `--inline` | repères `[S1]` dans le texte, résolus en fin de réponse |
| `--sans-patient`, `--sans-vente`, `--sans-pistes` | retire le bloc |
| `--sans-flux` | attendre la réponse entière |
| `--conserver` | conversation gardée par le serveur ; son id s'affiche en pied |
| `-c ID`, `--conversation ID` | poursuit la conversation `conv_…` |
| `--json` | la réponse complète en JSON, pour un script |

Sans texte, ou avec `-` à sa place, la question est lue sur l'entrée standard.

## Discussion

```bash
pharmassistant discussion
pharmassistant discussion --conserver -d
pharmassistant discussion --reprendre conv_…
```

Chaque question poursuit la précédente. Sans `--conserver`, l'historique reste sur le poste et disparaît à la sortie. En cours d'échange :

| Saisie | Effet |
|---|---|
| `/aide` | les commandes |
| `/nouvelle` | repart de zéro |
| `/detaille` | bascule la réponse détaillée |
| `/inline` | bascule les repères dans le texte |
| `/sources` | sources de la dernière réponse |
| `/id` | id de la conversation gardée |
| `/quitter`, Ctrl+D | sortie |
| un numéro | choisit une correction proposée après une demande de précision |

## Options communes

| Option | Effet |
|---|---|
| `--api-key CLE` | clé ; préférez la variable, une option reste dans l'historique du terminal |
| `--url URL` | autre adresse d'API |
| `--timeout S` | délai en secondes |
| `--essais N` | [nouveaux essais](erreurs.md#nouveaux-essais-automatiques) automatiques |
| `--sans-couleur` | aucune couleur ; `NO_COLOR=1` aussi |
| `-v`, `--verbeux` | journal des requêtes sur la sortie d'erreur |

## Dans un script shell

Codes de sortie :

| Code | Sens |
|---|---|
| 0 | réponse rendue |
| 1 | erreur d'API, de réseau ou de configuration (message et aide sur la sortie d'erreur) |
| 2 | commande mal formée |
| 3 | précision demandée : la question est ambiguë |
| 130 | interrompu (Ctrl+C) |

```bash
if pharmassistant question --json "$QUESTION" > reponse.json; then
    jq -r .answer reponse.json
elif [ $? -eq 3 ]; then
    jq -r '.clarification.corrections[]' reponse.json
fi
```

## Aide

```bash
pharmassistant aide                     # sommaire des sujets
pharmassistant aide flux
pharmassistant aide daily_limit_reached
pharmassistant aide codes               # tous les codes d'erreur
```

Sujets : demarrage, cle, questions, precision, conversations, flux, citations, erreurs, quotas, reessais, configuration, asynchrone, commande, confidentialite.
