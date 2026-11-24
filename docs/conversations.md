# Conversations

Par défaut, chaque question est indépendante. Pour qu'une question tienne compte des précédentes (« Et pendant la grossesse ? »), il faut une conversation. Deux façons de la tenir :

| | Historique chez vous | Gardée par le serveur |
|---|---|---|
| Ouverture | `client.start_conversation()` | `client.start_conversation(store=True)` |
| Ce qui part à chaque tour | la question et l'historique récent | la question et l'id `conv_…` |
| Conservation chez PharmAssistant | rien | jusqu'à 90 jours après la dernière activité |
| Reprise plus tard, ailleurs | à vous de garder l'historique | `client.resume_conversation(id)` |
| Relecture et suppression par l'API | non | `client.conversations` |

## Historique chez vous

```python
conv = client.start_conversation()

conv.ask("Amoxicilline et allaitement ?")
reponse = conv.ask("Et pendant la grossesse ?")

print(conv.history)          # [{"role": "user", "content": …}, …]
```

L'historique garde les 12 derniers échanges, comme le serveur. Les repères `[S1]` en sont retirés, et une demande de précision y figure pour que la question corrigée la suive. `conv.reset()` repart de zéro.

Pour garder l'historique d'une session à l'autre, sauvegardez `conv.history` et repassez-le en `history` :

```python
historique = conv.history
reponse = client.ask("Et chez l'enfant ?", history=historique)
```

## Gardée par le serveur

```python
conv = client.start_conversation(store=True)
conv.ask("Amoxicilline et allaitement ?")
identifiant = conv.id                      # conv_…, à conserver

# plus tard, dans un autre processus
suite = client.resume_conversation(identifiant)
suite.ask("Et chez le nourrisson de moins d'un mois ?")
```

`conv.id` vaut `None` jusqu'à la première réponse. Une conversation inconnue (supprimée, purgée après 90 jours d'inactivité, ou appartenant à une autre clé) lève [`ConversationNotFoundError`](erreurs.md#les-exceptions), sans décompte.

## Options par défaut

Les options passées à l'ouverture s'appliquent à chaque tour ; celles d'un tour les complètent :

```python
conv = client.start_conversation(mode="detailed", citations="inline", associated_sale=False)
conv.ask("Tramadol et sertraline ?")
conv.ask("Et avec le millepertuis ?", mode="standard")
```

`store`, `history` et `conversation_id` sont gérés par la conversation : les passer lève `ValueError`.

## Gérer les conversations gardées

```python
for c in client.conversations.list(limit=20):      # la plus récemment active d'abord
    print(c.id, c.updated_at, c.message_count, c.title)

detail = client.conversations.retrieve("conv_…")
for message in detail.messages:
    print(message.role, ":", message.content[:80])

client.conversations.delete("conv_…")              # immédiat et définitif
```

Depuis une conversation ouverte : `conv.delete()` l'efface côté serveur et repart à zéro.

Dans un terminal : `pharmassistant conversations`, `pharmassistant conversations voir conv_…`, `pharmassistant conversations supprimer conv_…`. Voir [Ligne de commande](cli.md).

## Sans l'objet conversation

Les mêmes mécanismes existent directement sur `ask` :

```python
ouverture = client.ask("Amoxicilline et allaitement ?", store=True)
suite = client.ask("Et pendant la grossesse ?", conversation_id=ouverture.conversation_id)
```

## En flux et en asynchrone

`conv.ask_stream(...)` met la conversation à jour dès l'événement `done`. Le client asynchrone a les mêmes méthodes, à attendre : voir [Client asynchrone](asynchrone.md).
