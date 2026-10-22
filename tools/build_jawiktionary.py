#!/usr/bin/env python3
"""Build japanese_gloss/jawiktionary.tsv: Japanese glosses of Chinese words.

Usage: tools/build_jawiktionary.py [--source FILE] [--zh-source FILE] [--output FILE]
  --source FILE     Japanese Wiktionary raw-wiktextract-data.jsonl[.gz] (kaikki.org);
                    default: download (~65 MB)
  --zh-source FILE  Chinese Wiktionary, the same format; default: download (~230 MB)
  --output FILE     default: japanese_gloss/jawiktionary.tsv in this repository

The glosses come from the Chinese entries of the Japanese Wiktionary (about
42 000 words): 走 -> 歩(ある)く; 行(い)く, with the readings of its ruby.
Words it lacks get the Japanese translations listed in the Chinese Wiktionary
(工作 -> 仕事(しごと)、労働(ろうどう)). Proper names come last.

Every entry is written under its Traditional and its Simplified headword, as
the filter does not convert this dictionary's keys. A word whose entry gives
only one script also gets a key converted character by character, with a
mapping learnt from the words that give both. Standard library only.
"""
import argparse
import collections
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dewiktionary  # noqa: E402
import build_handedict  # noqa: E402

JA_URL = "https://kaikki.org/jawiktionary/raw-wiktextract-data.jsonl.gz"
ZH_URL = build_dewiktionary.ZH_WIKTIONARY_URL
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHINESE = {"zh", "cmn"}
HAS_HAN = build_dewiktionary.HAS_HAN
MAX_TRANSLATIONS = 4
SAME_AS_JAPANESE = re.compile(r"[（(]日本語(?:語義\d*)?に同じ[）)]")
# Notes in ASCII brackets, "(疑問代名詞) 何", are written "（疑問代名詞）何" like the
# rest, so the same gloss in both styles is shown once.
ASCII_NOTE = re.compile(r"\(([^()]*)\)\s*")
KANA = re.compile(r"^[ぁ-ゟァ-ヿー]+$")


# ---- glosses ---------------------------------------------------------------

def add_ruby(text, ruby):
    """Insert the reading of each [base, reading] pair after the first
    occurrence of its base, left to right: 歩く + [歩, ある] -> 歩(ある)く."""
    out, pos = [], 0
    for pair in ruby or []:
        if len(pair) != 2 or not pair[0] or pair[0] == pair[1]:
            continue
        base, reading = pair
        at = text.find(base, pos)
        if at < 0:
            continue
        end = at + len(base)
        out.append(text[pos:end] + "(" + reading + ")")
        pos = end
    return "".join(out) + text[pos:]


def clean(gloss, ruby=None):
    gloss = ASCII_NOTE.sub(r"（\1）", SAME_AS_JAPANESE.sub("", gloss)).replace("~", "～")
    gloss = " ".join(add_ruby(gloss, ruby).split()).strip(" 。．.、，,;；")
    return gloss.replace("。", "、")


def drop_repeats(glosses):
    """Leave out a gloss whose items (split at 、) all appear in earlier glosses
    or in one longer gloss: 飛行機; 飛行機、航空機 -> 飛行機、航空機."""
    glosses = list(dict.fromkeys(glosses))
    sets = [set(g.split("、")) for g in glosses]
    seen, result = set(), []
    for gloss, items in zip(glosses, sets):
        if items <= seen or any(items < other for other in sets):
            continue
        result.append(gloss)
        seen |= items
    return result


def with_reading(word, reading):
    """仕事 + しごと -> 仕事(しごと); 働く + はたらく -> 働(はたら)く."""
    if not reading or not HAS_HAN.search(word) or not KANA.match(reading):
        return word
    head, tail = word, ""
    while head and reading and head[-1] == reading[-1] and not HAS_HAN.match(head[-1]):
        head, reading, tail = head[:-1], reading[:-1], head[-1] + tail
    return "%s(%s)%s" % (head, reading, tail) if head and reading else word


def variants(entry):
    """The Traditional and Simplified spellings an entry gives for its word."""
    return [f["form"] for f in entry.get("forms") or []
            if f.get("form") and {"Traditional-Chinese", "Simplified-Chinese"} & set(f.get("tags", []))]


def script_pair(entry):
    """(traditional, simplified) when the entry gives both, else None."""
    trad = simp = None
    for f in entry.get("forms") or []:
        tags = set(f.get("tags", []))
        if "Traditional-Chinese" in tags:
            trad = f.get("form")
        elif "Simplified-Chinese" in tags:
            simp = f.get("form")
    word = entry.get("word")
    if trad and not simp:
        simp = word
    elif simp and not trad:
        trad = word
    return (trad, simp) if trad and simp and trad != simp else None


# ---- sources ---------------------------------------------------------------

def read_ja(lines):
    """Return ({word: [glosses]}, {word: [proper-name glosses]}, {word: [variants]},
    [(traditional, simplified)]) from the Chinese entries of the Japanese Wiktionary."""
    glosses, names, forms, pairs = {}, {}, {}, []
    for line in lines:
        entry = json.loads(line)
        word = entry.get("word")
        if entry.get("lang_code") not in CHINESE or not word or not HAS_HAN.search(word):
            continue
        pair = script_pair(entry)
        if pair:
            pairs.append(pair)
        target = names if entry.get("pos") == "name" else glosses
        found = [clean(g, sense.get("ruby"))
                 for sense in entry.get("senses", []) for g in sense.get("glosses", [])]
        found = [g for g in found if g]
        if found:
            target.setdefault(word, []).extend(found)
            forms.setdefault(word, []).extend(variants(entry))
    return glosses, names, forms, pairs


def read_zh(lines):
    """Return ({word: [Japanese translations]}, {word: [variants]},
    [(traditional, simplified)]) from the Chinese entries of the Chinese Wiktionary."""
    translations, forms, pairs = {}, {}, []
    for line in lines:
        if '"zh"' not in line:
            continue  # most lines are other languages; skip parsing them
        entry = json.loads(line)
        word = entry.get("word")
        if entry.get("lang_code") not in CHINESE or not word or not HAS_HAN.search(word):
            continue
        pair = script_pair(entry)
        if pair:
            pairs.append(pair)
        items = list(entry.get("translations") or [])
        for sense in entry.get("senses", []):
            items.extend(sense.get("translations") or [])
        found = [with_reading(t["word"], (t.get("roman") or "").split(",")[0].strip())
                 for t in items if t.get("lang_code") == "ja" and t.get("word")]
        if found:
            translations.setdefault(word, []).extend(found)
            forms.setdefault(word, []).extend(variants(entry))
    return translations, forms, pairs


def char_map(pairs, min_count=1):
    """{Traditional char: Simplified char} learnt from (traditional, simplified)
    word pairs. A character that also appears in Simplified words keeps its
    form (乾 in 乾隆), and so does one whose pairs disagree more than agree or
    that has fewer than `min_count` pairs."""
    counts = collections.defaultdict(collections.Counter)
    simplified = set()
    for trad, simp in pairs:
        simplified.update(simp)
        if len(trad) == len(simp):
            for t, s in zip(trad, simp):
                counts[t][s] += 1
    result = {}
    for t, c in counts.items():
        s, n = c.most_common(1)[0]
        if s != t and t not in simplified and n >= min_count and n * 2 > sum(c.values()):
            result[t] = s
    return result


# ---- build -----------------------------------------------------------------

def build(ja_lines, zh_lines):
    """Return {headword: [glosses]} keyed by both scripts."""
    glosses, names, ja_forms, pairs = read_ja(ja_lines)
    translations, zh_forms, zh_pairs = read_zh(zh_lines)
    t2s = char_map(pairs + zh_pairs)

    def spellings(word, forms):
        found = [word] + forms.get(word, [])
        found.append("".join(t2s.get(c, c) for c in word))
        return list(dict.fromkeys(found))

    own, borrowed = {}, {}

    def add(word, items, forms):
        for i, key in enumerate(spellings(word, forms)):
            (own if i == 0 else borrowed).setdefault(key, []).extend(items)

    for word, items in glosses.items():
        add(word, items, ja_forms)
    for word, items in names.items():
        add(word, items, ja_forms)
    name_set = {g for items in names.values() for g in items}
    result = {}
    for key in own.keys() | borrowed.keys():
        items = drop_repeats(own.get(key, []) + borrowed.get(key, []))
        items.sort(key=lambda g: g in name_set)
        result[key] = items

    # The Chinese Wiktionary only fills in words the Japanese one lacks.
    extra = {}
    for word, items in translations.items():
        items = list(dict.fromkeys(items))[:MAX_TRANSLATIONS]
        for key in spellings(word, zh_forms):
            if key not in result:
                extra.setdefault(key, []).extend(items)
    for key, items in extra.items():
        result[key] = ["、".join(dict.fromkeys(items))]
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source")
    ap.add_argument("--zh-source")
    ap.add_argument("--output", default=os.path.join(REPO, "japanese_gloss", "jawiktionary.tsv"))
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        source = args.source or build_dewiktionary.download(JA_URL, tmp, "ja-wiktextract.jsonl.gz")
        zh_source = args.zh_source or build_dewiktionary.download(ZH_URL, tmp, "zh-wiktextract.jsonl.gz")
        print("reading %s and %s" % (source, zh_source), file=sys.stderr)
        with build_dewiktionary.open_lines(source) as ja, build_dewiktionary.open_lines(zh_source) as zh:
            entries = build(ja, zh)
    build_handedict.write(entries, args.output, [
        "Generated by tools/build_jawiktionary.py from the Japanese and Chinese Wiktionary",
        "via wiktextract (https://kaikki.org/) - licensed CC BY-SA 4.0",
    ])
    print("wrote %d headwords to %s" % (len(entries), args.output), file=sys.stderr)


if __name__ == "__main__":
    main()
