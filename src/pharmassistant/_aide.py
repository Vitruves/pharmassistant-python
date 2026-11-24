"""Aide intégrée : `pharmassistant.aide("sujet")` ou `pharmassistant aide sujet`."""

from __future__ import annotations

import difflib
import textwrap

from ._errors import CODES

SUJETS: dict[str, tuple[str, str]] = {
    "demarrage": ("Premiers pas", """
        Installation :
            pip install pharmassistant

        Clé : définissez PHARMASSISTANT_API_KEY (voir « aide cle »).

        Python :
            from pharmassistant import PharmAssistant

            client = PharmAssistant()
            reponse = client.ask("Amoxicilline et allaitement ?")
            print(reponse.answer)            # markdown
            print(reponse.patient_advice)    # discours pour le patient

        Terminal :
            pharmassistant "Amoxicilline et allaitement ?"
            pharmassistant discussion

        Suite : aide questions, aide conversations, aide flux, aide erreurs.
    """),
    "cle": ("Clé d'API", """
        La clé (pa_…) se retire sur le portail dont le lien vous est envoyé par
        email, après acceptation des conditions d'utilisation de l'API
        (https://pharmassistant.fr/developpeurs). Elle n'est montrée qu'une fois :
        une clé perdue se régénère depuis le portail, ce qui invalide aussitôt
        l'ancienne.

        Où la mettre, du plus sûr au moins sûr :
            1. variable d'environnement PHARMASSISTANT_API_KEY (ou coffre de
               secrets de votre plateforme) ;
            2. PharmAssistant(api_key=...) lue depuis votre configuration ;
            3. jamais dans le code versionné, jamais dans un navigateur.

        État de la clé (plafonds, portées, consommation) :
            client.me()                  pharmassistant cle
    """),
    "questions": ("Poser une question", """
        client.ask(question, **options) rend une Answer (dict lisible par
        attributs : reponse.answer ou reponse["answer"]).

        Options :
            mode="detailed"         analyse exhaustive (portée ask:detailed)
            citations="inline"      repères [S1] dans le texte (aide citations)
            store=True              conversation gardée par le serveur
            conversation_id="conv_…"   poursuit cette conversation
            history=[...]           historique porté par vous
            patient_advice=False    sans discours patient
            associated_sale=False   sans vente associée
            suggestions=False       sans pistes d'approfondissement
            timeout=600             délai pour cet appel

        Champs utiles de la réponse :
            answer, title, key_points (polarité), patient_advice,
            associated_sale, suggestions, sources, tools_used, usage,
            conversation_id, id (req_…, à joindre à toute demande de support),
            rate_limit (en-têtes de quota).

        Aucune donnée identifiant un patient dans les questions : aide
        confidentialite.
    """),
    "precision": ("Demande de précision", """
        Quand un mot de la question est ambigu, la réponse ne répond pas : elle
        demande une précision.

            reponse = client.ask("Collyre pour l'oeille ?")
            if reponse.needs_clarification:
                c = reponse.clarification
                print(c.message)                 # à afficher
                print(c.corrections)             # ["œil", "oreille"]
                nouvelle = c.corrected_question(reponse.question, c.corrections[0])
                reponse = client.ask(nouvelle)

        corrected_question remplace le mot ambigu comme le fait le chat.
        En ligne de commande, le code de sortie vaut 3.
    """),
    "conversations": ("Conversations", """
        Deux façons de poursuivre un échange :

        Historique chez vous (rien n'est gardé par le serveur) :
            conv = client.start_conversation()
            conv.ask("Amoxicilline et allaitement ?")
            conv.ask("Et pendant la grossesse ?")

        Conversation gardée par le serveur (90 jours après la dernière activité) :
            conv = client.start_conversation(store=True)
            conv.ask("Amoxicilline et allaitement ?")
            print(conv.id)                       # conv_…, à conserver
            plus_tard = client.resume_conversation("conv_…")

        Gestion : client.conversations.list(), .retrieve(id), .delete(id)
        Terminal : pharmassistant conversations [liste | voir ID | supprimer ID]

        Options par défaut de chaque tour :
            client.start_conversation(mode="detailed", citations="inline")
    """),
    "flux": ("Réponse en flux", """
        Le texte arrive au fil de la rédaction :

            with client.ask_stream("Amoxicilline et allaitement ?") as flux:
                for texte in flux.text_stream:
                    print(texte, end="", flush=True)
                reponse = flux.get_final_answer()    # Answer complète

        Événements (for evt in flux, ou for event, data in flux) :
            start        id de requête
            status       data["state"] : routing, tools_running, generating
            references   registre des sources (citations="inline")
            chunk        data["text"]
            done         data = Answer complète

        Un événement error lève l'exception typée ; un refus de pré-vol (clé,
        quota) est levé dès l'appel. Asynchrone : aide asynchrone.
    """),
    "citations": ("Citation des sources", """
        citations="list" (défaut) : la réponse ne porte aucune marque ; les
        références sont à part, par base, dans reponse.sources.
            for ref in reponse.all_sources():
                print(ref.title, ref.url)

        citations="inline" : chaque fait finit par le repère de sa source,
        [S1] ou [S2][S4], résolu par reponse.references ; reponse.passages
        donne l'extrait qui porte chaque phrase. Une question qu'aucune source
        ne couvre reçoit un aveu, jamais une réponse de mémoire.
            for c in reponse.iter_citations():
                print(c.n, c.reference.title, c.passage.quote if c.passage else "")
            texte_nu = reponse.answer_without_markers()
    """),
    "erreurs": ("Erreurs", """
        Toutes les erreurs héritent de PharmAssistantError et portent code,
        message, status, request_id, details et aide (que faire).

            PharmAssistantError
              ConfigurationError        clé absente ou mal formée
              APIConnectionError        réseau ; APITimeoutError : délai
              APIStatusError
                AuthenticationError     401
                PermissionDeniedError   403
                NotFoundError           404 ; ConversationNotFoundError
                InvalidRequestError     422
                RateLimitError          429 rafale, .retry_after
                QuotaExceededError      429 plafond, .reset_at
                ServerError             5xx

            from pharmassistant import QuotaExceededError
            try:
                client.ask("…")
            except QuotaExceededError as e:
                print(e.aide, e.reset_at)

        Détail d'un code : aide daily_limit_reached (liste : aide codes).
    """),
    "quotas": ("Quotas et décompte", """
        La facturation compte des requêtes, pas des jetons. Une requête refusée
        ou en échec (429, 500, 502, événement error du flux) n'est jamais
        décomptée.

        Plafonds possibles : journalier (minuit, heure de Paris), mensuel (1er
        du mois), sous-plafond du mode Détaillé, anti-rafale par minute.

        Suivi :
            reponse.rate_limit          limit, remaining, reset_at (UTC)
            reponse.usage               daily_requests_used, daily_requests_limit
            client.me()                 état complet, daily_remaining
    """),
    "reessais": ("Nouveaux essais automatiques", """
        Le client réessaie seul (max_retries=2 par défaut) quand rien ne peut
        avoir été décompté :
            connexion impossible        délai croissant (0,5 s, 1 s, 2 s…)
            429 rate_limited            après l'en-tête Retry-After (60 s max)
            500, 502, 503, 504          délai croissant

        Jamais réessayé seul : plafond atteint, refus 4xx, délai de lecture
        dépassé sur une question (la requête a pu être décomptée).

            PharmAssistant(max_retries=0)            # aucun nouvel essai
            client.with_options(max_retries=5).ask("…")
    """),
    "configuration": ("Configuration", """
        Variables d'environnement :
            PHARMASSISTANT_API_KEY      clé pa_…
            PHARMASSISTANT_API_URL      autre adresse d'API (essais)
            PHARMASSISTANT_LOG          debug, info ou warning : journal sur stderr
            HTTPS_PROXY, SSL_CERT_FILE  proxy et certificats (lus par httpx)

        Constructeur :
            PharmAssistant(api_key=None, base_url=None, timeout=300,
                           max_retries=2, default_headers=None, http_client=None)

        timeout : 300 s par défaut (connexion 10 s). Le mode Détaillé peut
        dépasser deux minutes ; ask_stream évite d'attendre sans nouvelles.

        Client httpx fourni (proxy d'entreprise, certificat interne) :
            import httpx
            client = PharmAssistant(http_client=httpx.Client(proxy="http://proxy:3128"))

        Journal Python : logging.getLogger("pharmassistant"). La clé n'y paraît
        jamais.
    """),
    "asynchrone": ("Client asynchrone", """
        Mêmes méthodes, à attendre :

            from pharmassistant import AsyncPharmAssistant

            async with AsyncPharmAssistant() as client:
                reponse = await client.ask("Amoxicilline et allaitement ?")

                flux = await client.ask_stream("Et pendant la grossesse ?")
                async with flux:
                    async for texte in flux.text_stream:
                        print(texte, end="")

                conv = client.start_conversation()
                await conv.ask("…")

        Plusieurs questions en parallèle : asyncio.gather, en restant sous
        l'anti-rafale de la clé.
    """),
    "commande": ("Ligne de commande", """
        pharmassistant "question"            réponse (en flux dans un terminal)
        pharmassistant question … [options]  même chose, options détaillées
        pharmassistant discussion            échange suivi, au clavier
        pharmassistant conversations         liste | voir ID | supprimer ID
        pharmassistant cle                   état de la clé
        pharmassistant service               disponibilité de l'API
        pharmassistant aide [sujet | code]   cette aide

        Chaque commande a son aide : pharmassistant question --help

        Codes de sortie :
            0   réponse rendue
            1   erreur d'API, de réseau ou de configuration
            2   commande mal formée
            3   précision demandée (question ambiguë)
            130 interrompu (Ctrl+C)
    """),
    "confidentialite": ("Données patient", """
        Les conditions d'utilisation de l'API interdisent d'y envoyer toute
        donnée identifiant un patient : nom, date de naissance, numéro de
        sécurité sociale, adresse, ordonnance nominative.

        Posez la question sur la situation clinique, jamais sur la personne :
            « Amoxicilline chez une femme allaitante ? »

        store=True garde la conversation chez PharmAssistant jusqu'à 90 jours
        après la dernière activité ; conv.delete() ou conversations.delete(id)
        l'efface aussitôt. Traitement des données :
        https://pharmassistant.fr/privacy
    """),
}

ALIAS = {
    "démarrage": "demarrage", "start": "demarrage", "debut": "demarrage",
    "clé": "cle", "key": "cle", "api_key": "cle",
    "question": "questions", "ask": "questions", "options": "questions",
    "précision": "precision", "clarification": "precision",
    "conversation": "conversations",
    "stream": "flux", "streaming": "flux",
    "sources": "citations", "citation": "citations", "inline": "citations",
    "erreur": "erreurs", "errors": "erreurs", "exceptions": "erreurs",
    "quota": "quotas", "limites": "quotas", "plafonds": "quotas",
    "réessais": "reessais", "retries": "reessais", "retry": "reessais",
    "config": "configuration", "proxy": "configuration", "timeout": "configuration",
    "async": "asynchrone", "asyncio": "asynchrone",
    "cli": "commande", "terminal": "commande",
    "confidentialité": "confidentialite", "rgpd": "confidentialite", "patient": "confidentialite",
}


def _fiche_code(code: str) -> str:
    info = CODES[code]
    statut = f"HTTP {info.status}" if info.status else "côté client"
    decompte = "la requête a pu être décomptée" if info.decompte else "non décomptée"
    return (f"{code}  ({statut}, {decompte})\n\n"
            f"{textwrap.fill(info.sens, 76)}\n\n"
            f"{textwrap.fill('Que faire : ' + info.aide, 76, subsequent_indent='  ')}")


def _liste_codes() -> str:
    largeur = max(len(c) for c in CODES)
    lignes = [f"  {code.ljust(largeur)}  {(f'HTTP {i.status}' if i.status else 'client').ljust(8)}  "
              f"{i.sens}" for code, i in CODES.items()]
    return "Codes d'erreur (aide <code> pour le détail) :\n\n" + "\n".join(lignes)


def _sommaire() -> str:
    largeur = max(len(s) for s in SUJETS)
    lignes = [f"  {nom.ljust(largeur)}  {titre}" for nom, (titre, _) in SUJETS.items()]
    return ("Aide de PharmAssistant. Sujets :\n\n" + "\n".join(lignes) +
            "\n\n  codes" + " " * (largeur - 3) + "Liste des codes d'erreur"
            "\n\nPython : pharmassistant.aide(\"flux\")    Terminal : pharmassistant aide flux"
            "\nGuides : https://github.com/Vitruves/pharmassistant-python/blob/main/docs/README.md"
            "\nAPI HTTP : https://api.pharmassistant.fr/docs")


def texte_d_aide(sujet: str | None = None) -> str:
    """Texte d'un sujet d'aide, d'un code d'erreur, ou le sommaire."""
    if not sujet:
        return _sommaire()
    cle = sujet.strip().lower().replace(" ", "_")
    cle = ALIAS.get(cle, cle)
    if cle in SUJETS:
        titre, corps = SUJETS[cle]
        return f"{titre}\n{'=' * len(titre)}\n{textwrap.dedent(corps).strip()}"
    if cle == "codes":
        return _liste_codes()
    if cle in CODES:
        return _fiche_code(cle)
    proches = difflib.get_close_matches(cle, list(SUJETS) + list(ALIAS) + list(CODES), n=3)
    suggestion = f" Vouliez-vous dire : {', '.join(proches)} ?" if proches else ""
    raise KeyError(f"Sujet d'aide inconnu : {sujet!r}.{suggestion}")


def aide(sujet: str | None = None) -> None:
    """Affiche l'aide : aide() pour le sommaire, aide("flux"), aide("rate_limited")."""
    try:
        print(texte_d_aide(sujet))
    except KeyError as exc:
        print(exc.args[0])
        print()
        print(_sommaire())
