# Réponse en flux

Une réponse prend quelques secondes, davantage en mode Détaillé. `ask_stream` rend le texte au fil de la rédaction, comme le chat de PharmAssistant. Il prend les mêmes options qu'[`ask`](questions.md#les-options).

## Le plus simple

```python
with client.ask_stream("Amoxicilline et allaitement ?") as flux:
    for texte in flux.text_stream:
        print(texte, end="", flush=True)
    reponse = flux.get_final_answer()

print()
print(reponse.patient_advice)
```

`get_final_answer()` rend la même [`Answer`](questions.md#lire-la-réponse) qu'`ask`. Les blocs « Au comptoir » (`patient_advice`) et vente associée (`associated_sale`), les points clés et les sources n'arrivent pas dans le texte du flux : ils sont dans cette réponse finale.

Toujours ouvrir le flux avec `with`, ou appeler `flux.close()` : la connexion reste sinon ouverte jusqu'au bout de la rédaction.

## Suivre chaque étape

Le flux est une suite d'événements :

| Événement | `data` | Raccourci |
|---|---|---|
| `start` | `id` (= identifiant de requête), `mode`, `question`, `conversation_id` | `flux.request_id` |
| `status` | `state` : `routing` (choix des bases), `tools_running` (consultation), `generating` (rédaction) | `evenement.state` |
| `references` | `references` : registre numéroté, seulement en `citations="inline"`, avant le premier mot | `flux.references` |
| `chunk` | `text` : fragment de la réponse | `evenement.text` |
| `done` | la réponse complète | `evenement.answer`, `flux.answer` |

```python
etats = {"routing": "Choix des sources", "tools_running": "Consultation",
         "generating": "Rédaction"}

with client.ask_stream("Tramadol et sertraline ?", citations="inline") as flux:
    for evenement in flux:
        if evenement.event == "status":
            print(f"[{etats.get(evenement.state, evenement.state)}…]")
        elif evenement.event == "references":
            print(f"{len(flux.references)} sources consultées")
        elif evenement.event == "chunk":
            print(evenement.text, end="", flush=True)
        elif evenement.event == "done":
            reponse = evenement.answer
```

Chaque événement se déballe aussi en `event, data`, comme avec le [fichier unique](fichier-unique.md) :

```python
for event, data in client.ask_stream("Amoxicilline et allaitement ?"):
    if event == "chunk":
        print(data["text"], end="")
```

## Les erreurs

- Un refus avant la rédaction (clé, portée, quota, conversation inconnue) est levé dès l'appel à `ask_stream`, avant tout événement : même exception qu'avec `ask`.
- Une erreur pendant la rédaction arrive comme un événement `error` : le client lève l'[exception typée](erreurs.md#les-exceptions) correspondante, avec l'identifiant de requête. La requête n'est pas décomptée.
- Un flux coupé avant `done` (réseau) lève `APIConnectionError` avec le code `stream_interrupted`. La requête a pu être décomptée.

```python
from pharmassistant import PharmAssistantError

try:
    with client.ask_stream("Amoxicilline et allaitement ?") as flux:
        for texte in flux.text_stream:
            print(texte, end="")
except PharmAssistantError as e:
    print("\n", e)
```

Le client réessaie seul les refus de pré-vol qui ne coûtent rien (rafale, 5xx), jamais un flux commencé. Voir [Nouveaux essais](erreurs.md#nouveaux-essais-automatiques).

## Dans une conversation

```python
conv = client.start_conversation()
with conv.ask_stream("Amoxicilline et allaitement ?") as flux:
    for texte in flux.text_stream:
        print(texte, end="")
# la conversation est à jour dès l'événement done
conv.ask("Et pendant la grossesse ?")
```

## En asynchrone

```python
flux = await client.ask_stream("Amoxicilline et allaitement ?")
async with flux:
    async for texte in flux.text_stream:
        print(texte, end="")
    reponse = await flux.get_final_answer()
```

Voir [Client asynchrone](asynchrone.md), et la recette [Relayer le flux depuis FastAPI](recettes.md#relayer-le-flux-depuis-fastapi).
