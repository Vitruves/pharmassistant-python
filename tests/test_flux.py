import unittest

import httpx
from _outils import Serveur, client, erreur, flux_complet, reponse_ask, sse

from pharmassistant import (
    Answer,
    APIConnectionError,
    QuotaExceededError,
    Reference,
    ServerError,
    StreamEvent,
)
from pharmassistant._streaming import LecteurSSE


class TestLecteur(unittest.TestCase):
    def lire(self, texte):
        lecteur, sortie = LecteurSSE(), []
        for ligne in texte.split("\n"):
            brut = lecteur.ligne(ligne)
            if brut:
                sortie.append(brut)
        reste = lecteur.fin()
        if reste:
            sortie.append(reste)
        return sortie

    def test_formes_du_protocole(self):
        texte = (": commentaire\n\nevent: chunk\r\ndata: {\"a\":1}\n\n"
                 "data: ligne1\ndata:ligne2\n\nevent: done\ndata: {}")
        self.assertEqual(self.lire(texte), [("chunk", '{"a":1}'), ("message", "ligne1\nligne2"),
                                            ("done", "{}")])


class TestFlux(unittest.TestCase):
    def test_evenements_et_reponse_finale(self):
        serveur = Serveur(flux_complet())
        c = client(serveur)
        with c.ask_stream("Q ?") as flux:
            evenements = list(flux)
        self.assertEqual([e.event for e in evenements], ["start", "status", "chunk", "chunk", "done"])
        self.assertTrue(all(isinstance(e, StreamEvent) for e in evenements))
        self.assertEqual(evenements[1].state, "routing")
        self.assertEqual("".join(e.text for e in evenements), "Compatible.")
        self.assertIsInstance(flux.answer, Answer)
        self.assertEqual(flux.request_id, "req_0001")
        self.assertTrue(serveur.corps()["stream"])
        self.assertEqual(serveur.requetes[0].headers["accept"], "text/event-stream")

    def test_deballage_comme_le_fichier_leger(self):
        reponse = None
        for event, data in client(Serveur(flux_complet())).ask_stream("Q ?"):
            if event == "done":
                reponse = data
        self.assertEqual(reponse["answer"], reponse_ask()["answer"])

    def test_text_stream_puis_reponse(self):
        with client(Serveur(flux_complet())).ask_stream("Q ?") as flux:
            self.assertEqual("".join(flux.text_stream), "Compatible.")
            self.assertEqual(flux.get_final_answer().id, "req_0001")

    def test_get_final_answer_seul(self):
        self.assertEqual(client(Serveur(flux_complet())).ask_stream("Q ?").get_final_answer().status,
                         "ok")

    def test_registre_avant_le_texte(self):
        corps = sse(("start", {"id": "req_1"}),
                    ("references", {"references": [{"n": 1, "tool": "t", "title": "T"}]}),
                    ("chunk", {"text": "A.[S1]"}), ("done", reponse_ask(citations="inline")))
        flux = client(Serveur(corps)).ask_stream("Q ?", citations="inline")
        evt = next(iter(flux))
        evt = next(flux)
        self.assertEqual(evt.event, "references")
        self.assertIsInstance(flux.references[0], Reference)
        flux.close()

    def test_erreur_en_cours_de_flux(self):
        corps = sse(("start", {"id": "req_9"}), ("chunk", {"text": "A"}),
                    ("error", {"error": {"code": "generation_failed", "message": "Échec."}}))
        flux = client(Serveur(corps)).ask_stream("Q ?")
        with self.assertRaises(ServerError) as ctx:
            list(flux)
        self.assertEqual((ctx.exception.code, ctx.exception.request_id),
                         ("generation_failed", "req_9"))

    def test_flux_tronque(self):
        corps = sse(("start", {"id": "req_9"}), ("chunk", {"text": "A"}))
        with self.assertRaises(APIConnectionError) as ctx:
            client(Serveur(corps)).ask_stream("Q ?").get_final_answer()
        self.assertEqual(ctx.exception.code, "stream_interrupted")

    def test_refus_de_pre_vol_leve_des_l_appel(self):
        serveur = Serveur(erreur(429, "daily_limit_reached"))
        with self.assertRaises(QuotaExceededError):
            client(serveur).ask_stream("Q ?")

    def test_5xx_de_pre_vol_reessaye(self):
        serveur = Serveur(erreur(502, "generation_failed"), flux_complet())
        self.assertEqual(client(serveur).ask_stream("Q ?").get_final_answer().status, "ok")

    def test_coupure_reseau_pendant_le_flux(self):
        class Coupe(httpx.SyncByteStream):
            def __iter__(self):
                yield b"event: start\ndata: {\"id\": \"req_5\"}\n\n"
                raise httpx.ReadError("coupure")

        serveur = Serveur(lambda r: httpx.Response(200, stream=Coupe()))
        with self.assertRaises(APIConnectionError) as ctx:
            client(serveur).ask_stream("Q ?").get_final_answer()
        self.assertEqual((ctx.exception.code, ctx.exception.request_id),
                         ("stream_interrupted", "req_5"))


if __name__ == "__main__":
    unittest.main()
