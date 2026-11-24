import io
import json
import unittest
from unittest import mock

import httpx
from _outils import CLE, URL, Serveur, clarification, erreur, flux_complet, reponse_ask

from pharmassistant import PharmAssistant
from pharmassistant._cli import main


class Terminal(io.StringIO):
    def isatty(self):
        return True


def lancer(argv, serveur=None, entree="", tty=False):
    sortie, err = (Terminal() if tty else io.StringIO()), io.StringIO()
    stdin = Terminal(entree) if tty else io.StringIO(entree)

    def fabrique(**options):
        options.pop("api_key", None)
        options["base_url"] = URL
        return PharmAssistant(CLE, http_client=httpx.Client(
            transport=httpx.MockTransport(serveur or Serveur(reponse_ask()))), **options)

    code = main(argv, client_factory=fabrique, stdin=stdin, stdout=sortie, stderr=err)
    return code, sortie.getvalue(), err.getvalue()


class TestQuestion(unittest.TestCase):
    def test_raccourci_et_blocs(self):
        serveur = Serveur(reponse_ask())
        code, sortie, _ = lancer(["Amoxicilline", "et", "allaitement", "?"], serveur)
        self.assertEqual(code, 0)
        self.assertEqual(serveur.corps(), {"question": "Amoxicilline et allaitement ?"})
        for attendu in ("Amoxicilline et allaitement", "Au comptoir", "Vous pouvez allaiter.",
                        "Vente associée", "Pour aller plus loin", "Sources", "CRAT : amoxicilline",
                        "req_0001", "4,2 s", "12/100 aujourd'hui"):
            self.assertIn(attendu, sortie)
        self.assertNotIn("\033[", sortie)

    def test_options(self):
        serveur = Serveur(reponse_ask())
        lancer(["question", "-d", "--inline", "--sans-patient", "--sans-vente", "--sans-pistes",
                "--consignes", "Bref.", "--conserver", "Q ?"], serveur)
        self.assertEqual(serveur.corps(), {
            "question": "Q ?", "mode": "detailed", "citations": "inline", "store": True,
            "patient_advice": False, "associated_sale": False, "suggestions": False,
            "instructions": "Bref."})

    def test_json(self):
        code, sortie, _ = lancer(["q", "--json", "Q ?"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie), reponse_ask())

    def test_question_sur_l_entree(self):
        serveur = Serveur(reponse_ask())
        lancer(["question"], serveur, entree="Tramadol et sertraline ?\n")
        self.assertEqual(serveur.corps()["question"], "Tramadol et sertraline ?")

    def test_question_absente_au_clavier(self):
        code, _, err = lancer(["question"], tty=True)
        self.assertEqual(code, 2)
        self.assertIn("Question absente", err)

    def test_flux_dans_un_terminal(self):
        serveur = Serveur(flux_complet())
        code, sortie, _ = lancer(["Q ?", "--sans-couleur"], serveur, tty=True)
        self.assertEqual(code, 0)
        self.assertTrue(serveur.corps()["stream"])
        self.assertIn("Compatible.\n", sortie)
        self.assertEqual(sortie.count("Vous pouvez allaiter."), 1)
        self.assertNotIn("Surveiller le nourrisson", sortie)

    def test_couleurs_dans_un_terminal(self):
        with mock.patch("pharmassistant._cli._console_ansi", return_value=True), \
                mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("NO_COLOR", None)
            _, sortie, _ = lancer(["Q ?", "--sans-flux"], tty=True)
        self.assertIn("\033[1m", sortie)

    def test_references_en_inline(self):
        _, sortie, _ = lancer(["Q ?", "--inline"], Serveur(reponse_ask(citations="inline")))
        self.assertIn("[S1] CRAT", sortie)
        self.assertIn("[S2] lactmed_search : aucun résultat (amoxicillin)", sortie)

    def test_precision_code_3(self):
        code, sortie, _ = lancer(["Collyre pour l'oeille ?"], Serveur(clarification()))
        self.assertEqual(code, 3)
        self.assertIn("1. œil", sortie)
        self.assertIn("2. oreille", sortie)

    def test_erreur_avec_aide(self):
        code, _, err = lancer(["Q ?"], Serveur(erreur(429, "daily_limit_reached", "Plafond.")))
        self.assertEqual(code, 1)
        self.assertIn("Erreur : Plafond. (daily_limit_reached)", err)
        self.assertIn("Aide : Attendez minuit", err)
        self.assertIn("Requête : req_err", err)

    def test_validation_detaillee(self):
        serveur = Serveur(httpx.Response(422, json={"error": {
            "code": "invalid_request", "message": "Corps de requête invalide.",
            "details": [{"loc": ["body", "question"], "msg": "trop longue"}]}}))
        _, _, err = lancer(["Q ?"], serveur)
        self.assertIn("question : trop longue", err)


class TestEncodage(unittest.TestCase):
    def test_sortie_cp1252_ne_plante_pas(self):
        tampon = io.BytesIO()
        sortie = io.TextIOWrapper(tampon, encoding="cp1252")
        serveur = Serveur(reponse_ask(answer="- ✔ Compatible\u202f!"))

        def fabrique(**options):
            return PharmAssistant(CLE, base_url=URL, http_client=httpx.Client(
                transport=httpx.MockTransport(serveur)))

        code = main(["Q ?"], client_factory=fabrique, stdin=io.StringIO(), stdout=sortie,
                    stderr=io.StringIO())
        sortie.flush()
        self.assertEqual(code, 0)
        self.assertIn(b"? Compatible", tampon.getvalue())


class TestAutresCommandes(unittest.TestCase):
    def test_sans_argument_affiche_l_aide(self):
        code, sortie, _ = lancer([])
        self.assertEqual(code, 0)
        self.assertIn("Utilisation : pharmassistant", sortie)

    def test_option_inconnue(self):
        code, _, err = lancer(["question", "--inconnue", "Q ?"])
        self.assertEqual(code, 2)
        self.assertIn("arguments non reconnus : --inconnue", err)

    def test_version_et_aide_de_commande(self):
        code, sortie, _ = lancer(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("pharmassistant 1.", sortie)
        code, sortie, _ = lancer(["question", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("Utilisation : pharmassistant [question] [options] QUESTION", sortie)
        self.assertIn("Options de la réponse :", sortie)

    def test_cle(self):
        serveur = Serveur({"id": "key_1", "name": "Intégration", "key_hint": "pa_ab…",
                           "pharmacy_slug": None, "daily_limit": 100, "monthly_limit": None,
                           "daily_detailed_limit": None, "limits_locked": False, "scopes": None,
                           "active": True, "expires_at": None, "created_at": "2026-07-23",
                           "last_used_at": None, "daily_requests_used": 30,
                           "daily_detailed_used": 0, "month_requests_used": 1200})
        code, sortie, _ = lancer(["cle"], serveur)
        self.assertEqual(code, 0)
        for attendu in ("Intégration", "30 / 100", "70 restantes", "1200 / illimité", "toutes",
                        "réglables au portail", "jamais"):
            self.assertIn(attendu, sortie)

    def test_service(self):
        serveur = Serveur({"status": "ok", "service": "pharmassistant-api", "version": "1.0.0"})
        code, sortie, _ = lancer(["service"], serveur)
        self.assertIn("API en service, version 1.0.0", sortie)

    def test_conversations(self):
        serveur = Serveur({"object": "list", "data": [
            {"id": "conv_1", "title": "Amoxicilline", "message_count": 4,
             "updated_at": "2026-11-24T10:42:07+01:00"}]})
        code, sortie, _ = lancer(["conversations"], serveur)
        self.assertIn("conv_1  2026-11-24 10:42    4 msg  Amoxicilline", sortie)
        serveur = Serveur({"id": "conv_1", "title": "T", "messages": [
            {"role": "user", "content": "Q"}, {"role": "assistant", "content": "R"}]})
        _, sortie, _ = lancer(["conv", "voir", "conv_1"], serveur)
        self.assertIn("Vous", sortie)
        self.assertIn("PharmAssistant", sortie)

    def test_suppression_confirmee(self):
        serveur = Serveur({"id": "conv_1", "deleted": True})
        code, _, err = lancer(["conversations", "supprimer", "conv_1"], serveur)
        self.assertEqual(code, 2)
        self.assertIn("--oui", err)
        self.assertEqual(serveur.requetes, [])
        code, sortie, _ = lancer(["conversations", "supprimer", "conv_1"], serveur, entree="n\n",
                                 tty=True)
        self.assertIn("Rien n'a été supprimé", sortie)
        self.assertEqual(serveur.requetes, [])
        code, sortie, _ = lancer(["conversations", "rm", "conv_1", "--oui"], serveur)
        self.assertIn("supprimée", sortie)
        self.assertEqual(serveur.requetes[0].method, "DELETE")

    def test_action_inconnue(self):
        code, _, err = lancer(["conversations", "effacer", "conv_1"])
        self.assertEqual(code, 2)

    def test_aide(self):
        code, sortie, _ = lancer(["aide", "flux"])
        self.assertEqual(code, 0)
        self.assertIn("Réponse en flux", sortie)
        code, _, err = lancer(["aide", "flu"])
        self.assertEqual(code, 2)
        self.assertIn("flux", err)


class TestDiscussion(unittest.TestCase):
    def test_echange_suivi_et_commandes(self):
        serveur = Serveur(reponse_ask(answer="R1."), reponse_ask(answer="R2."))
        code, sortie, _ = lancer(["discussion"], serveur,
                                 entree="Q1 ?\n/detaille\nQ2 ?\n/sources\n/id\n/inconnue\n/quitter\n")
        self.assertEqual(code, 0)
        self.assertEqual(serveur.corps(1)["mode"], "detailed")
        self.assertEqual(serveur.corps(1)["history"][1]["content"], "R1.")
        self.assertIn("Historique gardé sur ce poste", sortie)
        self.assertIn("Conversation non gardée par le serveur", sortie)
        self.assertIn("Commande inconnue : /inconnue", sortie)

    def test_choix_d_une_correction(self):
        serveur = Serveur(clarification(), reponse_ask())
        lancer(["chat"], serveur, entree="Collyre pour l'oeille ?\n2\n")
        self.assertEqual(serveur.corps(1)["question"], "Collyre pour l'oreille ?")

    def test_conversation_gardee(self):
        serveur = Serveur(reponse_ask(conversation_id="conv_5"))
        _, sortie, _ = lancer(["discussion", "--conserver"], serveur, entree="Q ?\n/id\n")
        self.assertEqual(serveur.corps(0)["store"], True)
        self.assertIn("conv_5", sortie)

    def test_erreur_d_authentification_arrete(self):
        serveur = Serveur(erreur(401, "invalid_api_key"))
        code, _, err = lancer(["discussion"], serveur, entree="Q ?\nQ2 ?\n")
        self.assertEqual(code, 1)
        self.assertEqual(len(serveur.requetes), 1)

    def test_erreur_passagere_continue(self):
        serveur = Serveur(erreur(429, "daily_limit_reached"), reponse_ask(answer="R2."))
        code, sortie, err = lancer(["discussion"], serveur, entree="Q ?\nQ2 ?\n")
        self.assertEqual(code, 0)
        self.assertIn("daily_limit_reached", err)
        self.assertIn("R2.", sortie)


if __name__ == "__main__":
    unittest.main()
