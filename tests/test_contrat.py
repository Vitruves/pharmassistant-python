"""Paquet confronté au schéma OpenAPI publié par l'API en service.

Réseau : lancé seulement avec PHARMASSISTANT_CONTRAT=1 (workflow hebdomadaire
contrat.yml). Un champ ajouté au serveur sans son reflet dans le paquet rougit ici.
"""

import inspect
import os
import unittest

import httpx

import pharmassistant as pa
from pharmassistant import _base, _streaming

URL = os.environ.get("PHARMASSISTANT_API_URL", pa.DEFAULT_BASE_URL).rstrip("/") + "/openapi.json"

REPONSES = {
    "AskResponse": pa.Answer, "KeyInfoResponse": pa.KeyInfo,
    "ConversationSummary": pa.ConversationSummary, "ConversationMessage": pa.ConversationMessage,
    "ConversationDetailResponse": pa.ConversationDetail,
    "ConversationDeletedResponse": pa.ConversationDeleted, "HealthResponse": pa.Health,
    "SourceRef": pa.SourceRef, "Reference": pa.Reference, "RecordLine": pa.RecordLine,
    "Passage": pa.Passage, "Clarification": pa.Clarification, "KeyPoint": pa.KeyPoint,
    "Usage": pa.Usage,
}
# Champs que le paquet n'expose pas exprès, même tant que le serveur les accepte.
RETIRES = {"instructions"}
ROUTES = {"/v1/health", "/v1/me", "/v1/ask", "/v1/conversations",
          "/v1/conversations/{conversation_id}"}


@unittest.skipUnless(os.environ.get("PHARMASSISTANT_CONTRAT") == "1",
                     "contrat réseau : PHARMASSISTANT_CONTRAT=1")
class TestContrat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = httpx.get(URL, timeout=30).raise_for_status().json()
        cls.schemas = cls.spec["components"]["schemas"]

    def _proprietes(self, nom):
        return self.schemas[nom].get("properties", {})

    def test_chaque_champ_de_requete_est_un_parametre(self):
        requete = self._proprietes("AskRequest")
        champs = set(requete) - {"stream"} - RETIRES
        for fonction in (pa.PharmAssistant.ask, pa.PharmAssistant.ask_stream,
                         pa.AsyncPharmAssistant.ask, pa.AsyncPharmAssistant.ask_stream,
                         _base.corps_ask):
            with self.subTest(fonction=fonction.__qualname__):
                parametres = inspect.signature(fonction).parameters
                self.assertLessEqual(champs, set(parametres))
                for nom in champs - {"question", "history", "conversation_id"}:
                    self.assertEqual(parametres[nom].default, requete[nom].get("default"), nom)

    def test_valeurs_permises(self):
        requete = self._proprietes("AskRequest")
        self.assertEqual(set(_base.MODES), set(requete["mode"]["enum"]))
        self.assertEqual(set(_base.CITATIONS), set(requete["citations"]["enum"]))
        statuts = self._proprietes("AskResponse")["status"]["enum"]
        self.assertEqual(set(statuts), {"ok", "clarification_needed"})

    def test_chaque_champ_de_reponse_est_un_attribut(self):
        for schema, classe in REPONSES.items():
            for champ in self._proprietes(schema):
                with self.subTest(schema=schema, champ=champ):
                    self.assertIsInstance(inspect.getattr_static(classe, champ, None), property)

    def test_routes(self):
        self.assertEqual(set(self.spec["paths"]), ROUTES)

    def test_evenements_du_flux_documentes(self):
        description = self.spec["info"].get("description", "")
        for evenement in _streaming.EVENEMENTS:
            self.assertIn(f"`{evenement}`", description)


if __name__ == "__main__":
    unittest.main()
