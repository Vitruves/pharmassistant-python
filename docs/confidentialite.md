# Données patient

Les [conditions d'utilisation de l'API](https://pharmassistant.fr/developpeurs) interdisent d'y envoyer toute donnée identifiant un patient : nom, prénom, date de naissance, numéro de sécurité sociale, adresse, téléphone, ordonnance nominative, ni aucune combinaison qui permettrait de le reconnaître.

## Poser la question sur la situation, pas sur la personne

| À envoyer | À ne jamais envoyer |
|---|---|
| « Amoxicilline chez une femme allaitante ? » | une question qui nomme la patiente |
| « Posologie du paracétamol chez un enfant de 15 kg ? » | une date de naissance, un numéro de dossier |
| « Interaction entre tramadol et sertraline ? » | le texte d'une ordonnance avec l'en-tête du patient |

Si votre logiciel part d'un dossier patient, construisez la question à partir des seuls éléments cliniques utiles (âge, poids, grossesse, traitements, fonction rénale), jamais en recopiant le dossier.

## Ce que garde PharmAssistant

- Sans `store`, la question et la réponse ne sont pas conservées en conversation.
- Avec `store=True`, la conversation est gardée jusqu'à 90 jours après la dernière activité ; `conversations.delete(id)` ou `conv.delete()` l'efface aussitôt.
- Le paquet n'écrit ni la clé ni le texte des questions dans son [journal](configuration.md#journal).

Traitement des données : [politique de confidentialité](https://pharmassistant.fr/privacy).
