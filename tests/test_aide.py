import contextlib
import io
import re
import unittest
from pathlib import Path

import pharmassistant
from pharmassistant import CODES, aide, texte_d_aide
from pharmassistant._aide import ALIAS, SUJETS

RACINE = Path(__file__).resolve().parent.parent


class TestAide(unittest.TestCase):
    def test_sommaire_liste_chaque_sujet(self):
        sommaire = texte_d_aide()
        for sujet in SUJETS:
            self.assertIn(sujet, sommaire)

    def test_chaque_sujet_et_alias(self):
        for sujet in SUJETS:
            self.assertTrue(texte_d_aide(sujet).strip())
        for alias, cible in ALIAS.items():
            self.assertIn(cible, SUJETS, alias)
            self.assertEqual(texte_d_aide(alias), texte_d_aide(cible))

    def test_chaque_code(self):
        for code in CODES:
            self.assertIn(code, texte_d_aide(code))
        self.assertIn("rate_limited", texte_d_aide("codes"))

    def test_sujet_inconnu_propose(self):
        with self.assertRaises(KeyError) as ctx:
            texte_d_aide("citation_")
        self.assertIn("citation", ctx.exception.args[0])
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            aide("zzz")
        self.assertIn("Sujets", sortie.getvalue())

    def test_noms_cites_dans_l_aide_existent(self):
        textes = "\n".join(texte_d_aide(s) for s in SUJETS)
        for nom in set(re.findall(r"\b([A-Z][A-Za-z]+(?:Error|Stream|PharmAssistant))\b", textes)):
            self.assertTrue(hasattr(pharmassistant, nom), nom)

    def test_typographie(self):
        textes = "\n".join(texte_d_aide(s) for s in SUJETS) + "\n".join(
            i.sens + i.aide for i in CODES.values())
        self.assertNotIn("—", textes)
        self.assertNotIn(" – ", textes)


DEPOT = "https://github.com/Vitruves/pharmassistant-python/blob/main/"
DOCS = RACINE / "docs"


def _ancre(titre):
    titre = re.sub(r"[`*_]", "", titre.strip().lower())
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", titre))


def _ancres(chemin):
    return {_ancre(t) for t in re.findall(r"^#+ (.+)$", chemin.read_text(encoding="utf-8"), re.M)}


def _pages():
    return [RACINE / "README.md", *sorted(DOCS.glob("*.md"))]


class TestDocumentation(unittest.TestCase):
    def test_chaque_code_et_chaque_exception_documentes(self):
        erreurs = (DOCS / "erreurs.md").read_text(encoding="utf-8")
        for code in CODES:
            self.assertIn(f"`{code}`", erreurs, code)
        for nom in pharmassistant.__all__:
            if nom.endswith("Error"):
                self.assertIn(nom, erreurs, nom)

    def test_exemples_compilent(self):
        for page in _pages():
            for bloc in re.findall(r"```python\n(.*?)```", page.read_text(encoding="utf-8"), re.S):
                code = (bloc.replace("await ", "").replace("async with", "with")
                        .replace("async for", "for"))
                with self.subTest(page=page.name, debut=bloc[:40]):
                    compile(code, page.name, "exec")

    def test_liens_vers_le_depot_et_ancres(self):
        for page in _pages():
            texte = page.read_text(encoding="utf-8")
            relatifs = re.findall(r"\]\((?!https?:|mailto:)([^)]+)\)", texte)
            base = DEPOT + str(page.relative_to(RACINE).parent).replace(".", "").strip("/")
            liens = [(f"{DEPOT}{page.relative_to(RACINE)}{c}" if c.startswith("#")
                      else f"{base}/{c}".replace("main//", "main/")) for c in relatifs]
            liens += re.findall(r'(?:\]\(|href=")(' + re.escape(DEPOT) + r'[^)"]+)', texte)
            for lien in liens:
                chemin, _, ancre = lien.replace(DEPOT, "").partition("#")
                with self.subTest(page=page.name, lien=lien):
                    cible = (RACINE / chemin).resolve()
                    self.assertTrue(cible.exists(), lien)
                    if ancre:
                        self.assertIn(ancre, _ancres(cible), lien)

    def test_sommaire_couvre_chaque_page(self):
        sommaire = (DOCS / "README.md").read_text(encoding="utf-8")
        for page in DOCS.glob("*.md"):
            if page.name != "README.md":
                self.assertIn(f"]({page.name})", sommaire, page.name)

    def test_typographie_de_la_documentation(self):
        for page in _pages():
            texte = page.read_text(encoding="utf-8")
            self.assertNotIn("—", texte, page.name)
            self.assertNotIn(" – ", texte, page.name)

    def test_version_unique(self):
        changelog = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {pharmassistant.__version__}", changelog)


if __name__ == "__main__":
    unittest.main()
