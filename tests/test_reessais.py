import unittest

import httpx
from _outils import Serveur, client, erreur, reponse_ask

from pharmassistant import (
    APITimeoutError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from pharmassistant._base import BACKOFF_MAX, RETRY_AFTER_MAX, delai_de_reessai


class TestPolitique(unittest.TestCase):
    def test_ce_qui_se_reessaie(self):
        self.assertIsNotNone(delai_de_reessai(0, 2, "POST", exc=httpx.ConnectError("x")))
        self.assertIsNotNone(delai_de_reessai(0, 2, "POST", exc=httpx.ConnectTimeout("x")))
        self.assertIsNotNone(delai_de_reessai(0, 2, "GET", exc=httpx.ReadTimeout("x")))
        for status in (500, 502, 503, 504):
            self.assertIsNotNone(delai_de_reessai(0, 2, "POST", status=status))
        self.assertEqual(delai_de_reessai(0, 2, "POST", status=429, code="rate_limited",
                                          headers={"Retry-After": "7"}), 7.0)

    def test_ce_qui_ne_se_reessaie_jamais(self):
        self.assertIsNone(delai_de_reessai(0, 2, "POST", exc=httpx.ReadTimeout("x")))
        self.assertIsNone(delai_de_reessai(0, 2, "POST", exc=httpx.RemoteProtocolError("x")))
        self.assertIsNone(delai_de_reessai(0, 2, "DELETE", exc=httpx.ReadTimeout("x")))
        for code in ("daily_limit_reached", "monthly_limit_reached", "detailed_limit_reached"):
            self.assertIsNone(delai_de_reessai(0, 2, "POST", status=429, code=code))
        for status in (400, 401, 403, 404, 422):
            self.assertIsNone(delai_de_reessai(0, 2, "POST", status=status))
        self.assertIsNone(delai_de_reessai(2, 2, "POST", status=502))

    def test_bornes_des_delais(self):
        self.assertEqual(delai_de_reessai(0, 2, "POST", status=429, code="rate_limited",
                                          headers={"retry-after": "3600"}), RETRY_AFTER_MAX)
        for tentative in range(10):
            self.assertLessEqual(delai_de_reessai(tentative, 99, "POST", status=502), BACKOFF_MAX)


class TestBoucle(unittest.TestCase):
    def test_rafale_puis_succes(self):
        serveur = Serveur(erreur(429, "rate_limited", **{"Retry-After": "4"}), reponse_ask())
        c = client(serveur)
        self.assertEqual(c.ask("Q ?").status, "ok")
        self.assertEqual(c.attentes, [4.0])
        self.assertEqual(len(serveur.requetes), 2)

    def test_5xx_puis_succes(self):
        serveur = Serveur(erreur(502, "generation_failed"), erreur(503, "x"), reponse_ask())
        c = client(serveur)
        c.ask("Q ?")
        self.assertEqual(len(c.attentes), 2)

    def test_epuisement_leve_la_derniere_erreur(self):
        serveur = Serveur(erreur(502, "generation_failed"))
        c = client(serveur, max_retries=3)
        with self.assertRaises(ServerError):
            c.ask("Q ?")
        self.assertEqual(len(serveur.requetes), 4)

    def test_rafale_epuisee(self):
        serveur = Serveur(erreur(429, "rate_limited", **{"Retry-After": "1"}))
        with self.assertRaises(RateLimitError) as ctx:
            client(serveur, max_retries=1).ask("Q ?")
        self.assertEqual(ctx.exception.retry_after, 1.0)

    def test_plafond_jamais_reessaye(self):
        serveur = Serveur(erreur(429, "daily_limit_reached"))
        c = client(serveur)
        with self.assertRaises(QuotaExceededError):
            c.ask("Q ?")
        self.assertEqual((len(serveur.requetes), c.attentes), (1, []))

    def test_connexion_refusee_puis_succes(self):
        serveur = Serveur(httpx.ConnectError("refusé"), reponse_ask())
        self.assertEqual(client(serveur).ask("Q ?").id, "req_0001")

    def test_lecture_coupee_sur_question_jamais_reessayee(self):
        serveur = Serveur(httpx.ReadTimeout("lent"), reponse_ask())
        with self.assertRaises(APITimeoutError):
            client(serveur).ask("Q ?")
        self.assertEqual(len(serveur.requetes), 1)

    def test_lecture_coupee_sur_get_reessayee(self):
        serveur = Serveur(httpx.ReadTimeout("lent"), {"id": "key_1"})
        self.assertEqual(client(serveur).me().id, "key_1")

    def test_aucun_essai(self):
        serveur = Serveur(erreur(502, "generation_failed"))
        with self.assertRaises(ServerError):
            client(serveur, max_retries=0).ask("Q ?")
        self.assertEqual(len(serveur.requetes), 1)


if __name__ == "__main__":
    unittest.main()
