"""Ligne de commande : `pharmassistant` ou `python -m pharmassistant`."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from collections.abc import Sequence
from typing import Any, Callable, TextIO

from ._aide import texte_d_aide
from ._client import PharmAssistant
from ._errors import InvalidRequestError, PharmAssistantError
from ._models import Answer, KeyInfo
from ._version import __version__

OK, ERREUR, USAGE, PRECISION, INTERROMPU = 0, 1, 2, 3, 130

COMMANDES = {
    "question": ("ask", "q"),
    "discussion": ("chat",),
    "conversations": ("conv",),
    "cle": ("clé", "me", "key"),
    "service": ("health",),
    "aide": ("help",),
}
ACTIONS_CONVERSATIONS = {
    "liste": "liste", "list": "liste", "ls": "liste",
    "voir": "voir", "show": "voir",
    "supprimer": "supprimer", "delete": "supprimer", "rm": "supprimer",
}

_TRADUCTIONS = (
    ("the following arguments are required:", "arguments obligatoires manquants :"),
    ("unrecognized arguments:", "arguments non reconnus :"),
    ("invalid choice:", "choix invalide :"),
    ("choose from", "choix possibles :"),
    ("expected one argument", "une valeur est attendue"),
    ("invalid int value:", "nombre entier attendu, reçu"),
    ("invalid float value:", "nombre attendu, reçu"),
    ("not allowed with argument", "incompatible avec"),
    ("argument ", "option "),
)

ClientFactory = Callable[..., PharmAssistant]


class _Formateur(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage: Any, actions: Any, groups: Any, prefix: str | None = None) -> None:
        super().add_usage(usage, actions, groups, "Utilisation : " if prefix is None else prefix)

    def start_section(self, heading: str | None) -> None:
        super().start_section(f"{heading} " if heading else heading)


class _Parseur(argparse.ArgumentParser):
    def __init__(self, *args: Any, aide: bool = True, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _Formateur)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "Arguments"
        self._optionals.title = "Options"
        if aide:
            self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                              help="affiche cette aide")

    def error(self, message: str) -> Any:
        for anglais, francais in _TRADUCTIONS:
            message = message.replace(anglais, francais)
        message = re.sub(r"(?<=[^\s:]):(?=\s)", " :", message)
        self.print_usage(sys.stderr)
        self.exit(USAGE, f"{self.prog} : erreur : {message}\n"
                         f"Aide : {self.prog} --help, ou pharmassistant aide commande\n")


class _Style:
    def __init__(self, actif: bool) -> None:
        self.actif = actif

    def _c(self, code: str, texte: str) -> str:
        return f"\033[{code}m{texte}\033[0m" if self.actif and texte else texte

    def gras(self, t: str) -> str:
        return self._c("1", t)

    def pale(self, t: str) -> str:
        return self._c("2", t)

    def vert(self, t: str) -> str:
        return self._c("32", t)

    def rouge(self, t: str) -> str:
        return self._c("31", t)

    def bleu(self, t: str) -> str:
        return self._c("36", t)


def _nombre(valeur: float) -> str:
    return f"{valeur:.1f}".replace(".", ",")


def _milliers(valeur: int | None) -> str:
    return "illimité" if valeur is None else f"{valeur:,}".replace(",", " ")


class _Sortie:
    def __init__(self, flux: TextIO, err: TextIO, style: _Style) -> None:
        self.flux, self.err, self.s = flux, err, style

    def ecrire(self, texte: str = "", fin: str = "\n") -> None:
        self.flux.write(texte + fin)
        self.flux.flush()

    def erreur(self, exc: PharmAssistantError) -> None:
        tete = exc.message + (f" ({exc.code})" if exc.code else "")
        lignes = [self.s.rouge("Erreur : ") + tete]
        if isinstance(exc, InvalidRequestError) and exc.details:
            for detail in exc.details:
                if isinstance(detail, dict):
                    champ = ".".join(str(x) for x in detail.get("loc", []) if x != "body")
                    lignes.append(f"  {champ or 'corps'} : {detail.get('msg', '')}")
        if exc.aide:
            lignes.append(self.s.gras("Aide : ") + exc.aide)
        if exc.request_id:
            lignes.append(self.s.pale(f"Requête : {exc.request_id}"))
        self.err.write("\n".join(lignes) + "\n")
        self.err.flush()

    def blocs(self, r: Answer, *, corps_affiche: bool) -> None:
        if r.needs_clarification and r.clarification:
            self.precision(r)
            return
        if not corps_affiche:
            if r.title:
                self.ecrire(self.s.gras(r.title))
                self.ecrire()
            self.ecrire(r.answer or "")
        if r.patient_advice:
            self.ecrire()
            self.ecrire(self.s.vert("Au comptoir"))
            self.ecrire(r.patient_advice)
        if r.associated_sale:
            self.ecrire()
            self.ecrire(self.s.vert("Vente associée"))
            self.ecrire(r.associated_sale)
        if r.suggestions:
            self.ecrire()
            self.ecrire(self.s.vert("Pour aller plus loin"))
            for piste in r.suggestions:
                self.ecrire(f"  • {piste}")
        self.sources(r)
        self.pied(r)

    def precision(self, r: Answer) -> None:
        c = r.clarification
        assert c is not None
        self.ecrire(self.s.gras(c.message))
        for i, correction in enumerate(c.corrections, 1):
            self.ecrire(f"  {i}. {correction}")

    def sources(self, r: Answer) -> None:
        if r.citations == "inline" and r.references:
            self.ecrire()
            self.ecrire(self.s.vert("Références"))
            for ref in r.references:
                if ref.empty:
                    texte = f"{ref.tool} : aucun résultat" + (f" ({ref.query})" if ref.query else "")
                else:
                    texte = ref.title or ref.tool
                self.ecrire(f"  {self.s.bleu(ref.marker)} {texte}" +
                            (f"  {self.s.pale(ref.url)}" if ref.url else ""))
            return
        sources = r.all_sources()
        if sources:
            self.ecrire()
            self.ecrire(self.s.vert("Sources"))
            for source in sources:
                self.ecrire(f"  • {source.title}" +
                            (f"  {self.s.pale(source.url)}" if source.url else ""))

    def pied(self, r: Answer) -> None:
        morceaux = [r.id] if r.id else []
        if r.usage.elapsed_ms:
            morceaux.append(f"{_nombre(r.usage.elapsed_ms / 1000)} s")
        if r.usage.daily_requests_limit is not None:
            morceaux.append(f"{r.usage.daily_requests_used}/{r.usage.daily_requests_limit} "
                            "aujourd'hui")
        if r.conversation_id:
            morceaux.append(r.conversation_id)
        if morceaux:
            self.ecrire()
            self.ecrire(self.s.pale(" · ".join(morceaux)))


def _commun() -> _Parseur:
    p = _Parseur(aide=False)
    g = p.add_argument_group("Connexion et affichage")
    g.add_argument("--api-key", metavar="CLE",
                   help="clé pa_… (défaut : PHARMASSISTANT_API_KEY ; préférez la variable, "
                        "une option reste dans l'historique du terminal)")
    g.add_argument("--url", metavar="URL", help="adresse de l'API (défaut : PHARMASSISTANT_API_URL)")
    g.add_argument("--timeout", type=float, metavar="S", help="délai en secondes (défaut 300)")
    g.add_argument("--essais", type=int, metavar="N", dest="max_retries",
                   help="nouveaux essais automatiques (défaut 2, voir aide reessais)")
    g.add_argument("--json", action="store_true", help="sortie JSON brute, pour un script")
    g.add_argument("--sans-couleur", action="store_true", help="aucune couleur (ou NO_COLOR=1)")
    g.add_argument("-v", "--verbeux", action="store_true", help="journal des requêtes sur stderr")
    return p


def _options_question(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Options de la réponse")
    g.add_argument("-d", "--detaille", action="store_true",
                   help="réponse détaillée, exhaustive (portée ask:detailed, plus lente)")
    g.add_argument("--inline", action="store_true",
                   help="repères [S1] dans le texte, résolus en fin de réponse")
    g.add_argument("--sans-patient", action="store_true", help="sans discours patient")
    g.add_argument("--sans-vente", action="store_true", help="sans vente associée")
    g.add_argument("--sans-pistes", action="store_true",
                   help="sans pistes d'approfondissement")
    g.add_argument("--sans-flux", action="store_true",
                   help="attendre la réponse entière au lieu de l'afficher au fil de l'eau")


def _parseur() -> _Parseur:
    commun = _commun()
    racine = _Parseur(
        prog="pharmassistant",
        description="Client de l'API PharmAssistant, l'assistant pharmaceutique pour l'officine.",
        epilog="Exemples :\n"
               "  pharmassistant \"Amoxicilline et allaitement ?\"\n"
               "  pharmassistant question -d --inline \"Tramadol et sertraline ?\"\n"
               "  pharmassistant discussion\n"
               "  pharmassistant cle\n"
               "  pharmassistant aide flux\n\n"
               "Clé : PHARMASSISTANT_API_KEY. Aide détaillée : pharmassistant aide")
    racine.add_argument("-V", "--version", action="version",
                        version=f"pharmassistant {__version__}", help="affiche la version")
    sous = racine.add_subparsers(dest="commande", title="Commandes", metavar="COMMANDE",
                                 parser_class=_Parseur)

    q = sous.add_parser(
        "question", aliases=list(COMMANDES["question"]), parents=[commun],
        usage="pharmassistant [question] [options] QUESTION",
        help="pose une question (commande par défaut)",
        description="Pose une question et affiche la réponse, au fil de l'eau dans un terminal.",
        epilog="Exemples :\n"
               "  pharmassistant question \"Amoxicilline et allaitement ?\"\n"
               "  pharmassistant question --inline \"Ibuprofène et grossesse ?\"\n"
               "  echo \"Tramadol et sertraline ?\" | pharmassistant question --json\n"
               "  pharmassistant question -c conv_… \"Et chez l'enfant ?\"\n\n"
               "Sans texte (ou « - »), la question est lue sur l'entrée standard.\n"
               "Code de sortie 3 : précision demandée (aide precision).")
    q.add_argument("texte", nargs="*", metavar="QUESTION", help="la question, en français")
    _options_question(q)
    g = q.add_argument_group("Conversation")
    g.add_argument("--conserver", action="store_true",
                   help="ouvre une conversation gardée par le serveur (affiche son id)")
    g.add_argument("-c", "--conversation", metavar="ID", help="poursuit la conversation conv_…")

    d = sous.add_parser(
        "discussion", aliases=list(COMMANDES["discussion"]), parents=[commun],
        usage="pharmassistant discussion [options]",
        help="échange suivi, question après question",
        description="Échange suivi au clavier : chaque question poursuit la précédente.\n"
                    "Commandes en cours d'échange : /aide, /nouvelle, /detaille, /inline,\n"
                    "/sources, /id, /quitter (ou Ctrl+D).",
        epilog="Sans --conserver, l'historique reste sur ce poste et disparaît à la sortie.")
    _options_question(d)
    g = d.add_argument_group("Conversation")
    g.add_argument("--conserver", action="store_true",
                   help="conversation gardée par le serveur (reprise possible par son id)")
    g.add_argument("--reprendre", metavar="ID", help="reprend la conversation conv_…")

    c = sous.add_parser(
        "conversations", aliases=list(COMMANDES["conversations"]), parents=[commun],
        usage="pharmassistant conversations [liste | voir ID | supprimer ID] [options]",
        help="liste, relit ou supprime les conversations gardées",
        description="Conversations gardées par le serveur (créées avec --conserver).",
        epilog="Exemples :\n"
               "  pharmassistant conversations\n"
               "  pharmassistant conversations voir conv_…\n"
               "  pharmassistant conversations supprimer conv_… --oui")
    c.add_argument("action", nargs="?", default="liste", metavar="ACTION",
                   help="liste (défaut), voir ou supprimer")
    c.add_argument("id", nargs="?", metavar="ID", help="id conv_… (voir, supprimer)")
    c.add_argument("--limite", type=int, default=50, metavar="N",
                   help="nombre de conversations listées (défaut 50)")
    c.add_argument("--oui", action="store_true", help="supprime sans demander confirmation")

    sous.add_parser("cle", aliases=list(COMMANDES["cle"]), parents=[commun],
                    usage="pharmassistant cle [options]",
                    help="état de la clé : plafonds, consommation",
                    description="État de la clé : plafonds, portées, consommation du jour et du mois.")
    sous.add_parser("service", aliases=list(COMMANDES["service"]), parents=[commun],
                    usage="pharmassistant service [options]",
                    help="disponibilité de l'API",
                    description="Vérifie que l'API répond (sans clé).")
    a = sous.add_parser("aide", aliases=list(COMMANDES["aide"]), help="aide détaillée par sujet",
                        usage="pharmassistant aide [SUJET | CODE]",
                        description="Aide détaillée. Sans sujet : le sommaire.",
                        epilog="Exemples :\n  pharmassistant aide flux\n"
                               "  pharmassistant aide daily_limit_reached")
    a.add_argument("sujet", nargs="?", metavar="SUJET", help="sujet, ou code d'erreur")
    return racine


def _canonique(commande: str | None) -> str | None:
    for nom, alias in COMMANDES.items():
        if commande == nom or commande in alias:
            return nom
    return commande


def _preparer(argv: list[str]) -> list[str]:
    if argv and not argv[0].startswith("-") and _canonique(argv[0]) not in COMMANDES:
        return ["question", *argv]
    return argv


def _client(args: argparse.Namespace, fabrique: ClientFactory) -> PharmAssistant:
    options: dict[str, Any] = {"api_key": args.api_key, "base_url": args.url}
    if args.timeout is not None:
        options["timeout"] = args.timeout
    if args.max_retries is not None:
        options["max_retries"] = args.max_retries
    return fabrique(**options)


def _ask_options(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "mode": "detailed" if args.detaille else "standard",
        "citations": "inline" if args.inline else "list",
        "patient_advice": not args.sans_patient,
        "associated_sale": not args.sans_vente,
        "suggestions": not args.sans_pistes,
    }


def _afficher_flux(client: Any, question: str, options: dict[str, Any], sortie: _Sortie) -> Answer:
    with client.ask_stream(question, **options) as flux:
        ecrit = False
        for evt in flux:
            if evt.event == "chunk":
                sortie.ecrire(evt.text, fin="")
                ecrit = True
            elif evt.event == "status" and not ecrit and sortie.s.actif:
                sortie.err.write(sortie.s.pale(f"\r{_ETATS.get(evt.state or '', '…')}   "))
                sortie.err.flush()
        if sortie.s.actif:
            sortie.err.write("\r" + " " * 40 + "\r")
        reponse: Answer = flux.get_final_answer()
    if ecrit:
        sortie.ecrire()
    sortie.blocs(reponse, corps_affiche=ecrit)
    return reponse


_ETATS = {"routing": "Choix des sources…", "tools_running": "Consultation des sources…",
          "generating": "Rédaction…"}


def _question(args: argparse.Namespace, client: PharmAssistant, sortie: _Sortie,
              entree: TextIO) -> int:
    texte = " ".join(args.texte).strip()
    if texte in ("", "-"):
        if entree.isatty() and texte == "":
            sortie.err.write("Question absente. Exemple : pharmassistant \"Amoxicilline et "
                             "allaitement ?\"\n")
            return USAGE
        texte = entree.read().strip()
    if not texte:
        sortie.err.write("Question vide.\n")
        return USAGE
    options = _ask_options(args)
    if args.conversation:
        options["conversation_id"] = args.conversation
    elif args.conserver:
        options["store"] = True
    if args.json:
        reponse = client.ask(texte, **options)
        sortie.ecrire(reponse.to_json())
    elif args.sans_flux or not sortie.flux.isatty():
        reponse = client.ask(texte, **options)
        sortie.blocs(reponse, corps_affiche=False)
    else:
        reponse = _afficher_flux(client, texte, options, sortie)
    return PRECISION if reponse.needs_clarification else OK


def _discussion(args: argparse.Namespace, client: PharmAssistant, sortie: _Sortie,
                entree: TextIO) -> int:
    options = _ask_options(args)
    if args.reprendre:
        conv: Any = client.resume_conversation(args.reprendre)
    else:
        conv = client.start_conversation(store=args.conserver)
    interactif = entree.isatty()
    flux = not args.sans_flux and sortie.flux.isatty()
    s = sortie.s
    sortie.ecrire(s.pale("Discussion PharmAssistant. /aide pour les commandes, /quitter pour "
                         "sortir." + ("" if conv.store else " Historique gardé sur ce poste.")))
    corrections: list[str] = []
    question_precedente = ""
    while True:
        try:
            ligne = input(s.gras("Vous › ")) if interactif and entree is sys.stdin \
                else _lire(entree, s.gras("Vous › "), sortie)
        except EOFError:
            sortie.ecrire()
            return OK
        ligne = ligne.strip()
        if not ligne:
            continue
        if ligne.startswith("/"):
            if _commande_discussion(ligne, conv, options, sortie):
                return OK
            continue
        if ligne.isdigit() and corrections and 1 <= int(ligne) <= len(corrections):
            derniere = conv.last_answer
            ligne = derniere.clarification.corrected_question(
                question_precedente, corrections[int(ligne) - 1])
            sortie.ecrire(s.pale(f"→ {ligne}"))
        try:
            if flux:
                reponse = _afficher_flux(conv, ligne, options, sortie)
            else:
                reponse = conv.ask(ligne, **options)
                sortie.blocs(reponse, corps_affiche=False)
        except PharmAssistantError as exc:
            sortie.erreur(exc)
            if exc.status in (401, 403) or exc.code == "missing_api_key":
                return ERREUR
            continue
        question_precedente = ligne
        corrections = reponse.clarification.corrections if reponse.needs_clarification \
            and reponse.clarification else []
        if corrections:
            sortie.ecrire(s.pale("Tapez le numéro d'une correction, ou reformulez."))
        sortie.ecrire()


def _lire(entree: TextIO, invite: str, sortie: _Sortie) -> str:
    sortie.ecrire(invite, fin="")
    ligne = entree.readline()
    if not ligne:
        raise EOFError
    return ligne


def _commande_discussion(ligne: str, conv: Any, options: dict[str, Any], sortie: _Sortie) -> bool:
    commande = ligne[1:].split()[0].lower() if ligne[1:].split() else ""
    s = sortie.s
    if commande in ("quitter", "q", "exit", "quit"):
        return True
    if commande in ("aide", "help", "?"):
        sortie.ecrire("/nouvelle   repart de zéro\n/detaille   bascule la réponse détaillée\n"
                      "/inline     bascule les repères [S1] dans le texte\n"
                      "/sources    sources de la dernière réponse\n"
                      "/id         id de la conversation gardée\n/quitter    sortie (ou Ctrl+D)\n"
                      "Un numéro choisit une correction proposée.")
    elif commande in ("nouvelle", "new", "reset"):
        conv.reset()
        sortie.ecrire(s.pale("Nouvelle conversation."))
    elif commande in ("detaille", "détaillé", "detailed"):
        options["mode"] = "standard" if options["mode"] == "detailed" else "detailed"
        sortie.ecrire(s.pale(f"Réponse {'détaillée' if options['mode'] == 'detailed' else 'standard'}."))
    elif commande == "inline":
        options["citations"] = "list" if options["citations"] == "inline" else "inline"
        sortie.ecrire(s.pale("Repères dans le texte." if options["citations"] == "inline"
                             else "Sources en fin de réponse."))
    elif commande == "sources":
        if conv.last_answer is None:
            sortie.ecrire(s.pale("Aucune réponse pour l'instant."))
        else:
            sortie.sources(conv.last_answer)
    elif commande == "id":
        sortie.ecrire(conv.id or s.pale("Conversation non gardée par le serveur (--conserver)."))
    else:
        sortie.ecrire(s.pale(f"Commande inconnue : /{commande}. /aide pour la liste."))
    return False


def _conversations(args: argparse.Namespace, client: PharmAssistant, sortie: _Sortie,
                   entree: TextIO) -> int:
    action = ACTIONS_CONVERSATIONS.get((args.action or "liste").lower())
    if action is None:
        sortie.err.write(f"Action inconnue : {args.action}. Attendu : liste, voir ou supprimer.\n")
        return USAGE
    if action != "liste" and not args.id:
        sortie.err.write(f"Id de conversation attendu : pharmassistant conversations {action} conv_…\n")
        return USAGE
    s = sortie.s
    if action == "liste":
        conversations = client.conversations.list(limit=args.limite)
        if args.json:
            sortie.ecrire(json.dumps(conversations, ensure_ascii=False, indent=2))
        elif not conversations:
            sortie.ecrire(s.pale("Aucune conversation gardée. Ouvrez-en une avec --conserver."))
        else:
            for conv in conversations:
                date = (conv.updated_at or conv.created_at or "")[:16].replace("T", " ")
                sortie.ecrire(f"{s.bleu(conv.id)}  {s.pale(date)}  {conv.message_count:>3} msg  "
                              f"{conv.title or ''}")
        return OK
    if action == "voir":
        detail = client.conversations.retrieve(args.id)
        if args.json:
            sortie.ecrire(detail.to_json())
            return OK
        sortie.ecrire(s.gras(detail.title or detail.id))
        for message in detail.messages:
            auteur = "Vous" if message.role == "user" else "PharmAssistant"
            sortie.ecrire()
            sortie.ecrire(s.vert(auteur) + s.pale(f"  {(message.created_at or '')[:16].replace('T', ' ')}"))
            sortie.ecrire(message.content)
        return OK
    if not args.oui:
        if not entree.isatty():
            sortie.err.write("Suppression définitive : ajoutez --oui pour confirmer.\n")
            return USAGE
        sortie.ecrire(f"Supprimer définitivement {args.id} ? [o/N] ", fin="")
        if entree.readline().strip().lower() not in ("o", "oui", "y", "yes"):
            sortie.ecrire("Rien n'a été supprimé.")
            return OK
    resultat = client.conversations.delete(args.id)
    sortie.ecrire(resultat.to_json() if args.json else f"Conversation {args.id} supprimée.")
    return OK


def _cle(args: argparse.Namespace, client: PharmAssistant, sortie: _Sortie) -> int:
    k: KeyInfo = client.me()
    if args.json:
        sortie.ecrire(k.to_json())
        return OK
    s = sortie.s
    jour = f"{k.daily_requests_used} / {_milliers(k.daily_limit)}"
    if k.daily_remaining is not None:
        jour += s.pale(f"  ({k.daily_remaining} restantes, remise à zéro à minuit)")
    lignes = [
        ("Clé", f"{k.name}  {s.pale(k.key_hint)}"),
        ("État", s.vert("active") if k.active else s.rouge("inactive")),
        ("Pharmacie", k.pharmacy_slug or "aucune"),
        ("Portées", ", ".join(k.scopes) if k.scopes is not None else "toutes"),
        ("Aujourd'hui", jour),
        ("Détaillé", f"{k.daily_detailed_used} / {_milliers(k.daily_detailed_limit)}"),
        ("Ce mois", f"{k.month_requests_used} / {_milliers(k.monthly_limit)}"),
        ("Plafonds", "fixés par PharmAssistant" if k.limits_locked else "réglables au portail"),
        ("Péremption", (k.expires_at or "aucune")[:10]),
        ("Dernier usage", (k.last_used_at or "jamais")[:16].replace("T", " ")),
    ]
    largeur = max(len(t) for t, _ in lignes)
    for titre, valeur in lignes:
        sortie.ecrire(f"{s.gras(titre.ljust(largeur))}  {valeur}")
    return OK


def _service(args: argparse.Namespace, client: PharmAssistant, sortie: _Sortie) -> int:
    h = client.health()
    if args.json:
        sortie.ecrire(h.to_json())
    else:
        sortie.ecrire(f"{sortie.s.vert('API en service')}, version {h.version} ({client.base_url})")
    return OK


def _sans_plantage_d_encodage(canal: TextIO) -> None:
    # Console Windows en cp1252 : « ✔ » remplacé plutôt qu'une UnicodeEncodeError.
    encodage = (getattr(canal, "encoding", None) or "").lower().replace("-", "")
    reconfigurer = getattr(canal, "reconfigure", None)
    if encodage and encodage != "utf8" and reconfigurer is not None:
        reconfigurer(errors="replace")


def _console_ansi() -> bool:
    if sys.platform != "win32":
        return True
    return any(v in os.environ for v in ("WT_SESSION", "ANSICON", "TERM_PROGRAM", "TERM"))


def main(argv: Sequence[str] | None = None, *, client_factory: ClientFactory | None = None,
         stdin: TextIO | None = None, stdout: TextIO | None = None,
         stderr: TextIO | None = None) -> int:
    """Point d'entrée de la commande ; rend le code de sortie."""
    entree, flux, err = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    for canal in (flux, err):
        _sans_plantage_d_encodage(canal)
    brut = list(sys.argv[1:] if argv is None else argv)
    parseur = _parseur()
    if not brut:
        parseur.print_help(flux)
        return OK
    try:
        with contextlib.redirect_stdout(flux), contextlib.redirect_stderr(err):
            args = parseur.parse_args(_preparer(brut))
    except SystemExit as exc:
        return int(exc.code or 0)
    commande = _canonique(args.commande)
    if commande == "aide":
        try:
            flux.write(texte_d_aide(args.sujet) + "\n")
            return OK
        except KeyError as exc:
            err.write(exc.args[0] + "\n")
            return USAGE
    couleur = (flux.isatty() and not args.sans_couleur and not args.json
               and not os.environ.get("NO_COLOR") and _console_ansi())
    sortie = _Sortie(flux, err, _Style(couleur))
    if args.verbeux:
        os.environ.setdefault("PHARMASSISTANT_LOG", "debug")
    try:
        with _client(args, client_factory or PharmAssistant) as client:
            if commande == "question":
                return _question(args, client, sortie, entree)
            if commande == "discussion":
                return _discussion(args, client, sortie, entree)
            if commande == "conversations":
                return _conversations(args, client, sortie, entree)
            if commande == "cle":
                return _cle(args, client, sortie)
            return _service(args, client, sortie)
    except PharmAssistantError as exc:
        sortie.erreur(exc)
        return ERREUR
    except ValueError as exc:
        err.write(f"Erreur : {exc}\n")
        return USAGE
    except KeyboardInterrupt:
        err.write("\nInterrompu.\n")
        return INTERROMPU


def run() -> None:
    sys.exit(main())
