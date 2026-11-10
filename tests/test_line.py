"""The compatibility line of a version, one rule shared by every script."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import _shared  # noqa: E402
import macros  # noqa: E402

CASES = {
    "0.0.1": "0.0",
    "0.2.0": "0.2",
    "0.3.7": "0.3",
    "1.0.0": "1",
    "1.4.2": "1",
    "12.0.1": "12",
}


class LineRule(unittest.TestCase):
    def test_line_below_one_is_major_minor(self):
        for version in ("0.0.1", "0.2.0", "0.3.7"):
            self.assertEqual(_shared.line(version), CASES[version])

    def test_line_from_one_is_major(self):
        for version in ("1.0.0", "1.4.2", "12.0.1"):
            self.assertEqual(_shared.line(version), CASES[version])

    def test_only_exact_versions_have_a_line(self):
        for bad in ("1", "1.2", "1.2.3-rc.1", "v1.2.3", ""):
            with self.assertRaises(ValueError):
                _shared.line(bad)

    def test_macros_apply_the_same_rule(self):
        for version, expected in CASES.items():
            self.assertEqual(macros.line(version), expected)


class LatestPerLine(unittest.TestCase):
    ENTRIES = [{"module": "0.1.0", "docs": "a"}, {"module": "0.2.0", "docs": "b"},
               {"module": "0.2.1", "docs": "c"}, {"module": "1.0.0", "docs": "d"},
               {"module": "1.1.0", "docs": "e"}]

    def test_one_entry_per_line_keeping_the_newest(self):
        want = [{"module": "0.1.0", "docs": "a"}, {"module": "0.2.1", "docs": "c"},
                {"module": "1.1.0", "docs": "e"}]
        self.assertEqual(_shared.latest_per_line(self.ENTRIES), want)
        self.assertEqual(macros.latest_per_line(self.ENTRIES), want)

    def test_empty(self):
        self.assertEqual(_shared.latest_per_line([]), [])


if __name__ == "__main__":
    unittest.main()
