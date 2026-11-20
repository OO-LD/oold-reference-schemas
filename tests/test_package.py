"""The offline package: a zip of unmodified documents laid out like the host."""

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import package
from config import CONFIG

BASE = CONFIG.namespace
SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"


PREFIX = BASE.removeprefix("https://")


def ident(module: str) -> str:
    return f"{BASE}/{module}"


def doc(refs=()):
    return {"$schema": SPEC, "properties": {f"p{i}": {"$ref": r} for i, r in enumerate(refs)}}


class Source:
    def __init__(self, modules):
        self.modules = modules

    """Test data is keyed by module name, the code under test by identity."""

    def versions(self, identity):
        return list(self.modules.get(identity.rsplit("/", 1)[-1], {}))

    def schemas(self, identity, version):
        return self.modules[identity.rsplit("/", 1)[-1]][version]

    def files(self, identity, version):
        return {name: json.dumps(schema, indent=2).encode() + b"\n"
                for name, schema in self.schemas(identity, version).items()}


def source():
    return Source({
        "quantities": {"0.2.0": {"Time.schema.json": doc()},
                       "0.3.0": {"Time.schema.json": doc()}},
        "unrelated": {"1.0.0": {"X.schema.json": doc()}},
        "materials": {"0.2.0": {
            "Material.schema.json": doc([f"{BASE}/quantities/0.2/Time.schema.json"])}},
    })


def members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


class Layout(unittest.TestCase):
    def test_holds_the_module_and_its_closure_under_exact_and_line_paths(self):
        names = set(members(package.build(ident("materials"), "0.2.0", source())))
        self.assertEqual(names, {
            f"{PREFIX}/materials/0.2.0/Material.schema.json",
            f"{PREFIX}/materials/0.2/Material.schema.json",
            f"{PREFIX}/materials/0.2.0/oold.lock.json", f"{PREFIX}/materials/0.2/oold.lock.json",
            f"{PREFIX}/quantities/0.2.0/Time.schema.json",
            f"{PREFIX}/quantities/0.2/Time.schema.json",
        })

    def test_a_major_line_uses_the_major_directory(self):
        src = Source({"m": {"1.4.2": {"A.schema.json": doc()}}})
        names = set(members(package.build(ident("m"), "1.4.2", src)))
        self.assertIn(f"{PREFIX}/m/1/A.schema.json", names)
        self.assertIn(f"{PREFIX}/m/1.4.2/A.schema.json", names)

    def test_documents_are_the_source_bytes(self):
        src = source()
        built = members(package.build(ident("materials"), "0.2.0", src))
        want = src.files(ident("quantities"), "0.2.0")["Time.schema.json"]
        self.assertEqual(built[f"{PREFIX}/quantities/0.2/Time.schema.json"], want)
        self.assertEqual(built[f"{PREFIX}/quantities/0.2.0/Time.schema.json"], want)

    def test_carries_the_lock_of_the_module(self):
        lock = json.loads(members(package.build(ident("materials"), "0.2.0", source()))
                          [f"{PREFIX}/materials/0.2.0/oold.lock.json"])
        self.assertEqual(lock["requires"], {ident("quantities"): {"version": "0.2.0"}})

    def test_a_module_without_dependencies_stands_alone(self):
        names = set(members(package.build(ident("quantities"), "0.2.0", source())))
        self.assertTrue(all(n.startswith(f"{PREFIX}/quantities/") for n in names))


class Determinism(unittest.TestCase):
    def test_same_input_same_bytes(self):
        self.assertEqual(package.build(ident("materials"), "0.2.0", source()),
                         package.build(ident("materials"), "0.2.0", source()))

    def test_same_documents_compare_equal_whatever_the_compression(self):
        a = package.build(ident("materials"), "0.2.0", source())
        self.assertTrue(package.same_documents(a, a))
        other = package.build(ident("materials"), "0.2.0", Source({
            **source().modules,
            "quantities": {"0.2.0": {"Time.schema.json":
                                     doc([f"{BASE}/unrelated/1/X.schema.json"])}}}))
        self.assertFalse(package.same_documents(a, other))


if __name__ == "__main__":
    unittest.main()
