"""The spec edition each schema is pinned to, and what a repin costs."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import level  # noqa: E402
import spec_edition  # noqa: E402


def meta(edition: str) -> str:
    return f"https://oo-ld.org/{edition}/meta/oold-meta-schema.json"


def module(root: Path, name: str, editions: dict[str, str]) -> None:
    directory = root / name
    directory.mkdir()
    for schema, edition in editions.items():
        text = json.dumps({"$schema": meta(edition), "$id": schema}, indent=2)
        (directory / f"{schema}.schema.json").write_text(text + "\n", encoding="utf-8")


class Edition(unittest.TestCase):
    def test_reads_an_exact_edition(self):
        self.assertEqual(spec_edition.edition_of(meta("1.0.1")), "1.0.1")
        self.assertEqual(spec_edition.edition_of(meta("1.0.0-rc.3")), "1.0.0-rc.3")

    def test_floating_or_foreign_pointers_have_no_edition(self):
        for pointer in (meta("latest"), meta("dev"), "Base.schema.json",
                        "https://json-schema.org/draft/2020-12/schema", None):
            self.assertIsNone(spec_edition.edition_of(pointer))


class Check(unittest.TestCase):
    def test_a_consistent_pinned_module_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            module(Path(tmp), "a", {"One": "1.0.1", "Two": "1.0.1"})
            self.assertEqual(spec_edition.problems(Path(tmp)), [])

    def test_latest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            module(Path(tmp), "a", {"One": "latest"})
            self.assertEqual(len(spec_edition.problems(Path(tmp))), 1)

    def test_a_module_may_not_mix_editions(self):
        with tempfile.TemporaryDirectory() as tmp:
            module(Path(tmp), "a", {"One": "1.0.1", "Two": "1.0.0"})
            self.assertEqual(len(spec_edition.problems(Path(tmp))), 1)

    def test_modules_may_differ_from_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            module(Path(tmp), "a", {"One": "1.0.1"})
            module(Path(tmp), "b", {"One": "1.0.0"})
            self.assertEqual(spec_edition.problems(Path(tmp)), [])


class Repin(unittest.TestCase):
    def test_set_rewrites_every_schema_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            module(Path(tmp), "a", {"One": "latest", "Two": "1.0.0"})
            before = (Path(tmp) / "a" / "One.schema.json").read_text(encoding="utf-8")
            spec_edition.set_edition(Path(tmp), "1.0.1")
            after = (Path(tmp) / "a" / "One.schema.json").read_text(encoding="utf-8")
            self.assertEqual(after, before.replace("latest", "1.0.1"))
            self.assertEqual(spec_edition.problems(Path(tmp)), [])


class Level(unittest.TestCase):
    def test_a_repin_is_at_least_minor(self):
        old = {"$schema": meta("1.0.0"), "$id": "A.schema.json"}
        new = {"$schema": meta("1.0.1"), "$id": "A.schema.json"}
        result, reasons = level.compare(old, new)
        self.assertEqual(result, "minor")
        self.assertIn("minor: spec edition changed", reasons)

    def test_the_same_edition_is_unchanged(self):
        schema = {"$schema": meta("1.0.1"), "$id": "A.schema.json"}
        self.assertEqual(level.compare(schema, dict(schema))[0], "none")


if __name__ == "__main__":
    unittest.main()
