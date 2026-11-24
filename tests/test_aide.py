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


class TestDocumentation(unittest.TestCase):
    def test_readme_cite_chaque_code_et_chaque_exception(self):
        readme = (RACINE / "README.md").read_text(encoding="utf-8")
        for code in CODES:
            self.assertIn(f"`{code}`", readme, code)
        for nom in pharmassistant.__all__:
            if nom.endswith("Error"):
                self.assertIn(nom, readme, nom)

    def test_exemples_du_readme_compilent(self):
        readme = (RACINE / "README.md").read_text(encoding="utf-8")
        for bloc in re.findall(r"```python\n(.*?)```", readme, re.S):
            compile(bloc.replace("await ", "").replace("async with", "with")
                    .replace("async for", "for"), "README", "exec")

    def test_version_unique(self):
        changelog = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {pharmassistant.__version__}", changelog)


if __name__ == "__main__":
    unittest.main()
