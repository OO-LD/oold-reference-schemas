"""The offline package: a zip of unmodified documents laid out like the host."""

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import package  # noqa: E402

BASE = "https://w3id.org/oo-ld/schemas"
SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"


def doc(refs=()):
    return {"$schema": SPEC, "properties": {f"p{i}": {"$ref": r} for i, r in enumerate(refs)}}


class Source:
    def __init__(self, modules):
        self.modules = modules

    def versions(self, module):
        return list(self.modules.get(module, {}))

    def schemas(self, module, version):
        return self.modules[module][version]

    def files(self, module, version):
        return {name: json.dumps(schema, indent=2).encode() + b"\n"
                for name, schema in self.modules[module][version].items()}


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
        names = set(members(package.build("materials", "0.2.0", source())))
        self.assertEqual(names, {
            "materials/0.2.0/Material.schema.json", "materials/0.2/Material.schema.json",
            "materials/0.2.0/oold.lock.json", "materials/0.2/oold.lock.json",
            "quantities/0.2.0/Time.schema.json", "quantities/0.2/Time.schema.json",
        })

    def test_a_major_line_uses_the_major_directory(self):
        src = Source({"m": {"1.4.2": {"A.schema.json": doc()}}})
        names = set(members(package.build("m", "1.4.2", src)))
        self.assertIn("m/1/A.schema.json", names)
        self.assertIn("m/1.4.2/A.schema.json", names)

    def test_documents_are_the_source_bytes(self):
        src = source()
        built = members(package.build("materials", "0.2.0", src))
        want = src.files("quantities", "0.2.0")["Time.schema.json"]
        self.assertEqual(built["quantities/0.2/Time.schema.json"], want)
        self.assertEqual(built["quantities/0.2.0/Time.schema.json"], want)

    def test_carries_the_lock_of_the_module(self):
        lock = json.loads(members(package.build("materials", "0.2.0", source()))
                          ["materials/0.2.0/oold.lock.json"])
        self.assertEqual(lock["requires"], {"quantities": "0.2.0"})

    def test_a_module_without_dependencies_stands_alone(self):
        names = set(members(package.build("quantities", "0.2.0", source())))
        self.assertEqual({n.split("/")[0] for n in names}, {"quantities"})


class Determinism(unittest.TestCase):
    def test_same_input_same_bytes(self):
        self.assertEqual(package.build("materials", "0.2.0", source()),
                         package.build("materials", "0.2.0", source()))

    def test_same_documents_compare_equal_whatever_the_compression(self):
        a = package.build("materials", "0.2.0", source())
        self.assertTrue(package.same_documents(a, a))
        other = package.build("materials", "0.2.0", Source({
            **source().modules,
            "quantities": {"0.2.0": {"Time.schema.json": doc([f"{BASE}/unrelated/1/X.schema.json"])}}}))
        self.assertFalse(package.same_documents(a, other))


if __name__ == "__main__":
    unittest.main()
