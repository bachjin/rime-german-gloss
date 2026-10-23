"""Unit tests for tools/build_dewiktionary.py.  Run:  python3 tests/test_build_dewiktionary.py"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
spec = importlib.util.spec_from_file_location("build_dewiktionary", REPO / "tools" / "build_dewiktionary.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


def entry(word, pos="noun", zh=(), form_of=(), sense_tags=(), tags=(), forms=(), lang_code="de"):
    """A wiktextract line; `forms` is [(form, [tags])]."""
    senses = [{"glosses": ["..."]}]
    tags = list(tags)
    if form_of:
        senses = [{"glosses": ["..."], "tags": ["form-of"] + list(sense_tags),
                   "form_of": [{"word": w} for w in form_of]}]
        tags.append("form-of")
    return json.dumps({
        "word": word, "pos": pos, "lang_code": lang_code, "tags": tags, "senses": senses,
        "forms": [{"form": f, "tags": t} for f, t in forms],
        "translations": [{"lang_code": "zh", "word": z} for z in zh]
                        + [{"lang_code": "en", "word": "house"}],
    }, ensure_ascii=False)


def verb(word, present, past, participle, aux, tags=()):
    forms = [(p, ["present"]) for p in present] + [(past, ["past"]),
             (participle, ["participle-2", "perfect"])] + [(a, ["auxiliary", "perfect"]) for a in aux]
    return entry(word, pos="verb", tags=tags, forms=forms)


WIKTIONARY = [
    entry("Haus", tags=["neuter"], zh=["房子", "房子"],
          forms=[("Haus", ["nominative", "singular"]), ("Häuser", ["nominative", "plural"])]),
    entry("Häuser", form_of=["Haus"], sense_tags=["nominative", "plural"]),
    entry("Haus", form_of=["Hau"], sense_tags=["genitive", "singular"]),
    entry("ging", pos="verb", form_of=["gehen"], sense_tags=["active", "indicative", "past", "singular"]),
    entry("gegangen", pos="verb", form_of=["gehen"], sense_tags=["perfect"]),
    verb("gehen", ["gehe", "gehst", "geht"], "ging", "gegangen", ["sein"]),
    entry("müde", pos="adj", forms=[("müder", ["comparative"]), ("am müdesten", ["superlative"])]),
    entry("gut", pos="adj", zh=["好"], forms=[("besser", ["comparative"]), ("am besten", ["superlative"])]),
    entry("besser", pos="adj", form_of=["gut"]),
    entry("Essen", pos="name", zh=["埃森"]),
    entry("Essen", tags=["neuter"], zh=["食物"]),
    entry("zum Beispiel", pos="phrase", zh=["例如"]),
    entry("House", lang_code="en", zh=["屋"]),
    entry("Fuß", tags=["masculine"], zh=["腳"]),
    entry("gingen", pos="verb", form_of=["gehen"], sense_tags=["past", "plural"]),
    entry("Wörter", form_of=["Wort"], sense_tags=["plural"]),
    entry("Häusern", pos="name"),
    entry("Häusern", form_of=["Haus"], sense_tags=["dative", "plural"]),
    entry("Leute", forms=[("Leute", ["nominative", "plural"])]),
    entry("Teil", tags=["masculine", "neuter"]),
    entry("für", pos="prep"),
]

ZH_WIKTIONARY = [
    json.dumps({"word": "gehen", "lang_code": "de", "senses": [
        {"glosses": ["走，步行"]}, {"glosses": ["離開，走"]},
        {"glosses": ["進展；順利 [接 與格 「對某人」] (習慣上將與格受詞作為主詞翻譯)"]},
        {"glosses": ["開出"]}]}, ensure_ascii=False),
    json.dumps({"word": "hausen", "lang_code": "de", "senses": [
        {"glosses": ["* 国际音标^(): /ˈhaʊ̯zn̩/"]}, {"glosses": ["v. 居住"]}]}, ensure_ascii=False),
    json.dumps({"word": "ging", "lang_code": "de", "senses": [
        {"glosses": ["gehen 的過去時"], "tags": ["form-of"]}]}, ensure_ascii=False),
    json.dumps({"word": "für", "lang_code": "de", "senses": [
        {"glosses": ["（支配宾格）为了、为…"]}, {"glosses": ["for"]}]}, ensure_ascii=False),
    json.dumps({"word": "go", "lang_code": "en", "senses": [{"glosses": ["走"]}]}),
]

HANDEDICT = """# comment
累 累 [lei4] /müde (Adj)/
困 困 [kun4] /matt (Adj)/müde (Adj)/
房子 房子 [fang2 zi5] /das Haus (S)/
腳 脚 [jiao3] /Fuß (S)/
腳 脚 [jiao3] /Fuss (S)/
離 离 [li2] /verlassen (V)/
事 事 [shi4] /Sache (S)/
事 亊 [shi4] /Sache (S)/
埃森 埃森 [ai1 sen1] /Essen (Eig, Geo)/
走 走 [zou3] /gehen, laufen (V); Bsp.: 走路 走路 -- zu Fuß gehen/
""".splitlines()


class FoldTest(unittest.TestCase):
    def test_umlauts_and_eszett(self):
        self.assertEqual(bd.fold("müde"), "muede")
        self.assertEqual(bd.fold("Straße"), "strasse")
        self.assertEqual(bd.fold("Ärger"), "aerger")

    def test_other_diacritics_are_stripped(self):
        self.assertEqual(bd.fold("Café"), "cafe")

    def test_not_encodable(self):
        self.assertIsNone(bd.fold("E-Mail"))
        self.assertIsNone(bd.fold("zum Beispiel"))
        self.assertIsNone(bd.fold("A4"))

    def test_codes(self):
        self.assertEqual(bd.codes("müde"), [("muede", False), ("mude", True)])
        self.assertEqual(bd.codes("Straße"), [("strasse", False)])
        self.assertEqual(bd.codes("Haus"), [("haus", False)])
        self.assertEqual(bd.codes("E-Mail"), [])


class GrammarTest(unittest.TestCase):
    def grammar(self, line):
        o = json.loads(line)
        return bd.grammar_of(o["word"], o)

    def test_strong_verb(self):
        self.assertEqual(self.grammar(verb("sprechen", ["spreche", "sprichst", "spricht"],
                                           "sprach", "gesprochen", ["haben"])),
                         "动 不规则 · spricht, sprach, hat gesprochen")

    def test_strong_verb_without_vowel_change(self):
        self.assertEqual(self.grammar(verb("gehen", ["gehe", "gehst", "geht"], "ging", "gegangen", ["sein"])),
                         "动 不规则 · ging, ist gegangen")

    def test_mixed_verb_is_irregular(self):
        self.assertEqual(self.grammar(verb("bringen", ["bringe", "bringst", "bringt"],
                                           "brachte", "gebracht", ["haben"])),
                         "动 不规则 · brachte, hat gebracht")

    def test_separable_verb(self):
        self.assertEqual(self.grammar(verb("anfangen", ["fange an", "fängst an", "fängt an"],
                                           "fing an", "angefangen", ["haben", "sein"])),
                         "动 不规则 · fängt an, fing an, hat/ist angefangen")
        self.assertEqual(self.grammar(verb("aufmachen", ["mache auf", "machst auf", "macht auf"],
                                           "machte auf", "aufgemacht", ["haben"])), "动")

    def test_regular_verbs(self):
        self.assertEqual(self.grammar(verb("machen", ["mache", "machst", "macht"], "machte", "gemacht", ["haben"])), "动")
        self.assertEqual(self.grammar(verb("arbeiten", ["arbeite", "arbeitest", "arbeitet"],
                                           "arbeitete", "gearbeitet", ["haben"])), "动")
        self.assertEqual(self.grammar(verb("sammeln", ["sammle", "sammelst", "sammelt"],
                                           "sammelte", "gesammelt", ["haben"])), "动")
        self.assertEqual(self.grammar(verb("reisen", ["reise", "reist", "reist"], "reiste", "gereist", ["sein"])),
                         "动 · ist gereist")

    def test_irregular_tag(self):
        self.assertEqual(self.grammar(verb("x", [], "xte", "gext", [], tags=["irregular"])),
                         "动 不规则 · xte, gext")

    def test_nouns(self):
        self.assertEqual(self.grammar(WIKTIONARY[0]), "das · 复数 Häuser")
        self.assertEqual(self.grammar(entry("Teil", tags=["masculine", "neuter"])), "der/das")
        self.assertEqual(self.grammar(entry("Leute", forms=[("Leute", ["nominative", "plural"])])), "复数 Leute")
        self.assertEqual(self.grammar(entry("Obst", tags=["neuter"], forms=[("—", ["nominative", "plural"])])), "das")

    def test_adjectives(self):
        self.assertEqual(self.grammar(entry("gut", pos="adj", forms=[("besser", ["comparative"]),
                                                                        ("am besten", ["superlative"])])),
                         "形 · besser, am besten")
        self.assertEqual(self.grammar(entry("müde", pos="adj", forms=[("müder", ["comparative"])])), "形")
        self.assertEqual(self.grammar(entry("schön", pos="adj", forms=[("schöner", ["comparative"])])), "形")

    def test_other_parts_of_speech(self):
        self.assertEqual(self.grammar(entry("für", pos="prep")), "介")
        self.assertEqual(self.grammar(entry("Beispiel", pos="phrase")), "")

    def test_form_labels(self):
        self.assertEqual(bd.form_label(["form-of", "active", "indicative", "past", "singular"]), "过去式")
        self.assertEqual(bd.form_label(["form-of", "perfect"]), "第二分词")
        self.assertEqual(bd.form_label(["form-of", "present", "singular", "subjunctive"]), "第一虚拟式")
        self.assertEqual(bd.form_label(["form-of", "nominative", "plural"]), "复数")
        self.assertEqual(bd.form_label(["form-of", "genitive", "singular"]), "变格")
        self.assertEqual(bd.form_label(["form-of"]), "变形")


class SourcesTest(unittest.TestCase):
    def test_wiktionary(self):
        translations, names, forms, lemmas, grammar = bd.read_wiktionary(WIKTIONARY)
        self.assertEqual(translations["Haus"], ["房子"])
        self.assertEqual(translations["Essen"], ["食物"])
        self.assertEqual(names["Essen"], ["埃森"])
        self.assertEqual(forms["Häuser"], [("Haus", "复数")])
        self.assertEqual(forms["Haus"], [("Hau", "变格")])
        self.assertEqual(forms["ging"], [("gehen", "过去式")])
        self.assertEqual(forms["besser"], [("gut", "比较级")])   # label from gut's forms
        self.assertIn("Haus", lemmas)
        self.assertNotIn("Häuser", lemmas)
        self.assertNotIn("zum Beispiel", lemmas)
        self.assertNotIn("House", lemmas)
        self.assertEqual(grammar["Haus"], "das · 复数 Häuser")    # from the first entry
        self.assertEqual(grammar["Essen"], "das")                # the name entry has none
        self.assertNotIn("Häuser", grammar)

    def test_zh_wiktionary(self):
        glosses = bd.read_zh_wiktionary(ZH_WIKTIONARY)
        self.assertEqual(glosses["gehen"], ["走，步行", "離開，走", "進展；順利", "開出"])
        self.assertEqual(glosses["für"], ["（支配宾格）为了、为…"])   # "for" has no Chinese
        self.assertNotIn("ging", glosses)                           # form-of senses skipped
        self.assertNotIn("go", glosses)
        self.assertEqual(glosses["hausen"], ["居住"])      # no pronunciation, no "v."
        self.assertEqual(bd.clean_gloss("①流产\n②堕胎 miscarriage\n"), "①流产; ②堕胎 miscarriage")

    def test_handedict_reverse(self):
        reverse, t2s = bd.read_handedict(HANDEDICT, {"累": 100, "困": 50})
        self.assertEqual(reverse["müde"], ["累", "困"])
        self.assertEqual(reverse["Haus"], ["房子"])
        self.assertEqual(reverse["gehen"], ["走"])
        self.assertNotIn("Essen", reverse)          # proper names are skipped
        self.assertNotIn("Fuß gehen", reverse)      # examples are stripped
        self.assertEqual(t2s["腳"], "脚")
        self.assertNotIn("事", t2s)                 # also Simplified: 事 stays 事

    def test_frequency_rank_beats_position(self):
        lines = ["適於 适于 [shi4 yu2] /für (P)/", "給 给 [gei3] /geben (V)/für; zu (P)/"]
        reverse, _ = bd.read_handedict(lines, {"給": 10000, "適於": 10})
        self.assertEqual(reverse["für"], ["给", "适于"])
        reverse, _ = bd.read_handedict(lines)
        self.assertEqual(reverse["für"], ["适于", "给"])

    def test_split_items(self):
        self.assertEqual(bd.split_items("für (P, a), zu; um"), ["für (P, a)", " zu", " um"])
        self.assertEqual(bd.german_word("die Straße (S)"), "Straße")
        self.assertIsNone(bd.german_word("die Straße überqueren (V)"))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.wiktionary = bd.read_wiktionary(WIKTIONARY)
        self.zh = bd.read_zh_wiktionary(ZH_WIKTIONARY)
        self.reverse, self.t2s = bd.read_handedict(HANDEDICT)
        freq = {"haus": 100, "müde": 50}
        self.glosses, self.entries = bd.build(*self.wiktionary, self.zh, self.reverse, self.t2s, freq)

    def test_lemma_glosses(self):
        self.assertEqual(self.glosses["Haus"], "das · 复数 Häuser · 房子")
        self.assertEqual(self.glosses["müde"], "形 · 累; 困")
        self.assertEqual(self.glosses["Fuß"], "der · 脚")                    # simplified
        self.assertEqual(self.glosses["Essen"], "das · 食物; 埃森")          # name last
        self.assertEqual(self.glosses["gehen"], "动 不规则 · ging, ist gegangen · 走，步行; 离開，走; 進展；順利")  # only 離 is in the t2s fixture
        self.assertEqual(self.glosses["für"], "介 · （支配宾格）为了、为…")
        self.assertEqual(self.glosses["Teil"], "der/das")                    # grammar without Chinese

    def test_form_glosses(self):
        self.assertEqual(self.glosses["Häuser"], "Haus 的复数 · 房子")
        self.assertEqual(self.glosses["ging"], "gehen 的过去式 · 走，步行")
        self.assertEqual(self.glosses["gegangen"], "gehen 的第二分词 · 走，步行")
        self.assertEqual(self.glosses["besser"], "gut 的比较级 · 好")
        self.assertEqual(self.glosses["Häusern"], "Haus 的复数 · 房子")      # also a lemma, no Chinese

    def test_forms_without_chinese_are_typeable_but_unglossed(self):
        self.assertNotIn("Wörter", self.glosses)
        self.assertIn(("Wörter", "woerter"), [(e[0], e[1]) for e in self.entries])
        self.assertIn(("Wörter", "worter"), [(e[0], e[1]) for e in self.entries])

    def test_weights(self):
        weight = {(w, c): x for w, c, x in self.entries}
        self.assertEqual(weight[("Haus", "haus")], 1003)
        self.assertEqual(weight[("müde", "muede")], 504)   # lowercase lemma
        self.assertLess(weight[("müde", "mude")], weight[("müde", "muede")])
        self.assertGreater(weight[("Fuß", "fuss")], weight[("Wörter", "woerter")])

    def test_no_forms(self):
        glosses, entries = bd.build(*self.wiktionary, {}, {}, {}, {}, with_forms=False)
        words = {e[0] for e in entries}
        self.assertNotIn("Wörter", words)
        self.assertNotIn("ging", words)
        self.assertIn("Haus", words)

    def test_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.glosses["Abort"] = "der · 厕所\n②流产\tx"
            dict_path, tsv_path = bd.write_outputs(tmp, self.glosses, self.entries, "2026.10.19")
            text = Path(dict_path).read_text(encoding="utf-8")
            self.assertTrue(text.startswith(bd.MARKER))
            self.assertIn("name: deutsch\n", text)
            self.assertIn('version: "2026.10.19"\n', text)
            self.assertIn("\n...\n", text)
            self.assertIn("müde\tmude\t", text)
            tsv = Path(tsv_path).read_text(encoding="utf-8").splitlines()
            self.assertTrue(tsv[0].startswith(bd.MARKER))
            self.assertIn("# sorted", tsv[:3])
            keys = [l.split("\t")[0] for l in tsv if not l.startswith("#")]
            self.assertEqual(keys, sorted(keys, key=lambda k: k.encode("utf-8")))
            self.assertIn("Abort\tder · 厕所 ②流产 x", tsv)
            self.assertIn("Häuser\tHaus 的复数 · 房子", tsv)


if __name__ == "__main__":
    unittest.main()
