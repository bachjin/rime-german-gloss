"""Unit tests for tools/build_ja_zh.py.  Run:  python3 tests/test_build_ja_zh.py"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_ja_zh as bz  # noqa: E402


def jsonl(*entries):
    return [json.dumps(e, ensure_ascii=False) for e in entries]


def pair(trad, simp):
    """Two Chinese entries that teach char_map trad -> simp."""
    return [{"word": trad, "lang_code": "zh", "pos": "noun",
             "forms": [{"form": simp, "tags": ["Simplified-Chinese"]}]}] * 2


ZH = jsonl(
    {"word": "仕事", "lang_code": "ja", "pos": "noun",
     "senses": [{"glosses": ["工作，職業"]}, {"glosses": ["任務"]}, {"glosses": ["功"]}, {"glosses": ["業績"]}]},
    {"word": "食べる", "lang_code": "ja", "pos": "verb", "senses": [{"glosses": ["吃"]}],
     "forms": [{"form": "食べた", "tags": ["past"]}, {"form": "食べ", "tags": ["continuative"]},
               {"form": "食べられる", "tags": [], "raw_tags": ["常用構式", "被動"]},
               {"form": "喰べる", "tags": ["alternative"]}]},
    {"word": "たべる", "lang_code": "ja", "pos": "soft-redirect", "senses": [{"tags": ["no-gloss"]}],
     "redirects": ["食べる"]},
    {"word": "はし", "lang_code": "ja", "pos": "soft-redirect", "redirects": ["箸", "橋", "無い"]},
    {"word": "箸", "lang_code": "ja", "pos": "noun", "senses": [{"glosses": ["筷子"]}]},
    {"word": "橋", "lang_code": "ja", "pos": "noun", "senses": [{"glosses": ["橋樑"]}]},
    {"word": "突破", "lang_code": "ja", "pos": "unknown", "senses": [{"glosses": [
        "突破【とっぱ】\n名?他サ 突破，冲破。\n難関を突破する\n突破难关。"]}]},
    {"word": "発生", "lang_code": "ja", "pos": "unknown", "senses": [{"glosses": [
        "発生【はっせい】\n1. 发生。\n例文\n2. 出现。"]}]},
    {"word": "山下", "lang_code": "ja", "pos": "name", "senses": [{"glosses": ["姓氏"]}]},
    {"word": "山下", "lang_code": "ja", "pos": "noun", "senses": [{"glosses": ["山腳"]}]},
    {"word": "taberu", "lang_code": "ja", "pos": "romanization", "senses": [{"glosses": ["たべる 的罗马字转写"]}]},
    {"word": "著し", "lang_code": "ja", "pos": "adj", "senses": [
        {"glosses": ["著しい的古典日語寫法"], "tags": ["alt-of"], "alt_of": [{"word": "著しい"}]}]},
    {"word": "学校", "lang_code": "ko", "pos": "noun", "senses": [{"glosses": ["不是日语"]}]},
    *[e for t, s in (("職", "职"), ("務", "务"), ("樑", "梁"), ("業", "业")) for e in pair(t, s)],
)

JA = jsonl(
    {"word": "パソコン", "lang_code": "ja", "pos": "noun", "translations": [
        {"lang_code": "zh", "word": "個人電腦"}, {"lang_code": "en", "word": "PC"}]},
    {"word": "仕事", "lang_code": "ja", "pos": "noun", "translations": [{"lang_code": "zh", "word": "活儿"}]},
)


class SensesTest(unittest.TestCase):
    def test_imported(self):
        self.assertEqual(bz.imported_senses("突破【とっぱ】\n名?他サ 突破，冲破。\n難関を突破する"),
                         ["名·他サ 突破，冲破"])
        self.assertEqual(bz.imported_senses("発生【はっせい】\n1. 发生。\n例文\n2. 出现。"), ["发生", "出现"])
        self.assertEqual(bz.imported_senses("纵弹性模量。"), ["纵弹性模量"])

    def test_clean(self):
        self.assertEqual(bz.clean(" 已经。 "), "已经")
        self.assertEqual(bz.clean("（this）"), "")
        self.assertEqual(bz.clean("???"), "")


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zh = bz.read_zh(ZH)
        cls.entries = bz.build(cls.zh, bz.read_ja(JA))

    def test_read(self):
        self.assertNotIn("taberu", self.zh["glosses"])
        self.assertNotIn("著し", self.zh["glosses"])
        self.assertEqual(self.zh["labels"]["食べる"], "动")
        self.assertEqual(self.zh["forms"]["食べた"], ("食べる", "过去式"))
        self.assertEqual(self.zh["forms"]["食べられる"], ("食べる", "被动形"))
        self.assertNotIn("食べ", self.zh["forms"])
        self.assertEqual(self.zh["spellings"]["喰べる"], "食べる")

    def test_glosses(self):
        e = self.entries
        self.assertEqual(e["仕事"], "名 · 工作，职业; 任务; 功")  # three senses, simplified
        self.assertEqual(e["食べる"], "动 · 吃")
        self.assertEqual(e["突破"], "名·他サ 突破，冲破")
        self.assertEqual(e["山下"], "名 · 山腳; 姓氏")  # the name last; no pair for 腳

    def test_pointers(self):
        e = self.entries
        self.assertEqual(e["たべる"], "食べる · 动 · 吃")
        self.assertEqual(e["はし"], "箸 · 筷子 / 橋 · 橋梁")
        self.assertEqual(e["喰べる"], "动 · 吃")
        self.assertEqual(e["食べた"], "食べる 的过去式 · 吃")

    def test_japanese_wiktionary_fills_gaps(self):
        self.assertEqual(self.entries["パソコン"], "個人電腦")  # no pairs for 個, 電, 腦
        self.assertNotIn("活儿", self.entries["仕事"])


if __name__ == "__main__":
    unittest.main()
