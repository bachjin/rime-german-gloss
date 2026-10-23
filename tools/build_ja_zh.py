#!/usr/bin/env python3
"""Build japanese_input/ja_zh.tsv: Chinese glosses of Japanese words.

Usage: tools/build_ja_zh.py [--zh-source FILE] [--source FILE] [--output FILE]
  --zh-source FILE  Chinese Wiktionary raw-wiktextract-data.jsonl[.gz] (kaikki.org);
                    default: download (~230 MB)
  --source FILE     Japanese Wiktionary, the same format; default: download (~65 MB)
  --output FILE     default: japanese_input/ja_zh.tsv in this repository

The glosses come from the Japanese entries of the Chinese Wiktionary (about
60 000 words): 仕事 -> 名 · 工作，职业; 任务; 功. Its kana redirects, the
alternative spellings it lists (有難う for ありがとう) and some inflected forms
(食べた -> 食べる 的过去式 · 吃) point to the same gloss. Words it lacks get
the Chinese translations of the Japanese Wiktionary. Proper names come last.
Traditional characters are simplified with a mapping learnt from the Chinese
entries that give both scripts. Standard library only.
"""
import argparse
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dewiktionary  # noqa: E402
import build_handedict  # noqa: E402
import build_jawiktionary  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHINESE = build_jawiktionary.CHINESE
HAS_HAN = build_dewiktionary.HAS_HAN
MAX_SENSES = 3
MAX_REDIRECTS = 3
SKIP_POS = {"romanization", "character", "syllable", "soft-redirect"}
POS_LABELS = {"noun": "名", "verb": "动", "adj": "形", "adj_noun": "形动", "adv": "副",
              "pron": "代", "intj": "叹", "conj": "接", "particle": "助", "num": "数",
              "counter": "量", "prefix": "前缀", "suffix": "后缀"}
# Inflected forms worth a gloss of their own, by the tags of the inflection table.
FORM_LABELS = {("past",): "过去式", ("formal",): "ます形", ("informal", "negative"): "否定形",
               ("causative",): "使役形"}
PASSIVE = "被動"
# Sense numbers of the imported dictionary entries: "1. 出现", "①出现".
NUMBERED = re.compile(r"^\s*(?:\d+[.．、]|[①-⑳])\s*")
# Their part of speech, "名·他サ 突破", written with "?" or "•" in some entries.
IMPORTED_POS = re.compile(r"^((?:名|自|他|形|副|连体|代|接|感|词组|惯)[^\s，,]{0,6})\s+")
NOTE_ONLY = re.compile(r"^[（(][^（）()]*[）)]$")


# ---- glosses ---------------------------------------------------------------

def clean(gloss):
    gloss = " ".join(gloss.split()).strip(" 。.;；")
    return gloss if HAS_HAN.search(gloss) and not NOTE_ONLY.match(gloss) else ""


def imported_senses(gloss):
    """The senses of a gloss taken from a printed dictionary:
    "突破【とっぱ】\\n名·他サ 突破，冲破。\\n難関を突破する\\n突破难关。"
    -> ["名·他サ 突破，冲破"]; the lines after the first are examples, except
    numbered senses ("1. 出现\\n2. 发生")."""
    lines = [l for l in gloss.split("\n") if l.strip()]
    if lines and "【" in lines[0] and len(lines) > 1:
        lines = lines[1:]
    if not lines:
        return []
    numbered = [NUMBERED.sub("", l) for l in lines if NUMBERED.match(l)]
    if NUMBERED.match(lines[0]) and numbered:
        found = numbered
    else:
        found = [lines[0]]
    result = []
    for sense in found:
        sense = re.sub(r"[?•・]", "·", sense) if IMPORTED_POS.match(sense) else sense
        result.append(clean(sense))
    return [s for s in result if s]


def form_label(form):
    """What an inflected form of the inflection table is, or None."""
    tags = tuple(sorted(form.get("tags", [])))
    if not tags and PASSIVE in (form.get("raw_tags") or []):
        return "被动形"
    return FORM_LABELS.get(tags)


# ---- sources ---------------------------------------------------------------

def read_zh(lines):
    """Read the Chinese Wiktionary. Return a dict with
      glosses    {word: [senses]}          words other than proper names
      names      {word: [senses]}          proper names
      labels     {word: part-of-speech}    of its first entry that has one
      redirects  {kana: [words]}           soft redirects (きれい -> 綺麗)
      spellings  {spelling: word}          alternative spellings (有難う)
      forms      {form: (word, label)}     inflected forms (食べた)
      pairs      [(traditional, simplified)] of the Chinese entries"""
    glosses, names, labels, redirects, spellings, forms, pairs = {}, {}, {}, {}, {}, {}, []
    for line in lines:
        if '"ja"' not in line and '"zh"' not in line:
            continue  # most lines are other languages; skip parsing them
        entry = json.loads(line)
        word, lang = entry.get("word"), entry.get("lang_code")
        if not word:
            continue
        if lang in CHINESE:
            pair = build_jawiktionary.script_pair(entry)
            if pair:
                pairs.append(pair)
            continue
        if lang != "ja":
            continue
        pos = entry.get("pos")
        if pos == "soft-redirect":
            redirects.setdefault(word, []).extend(entry.get("redirects") or [])
            continue
        if pos in SKIP_POS:
            continue
        found = []
        for sense in entry.get("senses", []):
            if {"form-of", "alt-of", "no-gloss"} & set(sense.get("tags", [])):
                continue
            for gloss in sense.get("glosses", []):
                found.extend(imported_senses(gloss) if pos == "unknown" else
                             [clean(g) for g in gloss.split("\n")[:1]])
        found = [g for g in found if g]
        if not found:
            continue
        (names if pos == "name" else glosses).setdefault(word, []).extend(found)
        if pos in POS_LABELS:
            labels.setdefault(word, POS_LABELS[pos])
        for form in entry.get("forms") or []:
            text, tags = form.get("form", ""), set(form.get("tags", []))
            if not text or text == word or text.startswith("-"):
                continue
            if "alternative" in tags:
                spellings.setdefault(text, word)
            elif pos in ("verb", "adj", "adj_noun"):
                label = form_label(form)
                if label:
                    forms.setdefault(text, (word, label))
    return {"glosses": glosses, "names": names, "labels": labels, "redirects": redirects,
            "spellings": spellings, "forms": forms, "pairs": pairs}


def read_ja(lines):
    """{Japanese word: [Chinese translations]} from the Japanese Wiktionary."""
    translations = {}
    for line in lines:
        if '"zh"' not in line and '"cmn"' not in line:
            continue
        entry = json.loads(line)
        word = entry.get("word")
        if entry.get("lang_code") != "ja" or not word:
            continue
        found = [t["word"] for t in entry.get("translations") or []
                 if t.get("lang_code") in CHINESE and HAS_HAN.search(t.get("word", ""))]
        if found:
            translations.setdefault(word, []).extend(found)
    return translations


# ---- build -----------------------------------------------------------------

def build(zh, ja_translations):
    """Return {Japanese word: gloss}."""
    # Two pairs at least: a single (澈, 彻) would turn 清澈 into 清彻.
    t2s = build_jawiktionary.char_map(zh["pairs"], min_count=2)

    def simplify(text):
        return "".join(t2s.get(c, c) for c in text)

    def senses_of(word):
        found = [simplify(g) for g in zh["glosses"].get(word, [])]
        found = list(dict.fromkeys(found))[:MAX_SENSES]
        found += list(dict.fromkeys(simplify(g) for g in zh["names"].get(word, [])))[:1]
        return found

    result = {}
    for word in zh["glosses"].keys() | zh["names"].keys():
        senses = senses_of(word)
        label = zh["labels"].get(word) if word in zh["glosses"] else ""
        result[word] = (label + " · " if label else "") + "; ".join(senses)

    # Alternative spellings and kana, unless they have an entry of their own.
    extra = {}
    for spelling, word in zh["spellings"].items():
        if spelling not in result and word in result:
            extra[spelling] = result[word]
    for kana, targets in zh["redirects"].items():
        if kana in result:
            continue
        targets = [t for t in dict.fromkeys(targets) if t in result][:MAX_REDIRECTS]
        if len(targets) == 1:
            extra[kana] = targets[0] + " · " + result[targets[0]]
        elif targets:
            extra[kana] = " / ".join("%s · %s" % (t, senses_of(t)[0]) for t in targets)
    for form, (word, label) in zh["forms"].items():
        if form not in result and form not in extra and word in result:
            extra[form] = "%s 的%s · %s" % (word, label, senses_of(word)[0])
    for word, items in ja_translations.items():
        if word not in result and word not in extra:
            extra[word] = "、".join(list(dict.fromkeys(simplify(t) for t in items))[:4])
    result.update(extra)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zh-source")
    ap.add_argument("--source")
    ap.add_argument("--output", default=os.path.join(REPO, "japanese_input", "ja_zh.tsv"))
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        zh_source = args.zh_source or build_dewiktionary.download(
            build_dewiktionary.ZH_WIKTIONARY_URL, tmp, "zh-wiktextract.jsonl.gz")
        source = args.source or build_dewiktionary.download(
            build_jawiktionary.JA_URL, tmp, "ja-wiktextract.jsonl.gz")
        print("reading %s and %s" % (zh_source, source), file=sys.stderr)
        with build_dewiktionary.open_lines(zh_source) as fh:
            zh = read_zh(fh)
        with build_dewiktionary.open_lines(source) as fh:
            ja_translations = read_ja(fh)
    entries = build(zh, ja_translations)
    build_handedict.write({k: [v] for k, v in entries.items()}, args.output, [
        "Generated by tools/build_ja_zh.py from the Chinese and Japanese Wiktionary",
        "via wiktextract (https://kaikki.org/) - licensed CC BY-SA 4.0",
    ])
    print("wrote %d headwords to %s" % (len(entries), args.output), file=sys.stderr)


if __name__ == "__main__":
    main()
