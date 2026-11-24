import unittest

import httpx
from _outils import Serveur, client_async, erreur, flux_complet, reponse_ask, sse

from pharmassistant import Answer, APIConnectionError, QuotaExceededError


class TestAsynchrone(unittest.IsolatedAsyncioTestCase):
    async def test_ask(self):
        serveur = Serveur(reponse_ask())
        async with client_async(serveur) as c:
            r = await c.ask("Q ?", citations="inline")
        self.assertIsInstance(r, Answer)
        self.assertEqual(serveur.corps(), {"question": "Q ?", "citations": "inline"})

    async def test_flux(self):
        c = client_async(Serveur(flux_complet()))
        flux = await c.ask_stream("Q ?")
        async with flux:
            textes = [t async for t in flux.text_stream]
            reponse = await flux.get_final_answer()
        self.assertEqual("".join(textes), "Compatible.")
        self.assertEqual(reponse.id, "req_0001")
        await c.close()

    async def test_deballage(self):
        c = client_async(Serveur(flux_complet()))
        evenements = [event async for event, _ in await c.ask_stream("Q ?")]
        self.assertEqual(evenements[-1], "done")
        await c.close()

    async def test_flux_tronque(self):
        c = client_async(Serveur(sse(("start", {"id": "req_1"}))))
        flux = await c.ask_stream("Q ?")
        with self.assertRaises(APIConnectionError):
            await flux.get_final_answer()
        await c.close()

    async def test_reessai_puis_succes(self):
        serveur = Serveur(erreur(429, "rate_limited", **{"Retry-After": "2"}), reponse_ask())
        c = client_async(serveur)
        await c.ask("Q ?")
        self.assertEqual(c.attentes, [2.0])
        await c.close()

    async def test_plafond(self):
        c = client_async(Serveur(erreur(429, "monthly_limit_reached")))
        with self.assertRaises(QuotaExceededError):
            await c.ask("Q ?")
        await c.close()

    async def test_conversation_gardee(self):
        serveur = Serveur(reponse_ask(conversation_id="conv_9"), reponse_ask(conversation_id="conv_9"))
        c = client_async(serveur)
        conv = c.start_conversation(store=True)
        await conv.ask("Q1 ?")
        await conv.ask("Q2 ?")
        self.assertEqual(serveur.corps(0), {"question": "Q1 ?", "store": True})
        self.assertEqual(serveur.corps(1), {"question": "Q2 ?", "conversation_id": "conv_9"})
        await c.close()

    async def test_me_et_conversations(self):
        serveur = Serveur({"id": "key_1"}, {"object": "list", "data": [{"id": "conv_1"}]},
                          {"id": "conv_1", "deleted": True})
        c = client_async(serveur)
        self.assertEqual((await c.me()).id, "key_1")
        self.assertEqual((await c.conversations.list())[0].id, "conv_1")
        self.assertTrue((await c.conversations.delete("conv_1")).deleted)
        await c.close()

    async def test_client_fourni_non_ferme(self):
        http = httpx.AsyncClient(transport=httpx.MockTransport(Serveur(reponse_ask())))
        from pharmassistant import AsyncPharmAssistant
        async with AsyncPharmAssistant("pa_test_0123456789", http_client=http):
            pass
        self.assertFalse(http.is_closed)
        await http.aclose()


if __name__ == "__main__":
    unittest.main()
