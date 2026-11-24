# Journal des versions

## 1.0.0

Première version publiée sur PyPI.

- Clients `PharmAssistant` (synchrone) et `AsyncPharmAssistant` (asynchrone), mêmes méthodes : `ask`, `ask_stream`, `me`, `health`, `conversations.list / retrieve / delete`, `with_options`.
- Réponses typées (`Answer`, `KeyInfo`…) : le JSON de l'API, lisible par clés comme par attributs ; `iter_citations`, `answer_without_markers`, `all_sources`, `rate_limit`.
- Réponse en flux (`AnswerStream`) : `text_stream`, `get_final_answer`, événements typés qui se déballent en `event, data`.
- Conversations suivies (`start_conversation`, `resume_conversation`), historique chez le client ou gardé par le serveur.
- Demande de précision : `Clarification.corrected_question`, même règle que le chat.
- Erreurs typées, chacune avec son `aide` ; nouveaux essais automatiques sur connexion impossible, rafale et 5xx, jamais sur ce qui a pu être décompté.
- Commande `pharmassistant` : question, discussion, conversations, cle, service, aide.
- Aide intégrée par sujet et par code d'erreur : `pharmassistant.aide()`.
- Compatible avec le code écrit pour le fichier unique servi par l'API.
