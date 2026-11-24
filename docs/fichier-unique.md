# Venir du fichier unique

L'API sert aussi un client minimal en un seul fichier, sans dépendance :

```bash
curl -O https://api.pharmassistant.fr/clients/pharmassistant.py
```

Le paquet le remplace sans rien réécrire : même nom de module, même classe, mêmes méthodes, mêmes paramètres.

## Passer au paquet

1. Supprimez `pharmassistant.py` de votre projet : il masquerait le paquet installé.
2. `pip install pharmassistant`, et ajoutez `pharmassistant` à vos dépendances.
3. C'est tout. Ce code fonctionne à l'identique avec les deux :

```python
from pharmassistant import PharmAssistant, PharmAssistantError

client = PharmAssistant("pa_votre_cle")
reponse = client.ask("Amoxicilline et allaitement ?", store=True)
print(reponse["answer"])

for event, data in client.ask_stream("Et pendant la grossesse ?",
                                     conversation_id=reponse["conversation_id"]):
    if event == "chunk":
        print(data["text"], end="")

client.conversations(limit=10)
client.conversation(reponse["conversation_id"])
client.delete_conversation(reponse["conversation_id"])

try:
    client.ask("…")
except PharmAssistantError as e:
    print(e.status, e.code, e.message)
```

## Ce qui change

| | Fichier unique | Paquet |
|---|---|---|
| Python | 3.8+ | 3.9+ |
| Dépendances | aucune | httpx |
| Mise à jour | retélécharger le fichier | `pip install -U pharmassistant` |
| Réponses | `dict` | `dict` lisible aussi par attributs, typé |
| Erreurs | `PharmAssistantError` seule | sous-classes par cas, plus `aide` et `request_id` |
| Nouveaux essais | aucun | rafale, 5xx, connexion impossible ; `max_retries=0` pour l'ancien comportement |
| Flux | tuples `(event, data)` | les mêmes, plus `text_stream` et `get_final_answer()` |
| Asynchrone | non | `AsyncPharmAssistant` |
| Conversations suivies, précision, citations | à la main | [`start_conversation`](conversations.md), [`corrected_question`](questions.md#demande-de-précision), [`iter_citations`](citations.md) |
| Commande et aide | `python pharmassistant.py "question"` | [`pharmassistant`](cli.md), `pharmassistant.aide()` |

Le fichier unique reste servi et maintenu pour qui ne peut rien installer.
