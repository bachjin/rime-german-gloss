"""Unit tests for tools/build_jawiktionary.py.  Run:  python3 tests/test_build_jawiktionary.py"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_jawiktionary as bj  # noqa: E402


def jsonl(*entries):
    return [json.dumps(e, ensure_ascii=False) for e in entries]


TRAD = {"tags": ["canonical", "Traditional-Chinese"]}
SIMP = {"tags": ["canonical", "Simplified-Chinese"]}

JA = jsonl(
    {"word": "学校", "lang_code": "zh", "pos": "noun", "forms": [dict(TRAD, form="學校")],
     "senses": [{"glosses": ["（日本語に同じ）学校。"]}]},
    {"word": "走", "lang_code": "zh", "pos": "verb",
     "senses": [{"glosses": ["歩く。"], "ruby": [["歩", "ある"]]}, {"glosses": ["行く。"], "ruby": [["行", "い"]]}]},
    {"word": "王", "lang_code": "zh", "pos": "name", "senses": [{"glosses": ["中国人の姓のひとつ。"]}]},
    {"word": "王", "lang_code": "zh", "pos": "noun", "senses": [{"glosses": ["王。"]}]},
    {"word": "什麼", "lang_code": "zh", "pos": "pron",
     "senses": [{"glosses": ["(疑問代名詞) 何"]}, {"glosses": ["何。"]}]},
    {"word": "什么", "lang_code": "zh", "pos": "pron", "forms": [dict(TRAD, form="什麼")],
     "senses": [{"glosses": ["（疑問代名詞）何"]}]},
    {"word": "飛機", "lang_code": "zh", "pos": "noun", "forms": [dict(SIMP, form="飞机")],
     "senses": [{"glosses": ["飛行機"]}]},
    {"word": "飞机", "lang_code": "zh", "pos": "noun", "forms": [dict(TRAD, form="飛機")],
     "senses": [{"glosses": ["飛行機、航空機"]}]},
    # only in Traditional: gets a Simplified key from the characters of 學校 and 飛機
    {"word": "學飛", "lang_code": "zh", "pos": "verb", "senses": [{"glosses": ["飛ぶことを学ぶ"]}]},
    {"word": "学校", "lang_code": "ja", "pos": "noun", "senses": [{"glosses": ["school"]}]},
    {"word": "ok", "lang_code": "zh", "pos": "intj", "senses": [{"glosses": ["オーケー"]}]},
)

ZH = jsonl(
    {"word": "工作", "lang_code": "zh", "pos": "noun", "translations": [
        {"lang_code": "ja", "word": "仕事", "roman": "しごと, shigoto"},
        {"lang_code": "ja", "word": "働く", "roman": "はたらく, hataraku"},
        {"lang_code": "ja", "word": "ワーク", "roman": "wāku"},
        {"lang_code": "en", "word": "work"}]},
    {"word": "学校", "lang_code": "zh", "pos": "noun", "senses": [{"translations": [
        {"lang_code": "ja", "word": "スクール"}]}]},
)


class GlossTest(unittest.TestCase):
    def test_ruby(self):
        self.assertEqual(bj.add_ruby("切り開く", [["切", "き"], ["開", "ひら"]]), "切(き)り開(ひら)く")
        self.assertEqual(bj.add_ruby("歩く", [["走", "はし"]]), "歩く")

    def test_clean(self):
        self.assertEqual(bj.clean("（日本語語義1に同じ）銀行。"), "銀行")
        self.assertEqual(bj.clean("交わる。合流する。"), "交わる、合流する")
        self.assertEqual(bj.clean("(文章語) ~に等しい"), "（文章語）～に等しい")

    def test_reading(self):
        self.assertEqual(bj.with_reading("仕事", "しごと"), "仕事(しごと)")
        self.assertEqual(bj.with_reading("働く", "はたらく"), "働(はたら)く")
        self.assertEqual(bj.with_reading("ワーク", "wāku"), "ワーク")

    def test_char_map(self):
        t2s = bj.char_map([("學校", "学校"), ("飛機", "飞机"), ("乾隆", "乾隆"), ("乾燥", "干燥")])
        self.assertEqual(t2s["學"], "学")
        self.assertNotIn("乾", t2s)  # also written in Simplified
        self.assertNotIn("校", t2s)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.entries = bj.build(JA, ZH)

    def test_both_scripts(self):
        self.assertEqual(self.entries["学校"], ["学校"])
        self.assertEqual(self.entries["學校"], ["学校"])

    def test_ruby_and_senses(self):
        self.assertEqual(self.entries["走"], ["歩(ある)く", "行(い)く"])

    def test_names_last(self):
        self.assertEqual(self.entries["王"], ["王", "中国人の姓のひとつ"])

    def test_note_styles_merged(self):
        self.assertEqual(self.entries["什么"], ["（疑問代名詞）何", "何"])
        self.assertEqual(self.entries["什麼"], ["（疑問代名詞）何", "何"])

    def test_contained_gloss_dropped(self):
        self.assertEqual(self.entries["飛機"], ["飛行機、航空機"])
        self.assertEqual(self.entries["飞机"], ["飛行機、航空機"])

    def test_converted_key(self):
        self.assertEqual(self.entries["学飞"], ["飛ぶことを学ぶ"])
        self.assertEqual(self.entries["學飛"], ["飛ぶことを学ぶ"])

    def test_chinese_wiktionary_fills_gaps(self):
        self.assertEqual(self.entries["工作"], ["仕事(しごと)、働(はたら)く、ワーク"])
        self.assertNotIn("スクール", "".join(self.entries["学校"]))

    def test_skips_other_languages_and_non_han(self):
        self.assertNotIn("school", "".join(self.entries["学校"]))
        self.assertNotIn("ok", self.entries)


if __name__ == "__main__":
    unittest.main()
