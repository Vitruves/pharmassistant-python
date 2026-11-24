# Sources et citations

Chaque réponse est rédigée à partir des bases documentaires interrogées pour la question. Le champ `citations` choisit comment ces sources vous reviennent.

## `citations="list"` (défaut)

La réponse ne porte aucune marque de source. Les références sont rendues à part, par base interrogée :

```python
reponse = client.ask("Amoxicilline et allaitement ?")

for base, references in reponse.sources.items():
    print(base)
    for ref in references:
        print("  ", ref.title, ref.url or "(base locale, sans lien)")

for ref in reponse.all_sources():          # à plat, sans doublon
    print(ref.title)
```

`url` vaut `None` pour une base sans adresse publique.

## `citations="inline"`

Chaque fait de la réponse se termine par le repère de sa source, `[S1]` ou `[S2][S4]`. Une question qu'aucune source ne couvre reçoit un aveu, jamais une réponse de mémoire.

```python
reponse = client.ask("Ibuprofène et grossesse ?", citations="inline")
print(reponse.answer)
# … contre-indiqué à partir du début du sixième mois.[S1][S2]
```

Trois champs résolvent les repères :

| Champ | Contenu |
|---|---|
| `references` | le registre numéroté : `[S3]` renvoie à la `Reference` dont `n` vaut 3 (`tool`, `title`, `url`, `empty`, `query`) |
| `passages` | pour chaque repère, l'extrait de la source qui porte la phrase, apparié par son rang dans le texte (`index`) |
| `answer` | le texte, avec ses repères |

### Parcourir les repères

`iter_citations()` rend chaque repère dans l'ordre du texte, avec sa référence et son extrait déjà appariés :

```python
for c in reponse.iter_citations():
    ref = c.reference                  # Reference, ou None
    extrait = c.passage                # Passage, ou None
    print(f"[S{c.n}] repère n° {c.rank} aux signes {c.start}-{c.end}")
    if ref:
        print("   source :", ref.title, ref.url)
    if extrait and extrait.quote:
        print("   extrait :", extrait.quote)
```

`start` et `end` sont les positions du repère dans `answer` : de quoi le remplacer par un lien, voir la recette [Rendre les citations en HTML](recettes.md#rendre-les-citations-en-html).

### Les extraits

Un `Passage` prend deux formes exclusives :

- de la prose : `quote`, avec son contexte `before` et `after` ;
- une fiche de données (`is_record` vaut `True`) : `record`, liste de lignes `label` / `value`, `cited` marquant celles qui portent un mot de la phrase, et `record_title`.

```python
for p in reponse.passages:
    if p.is_record:
        print(p.record_title)
        for ligne in p.record:
            marque = "→" if ligne.cited else " "
            print(f" {marque} {ligne.label} : {ligne.value}")
    else:
        print(f"…{p.before or ''}«{p.quote}»{p.after or ''}…")
```

Un repère dont l'extrait n'a pas été retrouvé avec assez de certitude n'a pas de passage : jamais un extrait à côté. L'extrait vient de la copie du texte fournie au moteur, pas d'une relecture de la page d'origine.

### Bases interrogées sans résultat

Une référence dont `empty` vaut `True` est une base consultée qui n'a rien rendu ; `query` dit ce qui a été cherché. La phrase qui la cite rapporte cette absence (« aucune donnée dans… »), ce qui est une information en soi.

```python
for ref in reponse.references:
    if ref.empty:
        print(f"{ref.marker} {ref.tool} : rien sur « {ref.query} »")
```

### Le texte sans repères

```python
texte = reponse.answer_without_markers()
```

Utile pour une synthèse vocale, un SMS, ou un historique de conversation : c'est d'ailleurs ce que fait [`start_conversation`](conversations.md) pour l'historique local.

## En flux

Avec `ask_stream(..., citations="inline")`, le registre arrive avant le premier mot, dans l'événement `references` : vous pouvez préparer l'affichage des sources pendant que le texte se rédige. Voir [Réponse en flux](flux.md#suivre-chaque-étape).
