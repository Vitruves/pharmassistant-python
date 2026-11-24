# Client asynchrone

`AsyncPharmAssistant` a les mêmes méthodes que `PharmAssistant`, à attendre avec `await`. C'est le bon choix dans un serveur `asyncio` (FastAPI, Starlette, aiohttp) ou pour poser plusieurs questions en parallèle.

```python
import asyncio
from pharmassistant import AsyncPharmAssistant

async def main():
    async with AsyncPharmAssistant() as client:
        reponse = await client.ask("Amoxicilline et allaitement ?")
        print(reponse.answer)

asyncio.run(main())
```

## Correspondance

| Synchrone | Asynchrone |
|---|---|
| `client.ask(...)` | `await client.ask(...)` |
| `client.ask_stream(...)` | `await client.ask_stream(...)` |
| `with flux:` | `async with flux:` |
| `for texte in flux.text_stream:` | `async for texte in flux.text_stream:` |
| `flux.get_final_answer()` | `await flux.get_final_answer()` |
| `client.me()`, `client.health()` | `await client.me()`, `await client.health()` |
| `client.conversations.list()` | `await client.conversations.list()` |
| `conv.ask(...)` | `await conv.ask(...)` |
| `client.close()` | `await client.close()` |

`start_conversation`, `resume_conversation` et `with_options` ne font aucun appel réseau : ils ne s'attendent pas.

## Flux

```python
flux = await client.ask_stream("Tramadol et sertraline ?", citations="inline")
async with flux:
    async for evenement in flux:
        if evenement.event == "chunk":
            print(evenement.text, end="")
    reponse = flux.answer
```

## Plusieurs questions en parallèle

La clé a un anti-rafale par minute. Bornez le parallélisme avec un sémaphore : le client réessaie de toute façon seul une rafale refusée, mais autant ne pas la provoquer.

```python
import asyncio
from pharmassistant import AsyncPharmAssistant, PharmAssistantError

QUESTIONS = ["Amoxicilline et allaitement ?", "Ibuprofène et grossesse ?",
             "Tramadol et sertraline ?"]

async def poser(client, limite, question):
    async with limite:
        try:
            return question, await client.ask(question)
        except PharmAssistantError as e:
            return question, e

async def main():
    limite = asyncio.Semaphore(3)
    async with AsyncPharmAssistant() as client:
        resultats = await asyncio.gather(*(poser(client, limite, q) for q in QUESTIONS))
    for question, resultat in resultats:
        print(question, "→", resultat.title if not isinstance(resultat, Exception) else resultat.code)

asyncio.run(main())
```

Plus complet : la recette [Traiter une liste de questions](recettes.md#traiter-une-liste-de-questions).

## Un seul client par application

Créez le client au démarrage et fermez-le à l'arrêt : il garde un pool de connexions. Dans FastAPI, cela se fait dans le `lifespan`, voir la recette [FastAPI](recettes.md#fastapi).
