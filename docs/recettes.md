# Recettes

Des intégrations complètes, à adapter. Chacune suppose la clé dans `PHARMASSISTANT_API_KEY`.

## FastAPI

Un client asynchrone pour toute l'application, ouvert et fermé avec elle. Les erreurs de PharmAssistant deviennent des réponses propres pour vos utilisateurs, sans jamais leur exposer un problème de clé.

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from pharmassistant import (APIConnectionError, AsyncPharmAssistant, PharmAssistantError,
                            QuotaExceededError)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPharmAssistant() as client:
        app.state.pharmassistant = client
        yield


app = FastAPI(lifespan=lifespan)


class Question(BaseModel):
    texte: str
    detaille: bool = False


@app.exception_handler(PharmAssistantError)
async def erreur_pharmassistant(request: Request, exc: PharmAssistantError):
    if isinstance(exc, QuotaExceededError):
        statut, message = 429, "Plafond de questions atteint pour aujourd'hui."
    elif isinstance(exc, APIConnectionError):
        statut, message = 503, "Service momentanément injoignable."
    else:
        statut, message = 502, "La question n'a pas pu aboutir."
    return JSONResponse({"erreur": message, "requete": exc.request_id}, status_code=statut)


@app.post("/question")
async def question(corps: Question, request: Request):
    client: AsyncPharmAssistant = request.app.state.pharmassistant
    reponse = await client.ask(corps.texte, mode="detailed" if corps.detaille else "standard")
    return reponse.to_dict()
```

### Relayer le flux depuis FastAPI

Le texte part vers votre interface au fur et à mesure. Un refus de pré-vol (quota, clé) est levé par `ask_stream` avant le premier octet, donc traité par le gestionnaire d'erreurs ci-dessus.

```python
@app.post("/question/flux")
async def question_flux(corps: Question, request: Request):
    client: AsyncPharmAssistant = request.app.state.pharmassistant
    flux = await client.ask_stream(corps.texte)

    async def textes():
        async with flux:
            async for texte in flux.text_stream:
                yield texte

    return StreamingResponse(textes(), media_type="text/plain; charset=utf-8")
```

## Django

Un client synchrone par processus, créé à la première question (sûr avec Gunicorn, qui crée ses processus avant).

```python
# monprojet/pharmassistant_client.py
from functools import lru_cache

from pharmassistant import PharmAssistant


@lru_cache(maxsize=1)
def client() -> PharmAssistant:
    return PharmAssistant()
```

```python
# monapp/views.py
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from monprojet.pharmassistant_client import client
from pharmassistant import PharmAssistantError, QuotaExceededError


@require_POST
def question(request):
    texte = json.loads(request.body)["question"]
    try:
        reponse = client().ask(texte)
    except QuotaExceededError:
        return JsonResponse({"erreur": "Plafond de questions atteint."}, status=429)
    except PharmAssistantError as e:
        return JsonResponse({"erreur": "La question n'a pas pu aboutir.",
                             "requete": e.request_id}, status=502)
    return JsonResponse(reponse.to_dict())
```

## Traiter une liste de questions

Une question par ligne dans `questions.txt`, une réponse JSON par ligne dans `reponses.jsonl`. Le traitement reprend où il s'était arrêté, garde trois questions en vol, et s'interrompt proprement au plafond.

```python
import asyncio
import json
from pathlib import Path

from pharmassistant import AsyncPharmAssistant, PharmAssistantError, QuotaExceededError

ENTREE, SORTIE = Path("questions.txt"), Path("reponses.jsonl")


async def main():
    faites = set()
    if SORTIE.exists():
        faites = {json.loads(ligne)["question"]
                  for ligne in SORTIE.read_text(encoding="utf-8").splitlines()}
    a_faire = [q for q in ENTREE.read_text(encoding="utf-8").splitlines()
               if q.strip() and q not in faites]
    limite, plafond = asyncio.Semaphore(3), asyncio.Event()

    async with AsyncPharmAssistant() as client:
        async def poser(question):
            async with limite:
                if plafond.is_set():
                    return
                try:
                    reponse = await client.ask(question)
                except QuotaExceededError as e:
                    plafond.set()
                    print("Arrêt :", e.aide)
                    return
                except PharmAssistantError as e:
                    print("Échec :", question, e.code)
                    return
                with SORTIE.open("a", encoding="utf-8") as f:
                    f.write(reponse.to_json(indent=None) + "\n")

        await asyncio.gather(*(poser(q) for q in a_faire))
    print(f"{len(a_faire)} questions traitées ou tentées.")


asyncio.run(main())
```

Pour plus de prudence, vérifiez d'abord le reste du jour : `(await client.me()).daily_remaining`.

## Rendre les citations en HTML

Avec `citations="inline"`, chaque repère `[S1]` devient un exposant cliquable vers sa source, puis le markdown est converti (ici avec le paquet `markdown`).

```python
import html

import markdown

from pharmassistant import Answer


def avec_liens(reponse: Answer) -> str:
    texte = reponse.answer or ""
    morceaux, curseur = [], 0
    for c in reponse.iter_citations():
        morceaux.append(texte[curseur:c.start])
        ref = c.reference
        titre = html.escape(ref.title or ref.tool, quote=True) if ref else ""
        if ref is not None and ref.url:
            morceaux.append(f'<sup><a href="{html.escape(ref.url, quote=True)}" '
                            f'title="{titre}">{c.n}</a></sup>')
        else:
            morceaux.append(f'<sup title="{titre}">{c.n}</sup>')
        curseur = c.end
    morceaux.append(texte[curseur:])
    return markdown.markdown("".join(morceaux))
```

Pour montrer l'extrait au survol, `c.passage.quote` (prose) ou `c.passage.record` (fiche) donne le texte de la source : voir [Sources et citations](citations.md#les-extraits).

## Tableau de bord de quota

```python
from pharmassistant import PharmAssistant

with PharmAssistant() as client:
    etat = client.me()

print(f"Clé {etat.name} ({etat.key_hint}), {'active' if etat.active else 'inactive'}")
for libelle, utilise, plafond in (
        ("Aujourd'hui", etat.daily_requests_used, etat.daily_limit),
        ("Détaillé", etat.daily_detailed_used, etat.daily_detailed_limit),
        ("Ce mois", etat.month_requests_used, etat.monthly_limit)):
    if plafond is None:
        print(f"{libelle} : {utilise} (sans plafond)")
    else:
        part = utilise / plafond if plafond else 1
        alerte = "  ⚠ plus de 80 %" if part >= 0.8 else ""
        print(f"{libelle} : {utilise} / {plafond}{alerte}")
if not etat.has_scope("ask:detailed"):
    print("Mode Détaillé non autorisé pour cette clé.")
```

Après chaque question, `reponse.rate_limit.remaining` donne le reste du jour sans appel supplémentaire.

## Tester votre code sans appeler l'API

Fournissez au client un transport httpx factice : vos tests ne consomment rien et ne dépendent pas du réseau.

```python
import httpx

from pharmassistant import PharmAssistant


def faux_serveur(requete: httpx.Request) -> httpx.Response:
    if requete.url.path == "/v1/ask":
        return httpx.Response(200, json={
            "id": "req_test", "status": "ok", "question": "Q ?", "answer": "Réponse factice.",
            "usage": {"elapsed_ms": 1, "daily_requests_used": 1, "daily_requests_limit": None},
        })
    return httpx.Response(404, json={"error": {"code": "not_found", "message": "Inconnu."}})


client = PharmAssistant("pa_test", http_client=httpx.Client(transport=httpx.MockTransport(faux_serveur)))
assert client.ask("Q ?").answer == "Réponse factice."
```

Pour simuler une erreur, rendez l'enveloppe de l'API : `httpx.Response(429, json={"error": {"code": "daily_limit_reached", "message": "…"}})` lève `QuotaExceededError`. Pensez à `max_retries=0` pour simuler un 5xx sans attente.
