import unittest

import httpx
from _outils import Serveur, client, erreur

from pharmassistant import (
    CODES,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    ConversationNotFoundError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    PharmAssistantError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from pharmassistant._errors import classe_de, erreur_d_api

ATTENDU = {
    "missing_api_key": AuthenticationError, "invalid_api_key": AuthenticationError,
    "revoked_api_key": AuthenticationError, "expired_api_key": AuthenticationError,
    "pharmacy_not_found": PermissionDeniedError, "pharmacy_suspended": PermissionDeniedError,
    "scope_denied": PermissionDeniedError, "conversation_not_found": ConversationNotFoundError,
    "not_found": NotFoundError, "invalid_request": InvalidRequestError,
    "rate_limited": RateLimitError, "daily_limit_reached": QuotaExceededError,
    "monthly_limit_reached": QuotaExceededError, "detailed_limit_reached": QuotaExceededError,
    "internal_error": ServerError, "generation_failed": ServerError, "empty_response": ServerError,
}


class TestCorrespondance(unittest.TestCase):
    def test_chaque_code_d_api_a_sa_classe(self):
        for code, classe in ATTENDU.items():
            with self.subTest(code=code):
                self.assertIs(classe_de(CODES[code].status, code), classe)
                self.assertIs(classe_de(None, code), classe)

    def test_chaque_code_a_une_aide(self):
        for code, info in CODES.items():
            with self.subTest(code=code):
                self.assertTrue(info.sens.strip() and info.aide.strip())
                self.assertNotIn("—", info.sens + info.aide)

    def test_code_inconnu_classe_par_statut(self):
        self.assertIs(classe_de(401, "nouveau_code"), AuthenticationError)
        self.assertIs(classe_de(429, "nouveau_code"), RateLimitError)
        self.assertIs(classe_de(503, None), ServerError)
        self.assertIs(classe_de(418, None), APIStatusError)

    def test_enveloppe_absente(self):
        exc = erreur_d_api(502, None, brut="<html>Bad gateway</html>")
        self.assertIsInstance(exc, ServerError)
        self.assertEqual(exc.code, "http_502")
        self.assertIn("Bad gateway", exc.message)


class TestLevees(unittest.TestCase):
    def test_erreur_porte_tout_ce_qu_il_faut(self):
        serveur = Serveur(erreur(401, "invalid_api_key", "Clé d'API inconnue."))
        with self.assertRaises(AuthenticationError) as ctx:
            client(serveur).ask("Q ?")
        exc = ctx.exception
        self.assertEqual((exc.status, exc.code, exc.request_id), (401, "invalid_api_key", "req_err"))
        texte = str(exc)
        self.assertTrue(texte.startswith("[401] invalid_api_key: Clé d'API inconnue."))
        self.assertIn("Aide : ", texte)
        self.assertIn("Requête : req_err", texte)
        self.assertIsInstance(exc, PharmAssistantError)

    def test_quota_dit_quand_reessayer(self):
        serveur = Serveur(erreur(429, "daily_limit_reached", **{"X-RateLimit-Reset": "1795993200"}))
        with self.assertRaises(QuotaExceededError) as ctx:
            client(serveur).ask("Q ?")
        self.assertEqual(ctx.exception.reset_at.timestamp(), 1795993200)
        self.assertEqual(len(serveur.requetes), 1)

    def test_validation_detaillee(self):
        serveur = Serveur(httpx.Response(422, json={"error": {
            "code": "invalid_request", "message": "Corps de requête invalide.",
            "details": [{"loc": ["body", "question"], "msg": "trop longue"}]}}))
        with self.assertRaises(InvalidRequestError) as ctx:
            client(serveur).ask("Q ?")
        self.assertEqual(ctx.exception.details[0]["msg"], "trop longue")

    def test_reseau(self):
        serveur = Serveur(httpx.ConnectError("refusé"))
        with self.assertRaises(APIConnectionError) as ctx:
            client(serveur, max_retries=0).ask("Q ?")
        self.assertEqual(ctx.exception.code, "connection_error")
        serveur = Serveur(httpx.ReadTimeout("lent"))
        with self.assertRaises(APITimeoutError) as ctx:
            client(serveur).ask("Q ?")
        self.assertEqual(ctx.exception.code, "timeout")

    def test_reponse_illisible(self):
        serveur = Serveur(httpx.Response(200, text="<html>portail captif</html>"))
        with self.assertRaises(APIConnectionError) as ctx:
            client(serveur).ask("Q ?")
        self.assertEqual(ctx.exception.code, "invalid_response")


if __name__ == "__main__":
    unittest.main()
