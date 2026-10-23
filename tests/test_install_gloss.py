"""Unit tests for install-gloss.py.  Run:  python3 tests/test_install_gloss.py"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install_gloss", REPO / "install-gloss.py")
ig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ig)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.user = root / "user"
        self.user.mkdir()
        self.shared = root / "shared"
        self.shared.mkdir()
        self.saved_shared_dirs = ig.shared_dirs
        ig.shared_dirs = lambda: [self.shared]

    def tearDown(self):
        ig.shared_dirs = self.saved_shared_dirs
        self.tmp.cleanup()

    def run_script(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ig.main(["--dir", str(self.user)] + list(argv))
        return out.getvalue()

    def read(self, name):
        return (self.user / name).read_text(encoding="utf-8")

    def test_installs_files(self):
        self.run_script("--schema", "cangjie5")
        self.assertTrue((self.user / "lua" / "german_gloss.lua").is_file())
        self.assertIn("die Schule", self.read("german_gloss/zh_de.tsv"))
        self.assertIn("l'école", self.read("french_gloss/zh_fr.tsv"))
        self.assertIn("学校(がっこう)", self.read("japanese_gloss/zh_ja.tsv"))

    def test_creates_patch(self):
        self.run_script("--schema", "cangjie5,luna_pinyin_simp")
        for schema in ("cangjie5", "luna_pinyin_simp"):
            text = self.read(schema + ".custom.yaml")
            self.assertTrue(text.startswith(ig.MARKER + "\npatch:\n"))
            self.assertIn("  switches/@next: {options: [gloss_de, gloss_fr, gloss_ja, gloss_none], "
                          "states: [德译, 法译, 日译, 无译]}\n", text)
            self.assertIn("  engine/filters/+: [lua_filter@*german_gloss, "
                          "lua_filter@*german_gloss@french_gloss, "
                          "lua_filter@*german_gloss@japanese_gloss]\n", text)
            self.assertIn("  german_gloss/option: gloss_de\n", text)
            self.assertIn("  french_gloss/base_dictionary: french_gloss/cfdict.tsv\n", text)
            self.assertIn("  japanese_gloss/base_dictionary: japanese_gloss/jawiktionary.tsv\n", text)
            self.assertNotIn("german_gloss/dictionary", text)
        self.assertIn("switcher/save_options/+: [gloss_de, gloss_fr, gloss_ja, gloss_none]",
                      self.read("default.custom.yaml"))

    def test_single_language(self):
        self.run_script("--language", "fr", "--schema", "cangjie5")
        text = self.read("cangjie5.custom.yaml")
        self.assertIn("{options: [gloss_fr, gloss_none], states: [法译, 无译]}", text)
        self.assertIn("engine/filters/+: [lua_filter@*german_gloss@french_gloss]", text)
        self.assertFalse((self.user / "german_gloss").exists())

    def test_language_order_sets_default(self):
        self.run_script("--language", "fr,de", "--schema", "cangjie5")
        self.assertIn("options: [gloss_fr, gloss_de, gloss_none]", self.read("cangjie5.custom.yaml"))

    def test_unknown_language(self):
        with self.assertRaises(SystemExit):
            self.run_script("--language", "es", "--schema", "cangjie5")

    def test_updates_generated_file_from_older_version(self):
        (self.user / "cangjie5.custom.yaml").write_text(
            ig.MARKER + "\npatch:\n  engine/filters/@next: lua_filter@*german_gloss\n"
            "  engine/segmentors/@before 2: lua_segmentor@*delimited_code\n", encoding="utf-8")
        self.run_script("--schema", "cangjie5")
        text = self.read("cangjie5.custom.yaml")
        self.assertNotIn("@next: lua_filter", text)
        self.assertIn("delimited_code", text)
        self.assertEqual(text.count("lua_filter@*german_gloss,"), 1)
        before = text
        self.assertIn("unchanged", self.run_script("--schema", "cangjie5"))
        self.assertEqual(self.read("cangjie5.custom.yaml"), before)

    def test_adds_new_language_to_generated_file(self):
        self.run_script("--language", "de,fr", "--schema", "cangjie5")
        self.run_script("--schema", "cangjie5")
        text = self.read("cangjie5.custom.yaml")
        self.assertIn("options: [gloss_de, gloss_fr, gloss_ja, gloss_none]", text)
        self.assertEqual(text.count("switches/@next"), 1)
        self.assertEqual(text.count("engine/filters/+"), 1)
        self.assertEqual(text.count("french_gloss/option"), 1)
        self.assertIn("japanese_gloss/option: gloss_ja", text)
        self.assertIn("unchanged", self.run_script("--schema", "cangjie5"))

    def test_foreign_file_with_older_switch(self):
        own = ("patch:\n  switches/@next: {options: [gloss_de, gloss_fr, gloss_none], "
               "states: [德译, 法译, 无译]}\n  french_gloss/option: gloss_fr\n")
        (self.user / "cangjie5.custom.yaml").write_text(own, encoding="utf-8")
        out = self.run_script("--schema", "cangjie5")
        self.assertEqual(self.read("cangjie5.custom.yaml"), own)
        self.assertIn("japanese_gloss/option: gloss_ja", out)
        stale = out.split("remove its lines\n")[1]
        self.assertTrue(stale.startswith("      switches/@next: {options: [gloss_de, gloss_fr, gloss_none]"))
        self.assertNotIn("french_gloss/option", stale)  # still wanted, so not stale

    def test_foreign_file_kept(self):
        own = "patch:\n  engine/filters/@next: lua_filter@*german_gloss\n"
        (self.user / "cangjie5.custom.yaml").write_text(own, encoding="utf-8")
        out = self.run_script("--schema", "cangjie5")
        self.assertEqual(self.read("cangjie5.custom.yaml"), own)
        self.assertIn("NOT modified", out)
        self.assertIn("switches/@next", out)
        self.assertIn("remove its line", out)

    def test_modified_user_dictionary_kept(self):
        (self.user / "french_gloss").mkdir()
        (self.user / "french_gloss" / "zh_fr.tsv").write_text("学校\tmon école\n", encoding="utf-8")
        self.run_script("--schema", "cangjie5")
        self.assertEqual(self.read("french_gloss/zh_fr.tsv"), "学校\tmon école\n")
        self.assertIn("l'école", self.read("french_gloss/zh_fr.tsv.new"))
        self.run_script("--schema", "cangjie5", "--force")
        self.assertIn("l'école", self.read("french_gloss/zh_fr.tsv"))

    def test_lists_schemas_without_schema(self):
        (self.shared / "cangjie5.schema.yaml").write_text(
            "schema:\n  schema_id: cangjie5\n  name: 倉頡五代\n", encoding="utf-8")
        (self.user / "luna_pinyin_simp.schema.yaml").write_text(
            "schema:\n  schema_id: luna_pinyin_simp\n  name: \"朙月拼音·简化字\"\n", encoding="utf-8")
        (self.user / "default.custom.yaml").write_text(
            "patch:\n  schema_list:\n    - {schema: cangjie5}\n    # comment\n"
            "    - schema: td_pinyin_flypy\n  key_binder/bindings/+: []\n", encoding="utf-8")
        out = self.run_script()
        lines = {line.split()[0]: line for line in out.splitlines() if line.startswith("      ")}
        self.assertIn("[installed][enabled]", lines["cangjie5"])
        self.assertIn("[installed]", lines["luna_pinyin_simp"])
        self.assertNotIn("[enabled]", lines["luna_pinyin_simp"])
        self.assertIn("朙月拼音·简化字", lines["luna_pinyin_simp"])
        self.assertNotIn("[", lines["wubi86"])
        self.assertIn("Other enabled schemas: td_pinyin_flypy", out)
        self.assertFalse((self.user / "cangjie5.custom.yaml").exists())  # nothing enabled
        self.assertNotIn("save_options", self.read("default.custom.yaml"))

    def test_enabled_from_shared_default(self):
        (self.shared / "default.yaml").write_text(
            "schema_list:\n  - schema: luna_pinyin\n  - schema: stroke\n\nswitcher:\n", encoding="utf-8")
        self.assertEqual(ig.enabled_schemas(self.user, [self.shared]), ["luna_pinyin", "stroke"])


if __name__ == "__main__":
    unittest.main()
