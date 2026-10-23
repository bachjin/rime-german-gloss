"""Unit tests for tools/build_frwiktionary.py.  Run:  python3 tests/test_build_frwiktionary.py"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_frwiktionary as bf  # noqa: E402


def jsonl(*entries):
    return [json.dumps(e, ensure_ascii=False) for e in entries]


ZH = {"lang_code": "zh", "word": "马"}

FR = jsonl(
    {"word": "cheval", "lang_code": "fr", "pos": "noun", "tags": ["masculine"],
     "senses": [{"glosses": ["Animal."]}], "forms": [{"form": "chevaux", "tags": ["plural"]}],
     "translations": [dict(ZH)]},
    {"word": "chevaux", "lang_code": "fr", "pos": "noun", "tags": ["form-of", "masculine"],
     "senses": [{"glosses": ["Pluriel de cheval."], "tags": ["form-of"], "form_of": [{"word": "cheval"}]}]},
    {"word": "maison", "lang_code": "fr", "pos": "noun", "tags": ["feminine"],
     "senses": [{"glosses": ["Bâtiment."]}], "forms": [{"form": "maisons", "tags": ["plural"]}]},
    {"word": "maisons", "lang_code": "fr", "pos": "noun", "tags": ["form-of"],
     "senses": [{"glosses": ["Pluriel de maison."], "tags": ["form-of"], "form_of": [{"word": "maison"}]}]},
    {"word": "beau", "lang_code": "fr", "pos": "adj", "senses": [{"glosses": ["Joli."]}],
     "forms": [{"form": "belle", "tags": ["singular", "feminine"]},
               {"form": "beaux", "tags": ["plural", "masculine"]}]},
    {"word": "grand", "lang_code": "fr", "pos": "adj", "senses": [{"glosses": ["Haut."]}],
     "forms": [{"form": "grande", "tags": ["singular", "feminine"]}]},
    {"word": "aller", "lang_code": "fr", "pos": "verb", "senses": [{"glosses": ["Se déplacer."]}]},
    {"word": "allais", "lang_code": "fr", "pos": "verb", "tags": ["form-of"], "senses": [
        {"glosses": ["Première personne du singulier de l’indicatif imparfait du verbe aller."],
         "tags": ["form-of"], "form_of": [{"word": "aller"}]}]},
    {"word": "été", "lang_code": "fr", "pos": "noun", "tags": ["masculine"], "senses": [{"glosses": ["Saison."]}]},
    {"word": "été", "lang_code": "fr", "pos": "verb", "senses": [
        {"glosses": ["Participe passé masculin singulier de être."], "tags": ["form-of"],
         "form_of": [{"word": "être"}]}]},
    {"word": "être", "lang_code": "fr", "pos": "verb", "senses": [{"glosses": ["Exister."]}]},
    {"word": "aujourd’hui", "lang_code": "fr", "pos": "adv", "senses": [{"glosses": ["Ce jour."]}]},
    {"word": "qu’", "lang_code": "fr", "pos": "conj", "tags": ["form-of"], "senses": [
        {"glosses": ["Élision de la conjonction que devant une voyelle ou un h muet."],
         "tags": ["form-of"], "form_of": [{"word": "conjonction"}]}]},
    {"word": "que", "lang_code": "fr", "pos": "conj", "senses": [{"glosses": ["Conjonction."]}]},
    {"word": "Maisons", "lang_code": "fr", "pos": "name", "senses": [{"glosses": ["Commune."]}]},
    {"word": "-ette", "lang_code": "fr", "pos": "suffix", "senses": [{"glosses": ["Suffixe."]}]},
    {"word": "cheval", "lang_code": "en", "pos": "noun", "senses": [{"glosses": ["horse"]}]},
)

ZH_WIKT = jsonl(
    {"word": "cheval", "lang_code": "fr", "pos": "noun",
     "senses": [{"glosses": ["n.m. 马；骑术；马肉pl. ~aux 骑兵"]}]},
    {"word": "aller", "lang_code": "fr", "pos": "verb", "senses": [{"glosses": ["去，走"]}]},
    {"word": "être", "lang_code": "fr", "pos": "verb", "senses": [{"glosses": ["存在"]}]},
    {"word": "été", "lang_code": "fr", "pos": "noun", "senses": [{"glosses": ["夏天"]}]},
    {"word": "beau", "lang_code": "fr", "pos": "adj", "senses": [{"glosses": ["美丽的"]}]},
    {"word": "que", "lang_code": "fr", "pos": "conj", "senses": [{"glosses": ["[连词] 引导从句"]}]},
    {"word": "aujourd'hui", "lang_code": "fr", "pos": "adv", "senses": [{"glosses": ["今天"]}]},
    {"word": "alto", "lang_code": "fr", "pos": "noun",
     "senses": [{"glosses": ["n.m. 女低音；中提琴adj. 中音的"]}]},
    {"word": "pas", "lang_code": "fr", "pos": "adv", "senses": [{"glosses": ["???"]}]},
    {"word": "cheval", "lang_code": "de", "pos": "noun", "senses": [{"glosses": ["不是法语"]}]},
)

CFDICT = [
    "房子 房子 [fang2 zi5] /maison/bâtiment/\n",
    "大 大 [da4] /grand/gros/(nom de famille)/\n",
    "馬 马 [ma3] /cheval/\n",
]

FREQUENCY = ["de 100\n", "maison 50\n", "été 40\n", "aller 30\n", "maisons 9\n"]


def build(with_forms=True):
    translations, names, forms, lemmas, grammar = bf.read_wiktionary(FR)
    zh = bf.read_zh_wiktionary(ZH_WIKT)
    cfdict, t2s = bf.read_cfdict(CFDICT)
    freq = bf.build_dewiktionary.read_frequency(FREQUENCY)
    return bf.build(translations, names, forms, lemmas, grammar, zh, cfdict, t2s, freq, with_forms)


class FoldTest(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(bf.codes("élève"), [("eleve", False)])
        self.assertEqual(bf.codes("cœur"), [("coeur", False)])
        self.assertEqual(bf.codes("peut-être"), [("peutetre", False)])
        self.assertEqual(bf.codes("aujourd'hui"), [("aujourd'hui", False), ("aujourdhui", True)])
        self.assertEqual(bf.codes("j'"), [("j'", False)])
        self.assertEqual(bf.codes("Ça"), [("ca", False)])
        self.assertEqual(bf.codes("x²"), [])

    def test_form_label(self):
        self.assertEqual(bf.form_label("Troisième personne du pluriel du subjonctif imparfait de aller."),
                         "虚拟式未完成过去时")
        self.assertEqual(bf.form_label("Participe passé féminin pluriel de aller."), "过去分词")
        self.assertEqual(bf.form_label("Féminin pluriel de beau."), "阴性复数")
        self.assertEqual(bf.form_label("Quelque chose."), "变形")


class GlossTest(unittest.TestCase):
    def test_clean_gloss(self):
        self.assertEqual(bf.clean_gloss("n.m. 马；骑术；马肉pl. ~aux 骑兵"), ["马", "骑术", "马肉"])
        self.assertEqual(bf.clean_gloss("n.m. 女低音；中提琴adj. 中音的"), ["女低音", "中提琴", "中音的"])
        self.assertEqual(bf.clean_gloss("???"), [])

    def test_grammar(self):
        _, _, _, _, grammar = bf.read_wiktionary(FR)
        self.assertEqual(grammar["cheval"], "n.m. · 复数 chevaux")
        self.assertEqual(grammar["maison"], "n.f.")
        self.assertEqual(grammar["beau"], "adj. · belle, beaux")
        self.assertEqual(grammar["grand"], "adj.")
        self.assertEqual(grammar["aller"], "v.")

    def test_read_wiktionary(self):
        translations, names, forms, lemmas, _ = bf.read_wiktionary(FR)
        self.assertIn("aujourd'hui", lemmas)  # typographic apostrophe normalized
        self.assertNotIn("-ette", lemmas)
        self.assertNotIn("chevaux", lemmas)
        self.assertIn("été", lemmas)
        self.assertEqual(forms["qu'"], [("que", "省音形式")])
        self.assertEqual(forms["allais"], [("aller", "未完成过去时")])
        self.assertEqual(translations["cheval"], ["马"])

    def test_glosses(self):
        glosses, _ = build()
        self.assertEqual(glosses["cheval"], "n.m. · 复数 chevaux · 马; 骑术; 马肉")
        self.assertEqual(glosses["chevaux"], "cheval 的复数 · 马")
        self.assertEqual(glosses["allais"], "aller 的未完成过去时 · 去，走")
        self.assertEqual(glosses["été"], "n.m. · 夏天 / être 的过去分词 · 存在")
        self.assertEqual(glosses["qu'"], "que 的省音形式 · 引导从句")
        self.assertEqual(glosses["maison"], "n.f. · 房子")  # from CFDICT read backwards
        self.assertEqual(glosses["aujourd'hui"], "adv. · 今天")

    def test_entries(self):
        _, entries = build()
        words = {(w, c) for w, c, _ in entries}
        self.assertIn(("aujourd'hui", "aujourdhui"), words)
        self.assertIn(("été", "ete"), words)
        self.assertNotIn("Maisons", {w for w, _ in words})  # name without Chinese, maisons exists
        weight = {(w, c): n for w, c, n in entries}
        self.assertGreater(weight[("maison", "maison")], weight[("maisons", "maisons")])
        self.assertEqual(entries, sorted(entries, key=lambda e: (e[1], -e[2], e[0])))

    def test_no_forms(self):
        _, entries = build(with_forms=False)
        words = {w for w, _, _ in entries}
        self.assertIn("été", words)  # also a lemma
        self.assertNotIn("allais", words)

    def test_write_outputs(self):
        glosses, entries = build()
        with tempfile.TemporaryDirectory() as tmp:
            dict_path, tsv_path = bf.write_outputs(tmp, glosses, entries, "2026.01.01")
            with open(dict_path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertTrue(text.startswith(bf.MARKER + "\n"))
            self.assertIn("name: francais", text)
            with open(tsv_path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            self.assertEqual(lines[2], "# sorted")
            keys = [l.split("\t")[0] for l in lines[3:]]
            self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
