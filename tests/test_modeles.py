import json
import unittest

from _outils import clarification, reponse_ask

from pharmassistant import (
    Answer,
    Clarification,
    KeyPoint,
    Passage,
    RateLimit,
    RecordLine,
    Reference,
    SourceRef,
)


class TestAnswer(unittest.TestCase):
    def setUp(self):
        self.r = Answer(reponse_ask())

    def test_dict_et_attributs(self):
        self.assertEqual(self.r["title"], self.r.title)
        self.assertIsInstance(self.r.key_points[0], KeyPoint)
        self.assertTrue(self.r.key_points[0].is_positive)
        self.assertIsInstance(self.r["sources"]["lecrat_search"][0], SourceRef)
        self.assertIsInstance(self.r.references[0], Reference)
        self.assertIsInstance(self.r.passages[1].record[0], RecordLine)
        self.assertEqual(self.r.usage.elapsed_ms, 4200)

    def test_serialisable(self):
        texte = json.dumps(self.r, ensure_ascii=False)
        self.assertEqual(json.loads(texte), reponse_ask())
        self.assertEqual(self.r.to_dict(), reponse_ask())
        self.assertIs(type(self.r.to_dict()["usage"]), dict)

    def test_reperes(self):
        citations = list(self.r.iter_citations())
        self.assertEqual([(c.rank, c.n) for c in citations], [(0, 1), (1, 1), (2, 2)])
        self.assertEqual(citations[0].passage.quote, "passe peu dans le lait")
        self.assertIsNone(citations[1].passage)
        self.assertTrue(citations[2].passage.is_record)
        self.assertTrue(citations[2].reference.empty)
        self.assertEqual(self.r.answer[citations[0].start:citations[0].end], "[S1]")
        self.assertEqual(self.r.answer_without_markers(), "Compatible. Surveiller le nourrisson.")
        self.assertEqual(self.r.reference(2).marker, "[S2]")
        self.assertIsNone(self.r.reference(9))

    def test_sources_sans_doublon(self):
        self.assertEqual([s.title for s in self.r.all_sources()], ["CRAT : amoxicilline", "LactMed"])

    def test_champs_absents(self):
        vide = Answer({"id": "req_1", "status": "ok"})
        self.assertEqual((vide.key_points, vide.sources, vide.references), ([], {}, []))
        self.assertIsNone(vide.answer_without_markers())
        self.assertEqual(list(vide.iter_citations()), [])
        self.assertIsNone(vide.usage.daily_requests_limit)

    def test_precision(self):
        r = Answer(clarification())
        self.assertTrue(r.needs_clarification)
        self.assertIsInstance(r.clarification, Clarification)
        self.assertEqual(r.clarification.corrections, ["œil", "oreille"])


class TestCorrection(unittest.TestCase):
    def c(self, mot):
        return Clarification({"word": mot, "corrections": [], "message": ""})

    def test_trois_regles_du_chat(self):
        self.assertEqual(self.c("oeille").corrected_question("Collyre pour l'OEILLE ?", "œil"),
                         "Collyre pour l'œil ?")
        self.assertEqual(self.c("doliprane").corrected_question("Dolipràne enfant ?", "Doliprane"),
                         "Doliprane enfant ?")
        self.assertEqual(self.c("zzz").corrected_question("Posologie ?", "paracétamol"),
                         "Posologie ? (paracétamol)")
        self.assertEqual(self.c("x").corrected_question("  ", "paracétamol"), "paracétamol")

    def test_caracteres_speciaux(self):
        self.assertEqual(self.c("a+b").corrected_question("Dose de a+b ?", "c"), "Dose de c ?")
        self.assertEqual(self.c("x").corrected_question("x et x", r"\1"), r"\1 et x")


class TestRateLimit(unittest.TestCase):
    def test_entetes(self):
        rl = RateLimit.from_headers({"X-RateLimit-Limit": "100", "x-ratelimit-remaining": "3",
                                     "X-RateLimit-Reset": "1795993200"})
        self.assertEqual((rl.limit, rl.remaining), (100, 3))
        self.assertIsNone(RateLimit.from_headers({}))
        self.assertIsNone(RateLimit.from_headers({"X-RateLimit-Limit": "abc",
                                                  "X-RateLimit-Remaining": "1"}))

    def test_passage_prose(self):
        p = Passage({"index": 0, "n": 1, "quote": "q", "record": None})
        self.assertFalse(p.is_record)


if __name__ == "__main__":
    unittest.main()
