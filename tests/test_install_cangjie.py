"""Unit tests for install-cangjie.py.  Run:  python3 tests/test_install_cangjie.py"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install_cangjie", REPO / "install-cangjie.py")
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)

HEADER = """# comment
---
name: "cangjie5"
sort: by_weight
columns:
  - text
  - code
  - stem
...
"""
BODY = """
欠\tno
久\tno
飞\tno
久\txno
晕\tabkq
晖\tabkq
晖\txabkq
明\tab
冐\tab
冐\txab
工\tmlm\tm
土\tmlm
土\txmlm
日\ta
曰\ta
女工\tno
"""
ESSAY = {"久": 8974, "欠": 3587, "明": 10778, "冐": 392, "工": 10, "土": 500, "日": 9, "曰": 99, "女工": 99999}


class ReweightTest(unittest.TestCase):
    def setUp(self):
        self.text, self.changes = ic.reweight(HEADER + BODY, ESSAY)
        self.lines = self.text.split("\n")

    def test_primary_outranks_frequent_secondary(self):
        self.assertIn("欠\tno\t\t8975", self.lines)
        self.assertIn(("no", "欠", 8975, "久"), self.changes)

    def test_stem_column_is_kept(self):
        self.assertIn("工\tmlm\tm\t501", self.lines)

    def test_only_listed_changes(self):
        self.assertEqual(sorted(c[0] for c in self.changes), ["mlm", "no"])
        untouched = ["久\tno", "飞\tno", "久\txno", "晕\tabkq", "明\tab", "日\ta", "曰\ta", "女工\tno"]
        for line in untouched:
            self.assertIn(line, self.lines)

    def test_weight_column_added_once(self):
        self.assertEqual(self.lines[5:9], ["  - text", "  - code", "  - stem", "  - weight"])
        again, changes = ic.reweight(self.text, ESSAY)
        self.assertEqual(again, self.text)
        self.assertEqual(changes, [])

    def test_no_change_leaves_text_identical(self):
        text = HEADER + "\n明\tab\n冐\tab\n冐\txab\n"
        self.assertEqual(ic.reweight(text, ESSAY), (text, []))

    def test_default_columns_have_weight(self):
        text = "---\nname: x\n...\n欠\tno\n久\tno\t50\n久\txno\n"
        fixed, changes = ic.reweight(text, {})
        self.assertIn("欠\tno\t51", fixed.split("\n"))
        self.assertEqual(changes, [("no", "欠", 51, "久")])

    def test_not_a_dictionary(self):
        with self.assertRaises(ValueError):
            ic.reweight("name: x\n", {})


class InstallTest(unittest.TestCase):
    def run_main(self, user, extra=()):
        with contextlib.redirect_stdout(io.StringIO()):
            ic.main(["--dir", str(user), "--source", str(self.source), "--essay", str(self.essay), *extra])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "shared.dict.yaml"
        self.source.write_text(HEADER + BODY, encoding="utf-8")
        self.essay = root / "essay.txt"
        self.essay.write_text("久\t8974\n欠\t3587\nbad line\n", encoding="utf-8")
        self.user = root / "user"
        self.user.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_install_and_rerun(self):
        self.run_main(self.user)
        custom = self.user / "cangjie5.custom.yaml"
        expected = ic.MARKER + "\npatch:\n  " + ic.SEGMENTOR_LINE + "\n"
        self.assertEqual(custom.read_text(encoding="utf-8"), expected)
        self.assertTrue((self.user / "lua" / "delimited_code.lua").is_file())
        installed = (self.user / "cangjie5.dict.yaml").read_text(encoding="utf-8")
        self.assertTrue(installed.startswith(ic.DICT_MARKER))
        self.assertIn("欠\tno\t\t8975\n", installed)
        self.run_main(self.user)
        self.assertEqual(custom.read_text(encoding="utf-8"), expected)
        self.assertEqual((self.user / "cangjie5.dict.yaml").read_text(encoding="utf-8"), installed)

    def test_appends_to_generated_custom_yaml(self):
        custom = self.user / "cangjie5.custom.yaml"
        custom.write_text(ic.MARKER + "\npatch:\n  engine/filters/@next: lua_filter@*german_gloss\n", encoding="utf-8")
        self.run_main(self.user, ["--skip-dict"])
        self.assertEqual(custom.read_text(encoding="utf-8").split("\n")[-3:],
                         ["  engine/filters/@next: lua_filter@*german_gloss", "  " + ic.SEGMENTOR_LINE, ""])
        self.assertFalse((self.user / "cangjie5.dict.yaml").exists())

    def test_foreign_files_are_kept(self):
        custom = self.user / "cangjie5.custom.yaml"
        custom.write_text("patch:\n  foo: 1\n", encoding="utf-8")
        own = self.user / "cangjie5.dict.yaml"
        own.write_text("# mine\n", encoding="utf-8")
        self.run_main(self.user)
        self.assertEqual(custom.read_text(encoding="utf-8"), "patch:\n  foo: 1\n")
        self.assertEqual(own.read_text(encoding="utf-8"), "# mine\n")
        self.run_main(self.user, ["--force", "--skip-segmentor"])
        self.assertTrue(own.read_text(encoding="utf-8").startswith(ic.DICT_MARKER))

    def test_generated_source_rejected(self):
        self.run_main(self.user)
        with self.assertRaises(SystemExit):
            ic.main(["--dir", str(self.user), "--source", str(self.user / "cangjie5.dict.yaml")])


if __name__ == "__main__":
    unittest.main()
