"""What a release may write over what is already published."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_publish as guard  # noqa: E402

SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"
BASE = {"$schema": SPEC, "$id": "Time.schema.json", "type": "object",
        "properties": {"value": {"type": "number"}}}


def put(root: Path, module: str, version: str, schema=None, lock=None) -> None:
    directory = root / module / version
    directory.mkdir(parents=True, exist_ok=True)
    if schema is not None:
        (directory / "Time.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    if lock is not None:
        (directory / "oold.lock.json").write_text(json.dumps(lock), encoding="utf-8")


def grown(schema):
    out = json.loads(json.dumps(schema))
    out["properties"]["unit"] = {"type": "string"}
    return out


def broken(schema):
    out = json.loads(json.dumps(schema))
    del out["properties"]["value"]
    return out


class Lines(unittest.TestCase):
    def check(self, line, published, staged):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            put(old, "q", line, published)
            put(new, "q", line, staged)
            return guard.line_problems("q", line, old / "q" / line, new / "q" / line)

    def test_a_line_below_one_takes_patches(self):
        patched = dict(BASE, description="clearer")
        self.assertEqual(self.check("0.2", BASE, patched), [])

    def test_a_line_below_one_refuses_additions(self):
        self.assertEqual(len(self.check("0.2", BASE, grown(BASE))), 1)

    def test_a_major_line_takes_additions(self):
        self.assertEqual(self.check("1", BASE, grown(BASE)), [])

    def test_every_line_refuses_breaks(self):
        for line in ("0.2", "1"):
            self.assertEqual(len(self.check(line, BASE, broken(BASE))), 1)


class Locks(unittest.TestCase):
    LOCK = {"module": "m", "version": "0.2.0", "requires": {"q": "0.2.0"}}

    def run_check(self, published_lock, staged_lock, published=(), staged=()):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            put(old, "m", "0.2.0", BASE, published_lock)
            put(new, "m", "0.2.0", BASE, staged_lock)
            for module, version in published:
                put(old, module, version, BASE)
            for module, version in staged:
                put(new, module, version, BASE)
            return guard.lock_problems("m", "0.2.0", old, new)

    def test_same_lock_republishes(self):
        self.assertEqual(self.run_check(self.LOCK, self.LOCK, published=[("q", "0.2.0")]), [])

    def test_a_published_lock_is_never_rewritten(self):
        other = dict(self.LOCK, requires={"q": "0.2.1"})
        problems = self.run_check(self.LOCK, other, published=[("q", "0.2.0"), ("q", "0.2.1")])
        self.assertEqual(len(problems), 1)

    def test_a_lock_may_be_added_to_a_release_that_has_none(self):
        self.assertEqual(self.run_check(None, self.LOCK, published=[("q", "0.2.0")]), [])

    def test_a_required_version_must_exist_somewhere(self):
        self.assertEqual(len(self.run_check(None, self.LOCK)), 1)

    def test_a_required_version_staged_in_the_same_release_counts(self):
        self.assertEqual(self.run_check(None, self.LOCK, staged=[("q", "0.2.0")]), [])


class Packages(unittest.TestCase):
    def zip_of(self, root: Path, name: str, content: bytes) -> None:
        import zipfile
        (root / "packages").mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root / "packages" / name, "w") as z:
            z.writestr("m/0.2.0/A.schema.json", content)

    def run_check(self, published, staged):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            old.mkdir()
            new.mkdir()
            if published is not None:
                self.zip_of(old, "m-0.2.0.zip", published)
            if staged is not None:
                self.zip_of(new, "m-0.2.0.zip", staged)
            return guard.package_problems("m", "0.2.0", old, new)

    def test_same_documents_republish(self):
        self.assertEqual(self.run_check(b"{}", b"{}"), [])

    def test_a_published_package_is_never_rewritten(self):
        self.assertEqual(len(self.run_check(b"{}", b'{"a": 1}')), 1)

    def test_a_new_package_is_fine(self):
        self.assertEqual(self.run_check(None, b"{}"), [])


if __name__ == "__main__":
    unittest.main()
