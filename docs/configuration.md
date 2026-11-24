# Configuration

## Le constructeur

```python
from pharmassistant import PharmAssistant

client = PharmAssistant(
    api_key=None,            # défaut : PHARMASSISTANT_API_KEY
    base_url=None,           # défaut : PHARMASSISTANT_API_URL, sinon https://api.pharmassistant.fr
    timeout=300,             # secondes ou httpx.Timeout ; connexion : 10 s
    max_retries=2,           # voir erreurs.md
    default_headers=None,    # en-têtes ajoutés à chaque requête
    http_client=None,        # httpx.Client fourni
)
```

`AsyncPharmAssistant` prend les mêmes arguments, avec un `httpx.AsyncClient` pour `http_client`.

## Variables d'environnement

| Variable | Effet |
|---|---|
| `PHARMASSISTANT_API_KEY` | clé, quand `api_key` n'est pas donnée |
| `PHARMASSISTANT_API_URL` | autre adresse d'API |
| `PHARMASSISTANT_LOG` | `debug`, `info` ou `warning` : journal sur la sortie d'erreur, sans rien configurer |
| `HTTPS_PROXY`, `NO_PROXY` | proxy, lus par httpx |
| `SSL_CERT_FILE`, `SSL_CERT_DIR` | certificats d'autorité, lus par httpx |

## Délais

Une réponse standard prend quelques secondes ; le mode Détaillé peut dépasser deux minutes. Le délai par défaut, 300 s, couvre les deux. Pour un appel :

```python
reponse = client.ask("…", mode="detailed", timeout=600)
```

Pour un réglage fin :

```python
import httpx
client = PharmAssistant(timeout=httpx.Timeout(120.0, connect=5.0))
```

Quand l'attente sans nouvelles gêne l'utilisateur, préférez le [flux](flux.md) : le premier mot arrive bien avant la fin. Un délai dépassé lève `APITimeoutError` ; la question n'est pas réessayée seule, car elle a pu être décomptée.

## Variantes d'un client

`with_options` rend une copie réglée autrement, qui partage les connexions de l'original :

```python
lent = client.with_options(timeout=900, max_retries=0)
lent.ask("…", mode="detailed")
```

Fermer la copie ne ferme pas l'original.

## Proxy et certificats d'entreprise

httpx lit `HTTPS_PROXY` et `SSL_CERT_FILE`. Pour un réglage explicite, fournissez votre propre client :

```python
import httpx
from pharmassistant import PharmAssistant

http = httpx.Client(proxy="http://proxy.interne:3128", verify="/etc/ssl/ca-interne.pem")
client = PharmAssistant(http_client=http)
```

Un client fourni n'est pas fermé par `client.close()` : il reste à vous.

## Journal

Le paquet écrit sur le journal standard `pharmassistant`, muet par défaut :

| Niveau | Contenu |
|---|---|
| `DEBUG` | chaque requête : méthode, route, statut, durée, identifiant de requête |
| `WARNING` | chaque [nouvel essai](erreurs.md#nouveaux-essais-automatiques) et son motif |

```python
import logging
logging.basicConfig()
logging.getLogger("pharmassistant").setLevel(logging.DEBUG)
```

ou, sans toucher au code : `PHARMASSISTANT_LOG=debug`. La clé n'apparaît jamais dans le journal, ni le texte des questions.

## En-têtes

Chaque requête porte `User-Agent: pharmassistant-python/<version> (python …; httpx …)`. Pour identifier votre intégration auprès du support :

```python
client = PharmAssistant(default_headers={"X-Integration": "logiciel-officine/4.2"})
```

## Fils d'exécution et processus

Un `PharmAssistant` est sûr entre fils d'exécution : créez-en un pour toute l'application. Après un `fork` (Gunicorn, multiprocessing), créez le client dans chaque processus, pas avant.
