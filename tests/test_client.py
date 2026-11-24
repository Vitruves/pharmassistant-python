import os
import unittest
from unittest import mock

import httpx
from _outils import CLE, URL, Serveur, client, reponse_ask

from pharmassistant import (
    Answer,
    ConfigurationError,
    ConversationDetail,
    KeyInfo,
    PharmAssistant,
    __version__,
)


class TestConfiguration(unittest.TestCase):
    def test_cle_lue_dans_l_environnement(self):
        with mock.patch.dict(os.environ, {"PHARMASSISTANT_API_KEY": CLE}):
            with PharmAssistant(base_url=URL) as c:
                self.assertEqual(c._opts.api_key, CLE)

    def test_cle_absente_ou_mal_formee(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError) as ctx:
                PharmAssistant()
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.assertIn("PHARMASSISTANT_API_KEY", ctx.exception.aide)
        self.assertIsInstance(ctx.exception, ValueError)
        with self.assertRaises(ConfigurationError) as ctx:
            PharmAssistant("sk_mauvaise_cle_123")
        self.assertNotIn("mauvaise_cle_123", str(ctx.exception))

    def test_url_et_delais(self):
        with mock.patch.dict(os.environ, {"PHARMASSISTANT_API_URL": "https://autre/"}):
            with PharmAssistant(CLE) as c:
                self.assertEqual(c.base_url, "https://autre")
                self.assertEqual(c.timeout.read, 300.0)
                self.assertEqual(c.timeout.connect, 10.0)
        with self.assertRaises(ConfigurationError):
            PharmAssistant(CLE, base_url="api.pharmassistant.fr")
        with self.assertRaises(ValueError):
            PharmAssistant(CLE, max_retries=-1)

    def test_with_options_partage_la_connexion(self):
        serveur = Serveur(reponse_ask())
        c = client(serveur)
        lent = c.with_options(timeout=600, max_retries=0)
        self.assertIs(lent._http, c._http)
        self.assertEqual(lent.timeout.read, 600.0)
        self.assertEqual(lent.max_retries, 0)
        self.assertEqual(c.timeout.read, 300.0)
        lent.close()
        self.assertFalse(c._http.is_closed)


class TestAsk(unittest.TestCase):
    def test_corps_minimal_et_entetes(self):
        serveur = Serveur(reponse_ask())
        client(serveur).ask("Amoxicilline et allaitement ?")
        requete = serveur.requetes[0]
        self.assertEqual(str(requete.url), f"{URL}/v1/ask")
        self.assertEqual(serveur.corps(), {"question": "Amoxicilline et allaitement ?"})
        self.assertEqual(requete.headers["x-api-key"], CLE)
        self.assertTrue(requete.headers["user-agent"].startswith(f"pharmassistant-python/{__version__} "))
        self.assertEqual(requete.headers["accept"], "application/json")

    def test_toutes_les_options(self):
        serveur = Serveur(reponse_ask())
        client(serveur).ask("Q ?", mode="detailed", store=True, suggestions=False,
                            patient_advice=False, associated_sale=False,
                            instructions="Bref.", citations="inline")
        self.assertEqual(serveur.corps(), {
            "question": "Q ?", "mode": "detailed", "store": True, "suggestions": False,
            "patient_advice": False, "associated_sale": False, "instructions": "Bref.",
            "citations": "inline"})

    def test_historique_normalise(self):
        serveur = Serveur(reponse_ask())
        client(serveur).ask("Et ensuite ?", history=[("user", "Q1"), {"role": "assistant",
                                                                        "content": "R1"}])
        self.assertEqual(serveur.corps()["history"], [{"role": "user", "content": "Q1"},
                                                      {"role": "assistant", "content": "R1"}])

    def test_refus_locaux_avant_tout_envoi(self):
        serveur = Serveur(reponse_ask())
        c = client(serveur)
        for kwargs in ({"mode": "rapide"}, {"citations": "pied"},
                       {"history": [("user", "Q")], "store": True},
                       {"history": [("user", "Q")], "conversation_id": "conv_1"},
                       {"history": [("robot", "Q")]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                c.ask("Q ?", **kwargs)
        with self.assertRaises(ValueError):
            c.ask("   ")
        self.assertEqual(serveur.requetes, [])

    def test_conversation_id_ecrase_store(self):
        serveur = Serveur(reponse_ask())
        client(serveur).ask("Q ?", conversation_id="conv_1", store=True)
        self.assertEqual(serveur.corps(), {"question": "Q ?", "conversation_id": "conv_1"})

    def test_reponse_typee_et_quota(self):
        serveur = Serveur(lambda r: httpx.Response(200, json=reponse_ask(), headers={
            "X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "88",
            "X-RateLimit-Reset": "1795993200"}))
        r = client(serveur).ask("Q ?")
        self.assertIsInstance(r, Answer)
        self.assertEqual(r["answer"], r.answer)
        self.assertEqual(r.rate_limit.remaining, 88)
        self.assertEqual(r.rate_limit.reset_at.timestamp(), 1795993200)
        self.assertEqual(r.usage.daily_requests_limit, 100)

    def test_timeout_par_appel(self):
        vus = []

        def gestionnaire(requete):
            vus.append(requete.extensions["timeout"])
            return httpx.Response(200, json=reponse_ask())

        client(Serveur(gestionnaire)).ask("Q ?", timeout=900)
        self.assertEqual(vus[0]["read"], 900.0)


class TestAutresRoutes(unittest.TestCase):
    def test_me(self):
        serveur = Serveur({"id": "key_1", "name": "Intégration", "key_hint": "pa_ab…",
                           "pharmacy_slug": None, "daily_limit": 100, "monthly_limit": None,
                           "daily_detailed_limit": 10, "limits_locked": True,
                           "scopes": ["ask"], "active": True, "expires_at": None,
                           "created_at": "2026-07-23T10:00:00+02:00", "last_used_at": None,
                           "daily_requests_used": 30, "daily_detailed_used": 2,
                           "month_requests_used": 300})
        k = client(serveur).me()
        self.assertIsInstance(k, KeyInfo)
        self.assertEqual(k.daily_remaining, 70)
        self.assertIsNone(k.monthly_remaining)
        self.assertTrue(k.has_scope("ask"))
        self.assertFalse(k.has_scope("ask:detailed"))
        self.assertEqual(str(serveur.requetes[0].url), f"{URL}/v1/me")

    def test_health_sans_cle(self):
        serveur = Serveur({"status": "ok", "service": "pharmassistant-api", "version": "1.0.0"})
        h = client(serveur).health()
        self.assertEqual(h.version, "1.0.0")
        self.assertNotIn("x-api-key", serveur.requetes[0].headers)

    def test_conversations(self):
        serveur = Serveur(
            {"object": "list", "data": [{"id": "conv_1", "title": "T", "message_count": 2}]},
            {"id": "conv_1", "object": "pharmassistant.conversation", "title": "T",
             "messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "R"}]},
            {"id": "conv_1", "object": "pharmassistant.conversation", "deleted": True})
        c = client(serveur)
        liste = c.conversations.list(limit=10)
        self.assertEqual(liste[0].message_count, 2)
        self.assertEqual(serveur.requetes[0].url.params["limit"], "10")
        detail = c.conversations.retrieve("conv_1")
        self.assertIsInstance(detail, ConversationDetail)
        self.assertEqual([m.role for m in detail.messages], ["user", "assistant"])
        self.assertTrue(c.conversations.delete("conv_1").deleted)
        self.assertEqual(serveur.requetes[2].method, "DELETE")

    def test_appels_du_fichier_leger_toujours_valides(self):
        serveur = Serveur({"object": "list", "data": []},
                          {"id": "conv_1", "messages": []},
                          {"id": "conv_1", "deleted": True})
        c = client(serveur)
        self.assertEqual(c.conversations(limit=5), [])
        self.assertEqual(c.conversation("conv_1").id, "conv_1")
        self.assertTrue(c.delete_conversation("conv_1")["deleted"])


if __name__ == "__main__":
    unittest.main()
