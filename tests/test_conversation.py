import unittest

from _outils import Serveur, clarification, client, flux_complet, reponse_ask

from pharmassistant import Conversation


class TestConversationLocale(unittest.TestCase):
    def test_historique_porte_par_le_client(self):
        serveur = Serveur(reponse_ask(answer="R1.[S1]"), reponse_ask(answer="R2."))
        conv = client(serveur).start_conversation(mode="detailed")
        self.assertIsInstance(conv, Conversation)
        conv.ask("Q1 ?")
        conv.ask("Q2 ?")
        self.assertEqual(serveur.corps(0), {"question": "Q1 ?", "mode": "detailed"})
        self.assertEqual(serveur.corps(1)["history"], [{"role": "user", "content": "Q1 ?"},
                                                       {"role": "assistant", "content": "R1."}])
        self.assertIsNone(conv.id)
        self.assertEqual(len(conv.history), 4)

    def test_historique_borne(self):
        serveur = Serveur(reponse_ask(answer="R."))
        conv = client(serveur).start_conversation(max_history_turns=2)
        for i in range(5):
            conv.ask(f"Q{i} ?")
        self.assertEqual(len(conv.history), 4)
        self.assertEqual(conv.history[0]["content"], "Q3 ?")

    def test_precision_gardee_dans_l_historique(self):
        serveur = Serveur(clarification(), reponse_ask())
        conv = client(serveur).start_conversation()
        r = conv.ask("Collyre pour l'oeille ?")
        conv.ask(r.clarification.corrected_question(r.question, "œil"))
        self.assertEqual(serveur.corps(1)["question"], "Collyre pour l'œil ?")
        self.assertEqual(serveur.corps(1)["history"][1]["content"], "Vouliez-vous dire :")

    def test_reset(self):
        serveur = Serveur(reponse_ask())
        conv = client(serveur).start_conversation()
        conv.ask("Q ?")
        conv.reset()
        conv.ask("Q ?")
        self.assertNotIn("history", serveur.corps())

    def test_options_reservees(self):
        conv = client(Serveur(reponse_ask())).start_conversation()
        for cle in ("store", "history", "conversation_id"):
            with self.subTest(cle=cle), self.assertRaises(ValueError):
                conv.ask("Q ?", **{cle: None})
        with self.assertRaises(ValueError):
            client(Serveur(reponse_ask())).start_conversation(store=True, history=[])


class TestConversationGardee(unittest.TestCase):
    def test_ouverture_puis_suite(self):
        serveur = Serveur(reponse_ask(conversation_id="conv_7"), reponse_ask(conversation_id="conv_7"))
        conv = client(serveur).start_conversation(store=True)
        conv.ask("Q1 ?")
        self.assertEqual(conv.id, "conv_7")
        conv.ask("Q2 ?", citations="inline")
        self.assertEqual(serveur.corps(1), {"question": "Q2 ?", "conversation_id": "conv_7",
                                            "citations": "inline"})

    def test_reprise_et_suppression(self):
        serveur = Serveur(reponse_ask(conversation_id="conv_3"),
                          {"id": "conv_3", "deleted": True})
        conv = client(serveur).resume_conversation("conv_3")
        conv.ask("Suite ?")
        conv.delete()
        self.assertEqual(serveur.requetes[1].method, "DELETE")
        self.assertTrue(str(serveur.requetes[1].url).endswith("/v1/conversations/conv_3"))
        self.assertIsNone(conv.id)

    def test_flux_met_la_conversation_a_jour(self):
        serveur = Serveur(flux_complet(reponse_ask(conversation_id="conv_8")), reponse_ask())
        conv = client(serveur).start_conversation(store=True)
        conv.ask_stream("Q1 ?").get_final_answer()
        self.assertEqual(conv.id, "conv_8")
        conv.ask("Q2 ?")
        self.assertEqual(serveur.corps(1)["conversation_id"], "conv_8")


if __name__ == "__main__":
    unittest.main()
