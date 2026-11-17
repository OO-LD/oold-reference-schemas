"""A rehearsal of releases over time: patches, a new line, 1.0, additions, a break.

Each release is staged the way the build stages it and judged by the same functions the
deploy runs, then written to a published root. The sequence shows what the scheme lets
through and what it refuses, including after a module reaches 1.0.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_publish as guard  # noqa: E402
import level  # noqa: E402
import lock  # noqa: E402
import package  # noqa: E402
from _shared import line  # noqa: E402

BASE = "https://w3id.org/oo-ld/schemas"
SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"


def quantity(version_note: str, props=("value",), spec=SPEC) -> dict:
    return {"$schema": spec, "$id": "Time.schema.json", "description": version_note,
            "properties": {name: {"type": "number"} for name in props}}


def material(cites: str, spec=SPEC) -> dict:
    return {"$schema": spec, "$id": "Material.schema.json",
            "properties": {"time": {"$ref": f"{BASE}/quantities/{cites}/Time.schema.json"}}}


class World:
    """Module versions by number, the release index, and what each release stages."""

    def __init__(self):
        self.documents = {}
        self.released = {}
        self.tree = {}

    def add(self, module, version, schema):
        self.documents.setdefault(module, {})[version] = {schema["$id"]: schema}

    def catalog(self, as_of=None):
        world = self

        class Catalog:
            def versions(self, module):
                return lock.visible(world.released.get(module, []), as_of, world.tree.get(module))

            def schemas(self, module, version):
                return world.documents[module][version]

            def files(self, module, version):
                return {n: json.dumps(d, indent=2).encode() + b"\n"
                        for n, d in world.documents[module][version].items()}

        return Catalog()


def stage(world: World, root: Path) -> None:
    """What the build writes for the versions in the tree, before anything is judged."""
    for module, version in world.tree.items():
        docs = lock.released_docs(world.released, module, version)
        catalog = world.catalog(docs)
        text = lock.render(lock.build(module, version, catalog))
        for directory in (version, line(version)):
            target = root / module / directory
            target.mkdir(parents=True, exist_ok=True)
            for name, data in catalog.files(module, version).items():
                (target / name).write_bytes(data)
            (target / lock.FILE).write_text(text, encoding="utf-8")
        (root / "packages").mkdir(exist_ok=True)
        (root / "packages" / f"{module}-{version}.zip").write_bytes(
            package.build(module, version, catalog))


def publish(world: World, docs: str, published: Path) -> list[str]:
    """One release: stage, judge, and write only if nothing is refused."""
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp)
        stage(world, staged)
        problems = []
        for module, version in world.tree.items():
            problems += guard.module_problems(module, version, line(version), published, staged)
        if problems:
            return problems
        for source in staged.rglob("*"):
            if source.is_file():
                target = published / source.relative_to(staged)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not (target.exists() and "packages" in target.parts):
                    target.write_bytes(source.read_bytes())
    for module, version in world.tree.items():
        entries = world.released.setdefault(module, [])
        if not any(e["module"] == version for e in entries):
            entries.append({"module": version, "docs": docs})
    return []


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.published = Path(self.tmp.name)
        self.world = World()

    def tearDown(self):
        self.tmp.cleanup()

    def release(self, docs, quantities=None, materials=None):
        for module, version, schema in (("quantities", *(quantities or (None, None))),
                                        ("materials", *(materials or (None, None)))):
            if version:
                self.world.add(module, version, schema)
                self.world.tree[module] = version
        return publish(self.world, docs, self.published)

    def lock_of(self, module, directory):
        return json.loads((self.published / module / directory / lock.FILE).read_text())

    def test_the_sequence(self):
        # 1. first release: materials cites the 0.2 line of quantities
        self.assertEqual(self.release("2026.01.01", ("0.2.0", quantity("first")),
                                      ("0.1.0", material("0.2"))), [])
        self.assertEqual(self.lock_of("materials", "0.1.0")["requires"], {"quantities": "0.2.0"})

        # 2. a patch moves the line and leaves the released materials lock frozen
        self.assertEqual(self.release("2026.02.01", ("0.2.1", quantity("clearer"))), [])
        self.assertEqual(self.lock_of("quantities", "0.2")["version"], "0.2.1")
        self.assertEqual(self.lock_of("materials", "0.1.0")["requires"], {"quantities": "0.2.0"})

        # 3. a patch of materials picks the newer pin up
        self.assertEqual(self.release("2026.03.01", None, ("0.1.1", material("0.2"))), [])
        self.assertEqual(self.lock_of("materials", "0.1.1")["requires"], {"quantities": "0.2.1"})

        # 4. an addition below 1.0 may not ride on the 0.2 line
        self.world.add("quantities", "0.2.2", quantity("sneaky", ("value", "unit")))
        self.world.tree["quantities"] = "0.2.2"
        refused = publish(self.world, "2026.03.15", self.published)
        self.assertEqual(len(refused), 1)
        self.assertIn("0.2 carries changes it does not allow", refused[0])
        del self.world.documents["quantities"]["0.2.2"]
        self.world.tree["quantities"] = "0.2.1"

        # 5. the same addition under its own line is fine
        self.assertEqual(self.release("2026.04.01", ("0.3.0", quantity("more", ("value", "unit")))),
                         [])

        # 6. promotion to 1.0: the dependent cites the major line from now on
        self.assertEqual(self.release("2026.05.01", ("1.0.0", quantity("stable", ("value", "unit"))),
                                      ("0.2.0", material("1"))), [])
        self.assertTrue((self.published / "quantities" / "1").is_dir())
        self.assertFalse((self.published / "quantities" / "1.0").exists())
        self.assertEqual(self.lock_of("materials", "0.2.0")["requires"], {"quantities": "1.0.0"})

        # 7. an addition reaches everyone on the major line
        self.assertEqual(self.release("2026.06.01",
                                      ("1.1.0", quantity("grown", ("value", "unit", "scale")))), [])
        self.assertEqual(self.lock_of("quantities", "1")["version"], "1.1.0")
        self.assertEqual(self.lock_of("materials", "0.2.0")["requires"], {"quantities": "1.0.0"})

        # 8. a break may not ride on the major line, whatever it is called
        self.world.add("quantities", "1.2.0", quantity("broken", ("scale",)))
        self.world.tree["quantities"] = "1.2.0"
        refused = publish(self.world, "2026.07.01", self.published)
        self.assertTrue(any("1 carries changes it does not allow" in r for r in refused))
        del self.world.documents["quantities"]["1.2.0"]

        # 9. a break gets a new line and the old one keeps its bytes
        before = (self.published / "quantities" / "1" / "Time.schema.json").read_bytes()
        self.assertEqual(self.release("2026.08.01", ("2.0.0", quantity("v2", ("scale",)))), [])
        self.assertEqual((self.published / "quantities" / "1" / "Time.schema.json").read_bytes(),
                         before)
        self.assertTrue((self.published / "quantities" / "2").is_dir())

    def test_an_exact_release_cannot_change(self):
        self.release("2026.01.01", ("0.2.0", quantity("first")))
        self.world.documents["quantities"]["0.2.0"] = {"Time.schema.json": quantity("edited")}
        refused = publish(self.world, "2026.01.02", self.published)
        self.assertTrue(any("already published" in r for r in refused))


class Promotion(unittest.TestCase):
    def test_levels_around_one_point_zero(self):
        self.assertEqual(level.raise_to("0.9.3", "major"), "0.10.0")
        self.assertEqual(level.raise_to("0.9.3", "minor"), "0.10.0")
        self.assertEqual(level.raise_to("1.0.0", "minor"), "1.1.0")
        self.assertEqual(level.raise_to("1.4.2", "major"), "2.0.0")
        self.assertEqual(level.raise_to("1.4.2", "patch"), "1.4.3")


class Backfill(unittest.TestCase):
    def test_adds_a_lock_to_old_releases_once_and_never_rewrites(self):
        unpinned = "https://oo-ld.org/latest/meta/oold-meta-schema.json"
        world = World()
        world.add("quantities", "0.2.0", quantity("first", spec=unpinned))
        world.add("quantities", "0.2.1", quantity("patch", spec=unpinned))
        world.add("materials", "0.1.0", material("0.2", spec=unpinned))
        world.released = {"quantities": [{"module": "0.2.0", "docs": "2026.01.01"},
                                         {"module": "0.2.1", "docs": "2026.02.01"}],
                          "materials": [{"module": "0.1.0", "docs": "2026.01.15"}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for module, directory in (("quantities", "0.2.0"), ("quantities", "0.2.1"),
                                      ("quantities", "0.2"), ("materials", "0.1.0")):
                (root / module / directory).mkdir(parents=True)
            written = lock.backfill(root, world.released, world.catalog)
            names = sorted(str(p.relative_to(root)) for p in written)
            self.assertEqual(names, ["materials/0.1.0/oold.lock.json",
                                     "quantities/0.2.0/oold.lock.json",
                                     "quantities/0.2.1/oold.lock.json",
                                     "quantities/0.2/oold.lock.json"])
            old = json.loads((root / "materials/0.1.0/oold.lock.json").read_text())
            self.assertIsNone(old["spec_edition"])
            self.assertEqual(old["requires"], {"quantities": "0.2.0"})
            line_lock = json.loads((root / "quantities/0.2/oold.lock.json").read_text())
            self.assertEqual(line_lock["version"], "0.2.1")
            self.assertEqual(lock.backfill(root, world.released, world.catalog), [])


if __name__ == "__main__":
    unittest.main()
