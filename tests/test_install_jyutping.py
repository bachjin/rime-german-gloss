"""Unit tests for install-jyutping.py.  Run:  python3 tests/test_install_jyutping.py"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install_jyutping", REPO / "install-jyutping.py")
ij = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ij)

TEMPLATE = r"""# Rime schema template
engine:
  translators:
    - script_translator
  filters:
    - dictionary_lookup_filter
    - simplifier

dictionary_lookup_filter:
  dictionary: jyut6ping3_scolar

translator:
  dictionary: jyut6ping3
  always_show_comments: true
  comment_format:
    - xform/^/\f/
    - xform/~//
"""
SCHEMA = r"""__include: template:/

luna_pinyin:
  tag: luna_pinyin
  tips: 〔普通話〕
  comment_format:
    - xform/^/\v/

loengfan:
  tips: 〔粵語兩分〕
  comment_format:
    - xform/^/\v/
    - xform/~//

cangjie:
  comment_format:
    - 'xform/^/\v/'
    - "xlit|ab|日月|"
  __patch:
    - common:/use_cangjie3?
"""
FULL_SCHEMA = r"""__include: template:/

schema:
  dependencies:
    - jyut6ping3_scolar
    - luna_pinyin

engine:
  translators:
    - script_translator@luna_pinyin

luna_pinyin:
  tag: luna_pinyin
  dictionary: luna_pinyin
  prefix: "`p"
  tips: 〔普通話〕
  preedit_format:
    - xform/([nl])v/$1ü/
    - xform/([jqxy])v/$1u/
  comment_format:
    - xform/^/\v/

loengfan:
  dictionary: loengfan
  tips: 〔粵語兩分〕
  preedit_format:
    - xform/a/b/
"""
DICT = "\n---\nname: jyut6ping3\nsort: by_weight\nuse_preset_vocabulary: true\n...\n\n香\thoeng1\t100.0%\n"
SCOLAR = "\n".join([
    "---", "name: jyut6ping3_scolar", "...", "",
    "hong2,,,,,,,2,,,n,,,,,,bank,,,,\t行",
    "hong4,,,,,,,1,,,mw,,,,,,\"row, profession\",व्यवसाय,شعبہ,,\t行",
    "aa1,,,,,,,1,,,,,,,,,,,,,\t㝞",
    "baau2tou5,,,,,,,1,,,adj,yue,,有飽腹感,,,\"filling, satiated\",,,,seutuh\t飽肚",
    "no tab here",
    "",
])


class TransformTest(unittest.TestCase):
    def test_template(self):
        lines = ij.patch_template(TEMPLATE, ["eng", "hin"], 10).split("\n")
        self.assertIn("    - " + ij.FILTER, lines)
        self.assertLess(lines.index("    - " + ij.FILTER), lines.index("    - simplifier"))
        self.assertNotIn("    - dictionary_lookup_filter", lines)
        self.assertNotIn("    - xform/^/\\f/", lines)
        self.assertIn("    - xform/~//", lines)
        self.assertEqual(lines[lines.index("translator:") + 1], "  spelling_hints: 10")
        self.assertEqual(lines[-7:], ["", "typeduck_gloss:", "  languages: [ eng, hin ]", "  show_pos: true",
                                      '  separator: " / "', "  max_length: 60", ""])

    def test_template_without_hints(self):
        self.assertNotIn("spelling_hints", ij.patch_template(TEMPLATE, ["eng"], 0))

    def test_template_changed_upstream(self):
        with self.assertRaises(ValueError):
            ij.patch_template(TEMPLATE.replace("dictionary_lookup_filter", "other_filter"), ["eng"], 10)
        with self.assertRaises(ValueError):
            ij.patch_template(TEMPLATE.replace("translator:", "translators:"), ["eng"], 10)

    def test_schema(self):
        text = ij.patch_schema(SCHEMA)
        self.assertNotIn("\\v", text)
        lines = text.split("\n")
        # emptied comment_format is dropped with its marker, the others stay
        self.assertEqual(lines[lines.index("luna_pinyin:"):lines.index("loengfan:")],
                         ["luna_pinyin:", "  tag: luna_pinyin", "  tips: 〔普通話〕", ""])
        self.assertEqual(lines[lines.index("loengfan:"):lines.index("cangjie:")],
                         ["loengfan:", "  tips: 〔粵語兩分〕", "  comment_format:", "    - xform/~//", ""])
        self.assertIn('    - "xlit|ab|日月|"', lines)
        self.assertIn("    - common:/use_cangjie3?", lines)

    def test_flypy(self):
        lines = ij.patch_flypy(ij.patch_schema(FULL_SCHEMA)).split("\n")
        self.assertEqual(lines[lines.index("schema:"):lines.index("engine:")],
                         ["schema:", "  dependencies:", "    - jyut6ping3_scolar", "    - " + ij.FLYPY, ""])
        # the engine keeps naming the section, only the dependency changes
        self.assertIn("    - script_translator@luna_pinyin", lines)
        self.assertEqual(lines[lines.index("luna_pinyin:"):lines.index("loengfan:")],
                         ["luna_pinyin:", "  tag: luna_pinyin", "  dictionary: luna_pinyin",
                          "  prism: " + ij.FLYPY, '  prefix: "`p"', "  tips: 〔普通話·小鶴〕", ""])
        self.assertEqual(lines[lines.index("loengfan:"):],
                         ["loengfan:", "  dictionary: loengfan", "  tips: 〔粵語兩分〕", "  preedit_format:",
                          "    - xform/a/b/", ""])
        for anchor in ("    - luna_pinyin\n", "  dictionary: luna_pinyin\n"):
            with self.assertRaises(ValueError):
                ij.patch_flypy(FULL_SCHEMA.replace(anchor, ""))

    def test_dict(self):
        lines = ij.patch_dict(DICT).split("\n")
        self.assertEqual(lines[4:7], ["use_preset_vocabulary: true", "vocabulary: typeduck_essay", "..."])
        self.assertEqual(ij.patch_dict(ij.patch_dict(DICT)), ij.patch_dict(DICT))
        with self.assertRaises(ValueError):
            ij.patch_dict("name: x\n")

    def test_index(self):
        index, count = ij.build_index(SCOLAR.split("\n"))
        self.assertEqual(count, 3)
        us, rs = ij.US, ij.RS
        self.assertEqual(index, [
            "行\t" + us.join(["hong2", "n", "bank", "", "", "", ""]) + rs
            + us.join(["hong4", "mw", "row, profession", "व्यवसाय", "شعبہ", "", ""]),
            "飽肚\t" + us.join(["baau2tou5", "adj", "filling, satiated", "", "", "", "seutuh"]),
        ])


    def test_readings(self):
        index, count = ij.build_readings([
            "# header comment", "---", "name: jyut6ping3", "...", "",
            "行\thaang1\t0.0%", "行\thaang4\t30.0%", "行\thang4\t50.0%", "行\thong4\t17.0%",
            "尼\tnei4\t0.0%", "尼\tni1\t0.0%",          # no weight at all: all kept, file order
            "香港\thoeng1 gong2\t100.0%", "香港\thoeng1 gong2\t5.0%",
            "杭\thong4", "# comment", "no tab here", "\tx\t1%",
        ])
        us = ij.US
        self.assertEqual(count, 4)
        self.assertEqual(index, ["行\t" + us.join(["hang4", "haang4", "hong4"]), "尼\t" + us.join(["nei4", "ni1"]),
                                 "香港\thoeng1 gong2", "杭\thong4"])


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "source"
        (self.source / "opencc").mkdir(parents=True)
        for name in ij.VERBATIM:
            (self.source / name).write_text("# upstream " + name + "\n", encoding="utf-8")
        files = {
            "template.yaml": TEMPLATE, "jyut6ping3.schema.yaml": SCHEMA, "jyut6ping3.dict.yaml": DICT,
            "jyut6ping3_scolar.dict.yaml": SCOLAR, "essay.txt": "香港\t100\n", "opencc/hk2s.json": "{}\n",
            # must never reach the user directory
            "luna_pinyin.dict.yaml": "x\n", "cangjie5.schema.yaml": "x\n", "stroke.dict.yaml": "x\n",
            "default.yaml": "x\n", "default.custom.yaml": "x\n", "jyut6ping3_mobile.schema.yaml": "x\n",
        }
        for name, text in files.items():
            (self.source / name).write_text(text, encoding="utf-8")
        self.user = root / "user"
        self.user.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, extra=()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ij.main(["--dir", str(self.user), "--source", str(self.source), *extra])
        return out.getvalue()

    def read(self, name):
        return (self.user / name).read_text(encoding="utf-8")

    def test_fresh_install_and_rerun(self):
        out = self.run_main()
        installed = sorted(p.relative_to(self.user).as_posix() for p in self.user.rglob("*") if p.is_file())
        self.assertEqual(installed, sorted(ij.VERBATIM + [
            "template.yaml", "jyut6ping3.schema.yaml", "jyut6ping3.dict.yaml", "typeduck_essay.txt",
            "opencc/hk2s.json", "lua/typeduck_gloss.lua", "lua/typeduck_gloss.txt",
            "lua/typeduck_readings.txt"]))
        for name in ("template.yaml", "jyut6ping3.schema.yaml", "jyut6ping3.dict.yaml"):
            self.assertTrue(self.read(name).startswith(ij.MARKER + " from " + str(self.source) + "\n"))
        self.assertIn("vocabulary: typeduck_essay\n", self.read("jyut6ping3.dict.yaml"))
        self.assertEqual(self.read("typeduck_essay.txt"), "香港\t100\n")
        # not splitlines(): that also splits at the record separator \x1e
        self.assertEqual(len(self.read("lua/typeduck_gloss.txt").rstrip("\n").split("\n")), 2)
        self.assertEqual(self.read("lua/typeduck_readings.txt"), "香\thoeng1\n")
        self.assertIn("- schema: jyut6ping3", out)
        self.assertNotIn("Kept", out)
        before = {name: self.read(name) for name in installed}
        self.run_main()
        self.assertEqual({name: self.read(name) for name in installed}, before)

    def test_foreign_files_are_kept(self):
        (self.user / "template.yaml").write_text("# mine\n", encoding="utf-8")
        (self.user / "quick5.dict.yaml").write_text("# mine\n", encoding="utf-8")
        (self.user / "default.custom.yaml").write_text("patch:\n  schema_list:\n    - schema: jyut6ping3\n",
                                                       encoding="utf-8")
        out = self.run_main()
        self.assertEqual(self.read("template.yaml"), "# mine\n")
        self.assertEqual(self.read("quick5.dict.yaml"), "# mine\n")
        self.assertIn("  quick5.dict.yaml\n  template.yaml\n", out)
        self.assertNotIn("is not enabled", out)
        out = self.run_main(["--force"])
        self.assertTrue(self.read("template.yaml").startswith(ij.MARKER))
        self.assertEqual(self.read("quick5.dict.yaml"), "# upstream quick5.dict.yaml\n")
        self.assertNotIn("Kept", out)

    def test_generated_files_follow_upstream(self):
        self.run_main(["--languages", "eng,urd", "--spelling-hints", "0"])
        self.assertIn("  languages: [ eng, urd ]\n", self.read("template.yaml"))
        self.assertNotIn("spelling_hints", self.read("template.yaml"))
        (self.source / "jyut6ping3.schema.yaml").write_text(SCHEMA + "added: 1\n", encoding="utf-8")
        self.run_main()
        self.assertIn("added: 1\n", self.read("jyut6ping3.schema.yaml"))
        self.assertIn("  spelling_hints: 10\n", self.read("template.yaml"))

    def test_flypy_install(self):
        (self.source / "jyut6ping3.schema.yaml").write_text(FULL_SCHEMA, encoding="utf-8")
        self.run_main(["--flypy"])
        helper = self.read(ij.FLYPY + ".schema.yaml")
        self.assertTrue(helper.startswith(ij.MARKER))
        self.assertIn("  schema_id: %s\n" % ij.FLYPY, helper)
        self.assertIn("  dictionary: luna_pinyin\n  prism: %s\n" % ij.FLYPY, helper)
        self.assertIn("  prism: %s\n" % ij.FLYPY, self.read("jyut6ping3.schema.yaml"))
        # without the option the lookup goes back to full Pinyin
        self.run_main()
        self.assertNotIn(ij.FLYPY, self.read("jyut6ping3.schema.yaml"))
        # an upstream schema the option cannot be applied to is an error
        (self.source / "jyut6ping3.schema.yaml").write_text(SCHEMA, encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_main(["--flypy"])

    def test_bad_arguments(self):
        for extra in (["--languages", "deu"], ["--languages", ""], ["--source", str(self.user)]):
            with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
                ij.main(["--dir", str(self.user), "--source", str(self.source), *extra])
        (self.source / "template.yaml").write_text("no filter here\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_main()

    def test_generated_source_rejected(self):
        self.run_main()
        for name in ij.VERBATIM + ["essay.txt"]:
            (self.user / name).write_text("x\n", encoding="utf-8")
        (self.user / "opencc").mkdir(exist_ok=True)
        with self.assertRaises(SystemExit):
            ij.main(["--dir", str(self.user), "--source", str(self.user)])


if __name__ == "__main__":
    unittest.main()
