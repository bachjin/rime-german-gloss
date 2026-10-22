"""Unit tests for tools/build_cfdict.py.  Run:  python3 tests/test_build_cfdict.py"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_cfdict as bc  # noqa: E402
import build_handedict  # noqa: E402

CFDICT = """\
﻿#############################
# CFDICT, le dictionnaire chinois-francais libre
#############################
學校 学校 [xue2 xiao4] /école/
張 张 [zhang1] /(classificateur pour les objets plats)/(nom de famille)/ouvrir/s'étendre/
王 王 [wang2] /roi/prince/(nom de famille)/
王 王 [wang4] /régner sur/
一絲不掛 一丝不挂 [yi1 si1 bu4 gua4] /(expr. idiom.) tout nu/nu comme un ver/
疼惜\t 疼惜\t [teng2 xi1] /chérir/choyer/
桀驁不馴  桀骜不驯  [jie2 ao4 bu4 xun4] /de caractère violent/
萬年 万年 [Wan4 nian2] /(xian de) Wannian/
ligne invalide
"""


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.entries = bc.build(CFDICT.splitlines())

    def test_both_scripts(self):
        self.assertEqual(self.entries["學校"], ["école"])
        self.assertEqual(self.entries["学校"], ["école"])

    def test_readings_merged(self):
        self.assertEqual(self.entries["王"], ["roi", "prince", "régner sur", "(nom de famille)"])

    def test_measure_words_and_names_last(self):
        self.assertEqual(self.entries["张"],
                         ["ouvrir", "s'étendre", "(classificateur pour les objets plats)",
                          "(nom de famille)"])

    def test_idiom_tag_dropped(self):
        self.assertEqual(self.entries["一丝不挂"], ["tout nu", "nu comme un ver"])

    def test_irregular_spacing(self):
        self.assertEqual(self.entries["疼惜"], ["chérir", "choyer"])
        self.assertEqual(self.entries["桀骜不驯"], ["de caractère violent"])

    def test_comments_and_invalid_lines_skipped(self):
        self.assertFalse(any(k.startswith("#") or k == "ligne" for k in self.entries))

    def test_write_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out", "cfdict.tsv")
            build_handedict.write(self.entries, path, ["Generated", "CC BY-SA 3.0"])
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        self.assertEqual(lines[:3], ["# Generated", "# CC BY-SA 3.0", "# sorted"])
        keys = [line.split("\t")[0] for line in lines[3:]]
        self.assertEqual(keys, sorted(keys, key=lambda k: k.encode("utf-8")))
        self.assertIn("王\troi; prince; régner sur; (nom de famille)", lines)


if __name__ == "__main__":
    unittest.main()
