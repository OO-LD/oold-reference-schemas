"""Identities carry their namespace: locks, packages and readers keep namespaces apart."""

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "versioning"))

import check_publish  # noqa: E402
import lock  # noqa: E402
import package  # noqa: E402
from config import CONFIG  # noqa: E402

try:
    import validate_offline
except ImportError:  # jsonschema and referencing are installed by make check
    validate_offline = None

OWN = CONFIG.namespace
OTHER = "https://other.example.org/ns"
SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"


def ident(module: str, namespace: str = OWN) -> str:
    return f"{namespace}/{module}"


def ref(module: str, line: str, namespace: str = OWN) -> str:
    return f"{namespace}/{module}/{line}/T.schema.json"


def doc(*refs: str) -> dict:
    return {"$schema": SPEC, "properties": {f"p{i}": {"$ref": r} for i, r in enumerate(refs)}}


class Source:
    """A catalog keyed by identity, with the files a package needs."""

    def __init__(self, modules: dict[str, dict[str, dict]]):
        self.modules = modules

    def versions(self, identity):
        return list(self.modules.get(identity, {}))

    def schemas(self, identity, version):
        return {"T.schema.json": self.modules[identity][version]}

    def files(self, identity, version):
        return {n: json.dumps(s, indent=2).encode() + b"\n"
                for n, s in self.schemas(identity, version).items()}


class Lock(unittest.TestCase):
    def source(self):
        return Source({ident("m"): {"0.2.0": doc(ref("q", "0.2"))},
                       ident("q"): {"0.2.0": doc(), "0.2.1": doc()}})

    def test_the_lock_names_its_namespace_and_keys_requires_by_identity(self):
        built = lock.build(ident("m"), "0.2.0", self.source())
        self.assertEqual((built["lock_version"], built["namespace"], built["module"]),
                         (2, OWN, "m"))
        self.assertEqual(built["requires"], {ident("q"): {"version": "0.2.1"}})
        self.assertEqual(list(json.loads(lock.render(built))), list(lock.FIELDS))

    def test_the_same_module_name_in_two_namespaces_is_two_dependencies(self):
        source = Source({ident("m"): {"0.2.0": doc(ref("q", "0.2"), ref("q", "0.1", OTHER))},
                         ident("q"): {"0.2.0": doc()}, ident("q", OTHER): {"0.1.4": doc()}})
        built = lock.build(ident("m"), "0.2.0", source, namespaces=[OWN, OTHER])
        self.assertEqual(built["requires"], {ident("q"): {"version": "0.2.0"},
                                             ident("q", OTHER): {"version": "0.1.4"}})
        unlisted = lock.build(ident("m"), "0.2.0", source)
        self.assertEqual(list(unlisted["requires"]), [ident("q")])

    def test_one_identity_on_two_lines_is_a_conflict_naming_both(self):
        source = Source({ident("m"): {"0.2.0": doc(ref("q", "0.2"), ref("q", "0.3"))},
                         ident("q"): {"0.2.0": doc(), "0.3.0": doc()}})
        with self.assertRaisesRegex(lock.LockError, r"0\.2\.0.*0\.3\.0|0\.3\.0.*0\.2\.0"):
            lock.build(ident("m"), "0.2.0", source)

    def test_a_reference_may_cite_an_exact_version(self):
        source = Source({ident("m"): {"0.2.0": doc(ref("q", "0.2.0"))},
                         ident("q"): {"0.2.0": doc(), "0.2.1": doc()}})
        self.assertEqual(lock.build(ident("m"), "0.2.0", source)["requires"],
                         {ident("q"): {"version": "0.2.0"}})
        source.modules[ident("m")]["0.2.0"] = doc(ref("q", "0.9.9"))
        with self.assertRaises(lock.LockError):
            lock.build(ident("m"), "0.2.0", source)


class Dependencies(unittest.TestCase):
    def test_only_complete_schema_references_count(self):
        for text in (ref("q", "0.2") + ".bak", ref("q", "0.2") + "/more"):
            self.assertEqual(lock.dependencies(ident("m"), doc(text)), set(), text)
        found = lock.dependencies(ident("m"), doc(ref("q", "0.2") + "#/$defs/A"))
        self.assertEqual(found, {(ident("q"), "0.2")})

    def test_a_property_named_like_a_data_keyword_is_still_read(self):
        schema = {"properties": {"default": {"$ref": ref("q", "0.2")},
                                 "enum": {"$ref": ref("r", "1")}}}
        self.assertEqual(lock.dependencies(ident("m"), schema),
                         {(ident("q"), "0.2"), (ident("r"), "1")})

    def test_example_data_is_not_a_reference(self):
        data = {"$ref": ref("q", "0.2")}
        schema = {"examples": [data], "default": data,
                  "properties": {"x": {"const": data, "enum": [data]}}}
        self.assertEqual(lock.dependencies(ident("m"), schema), set())


class Formats(unittest.TestCase):
    V1: ClassVar[dict] = {"lock_version": 1, "module": "m", "version": "0.2.0",
                          "spec_edition": "1.0.1", "requires": {"q": "0.2.0"}, "ontologies": []}

    def v2(self, **change):
        return {"lock_version": 2, "namespace": OWN, "module": "m", "version": "0.2.0",
                "spec_edition": "1.0.1", "requires": {ident("q"): {"version": "0.2.0"}},
                "ontologies": [], **change}

    def test_both_formats_validate(self):
        self.assertEqual(lock.validate(self.V1), [])
        self.assertEqual(lock.validate(self.v2()), [])
        digest = {ident("q"): {"version": "0.2.0", "sha256": "a" * 64}}
        self.assertEqual(lock.validate(self.v2(requires=digest)), [])

    def test_a_v1_lock_reads_as_the_repository_namespace(self):
        read = lock.read_lock(self.V1)
        self.assertEqual(read["namespace"], OWN)
        self.assertEqual(read["requires"], {ident("q"): {"version": "0.2.0"}})
        self.assertEqual(self.V1["requires"], {"q": "0.2.0"})
        self.assertEqual(lock.read_lock(self.v2()), self.v2())

    def test_what_is_refused(self):
        for bad in (None, [], {**self.V1, "lock_version": 3}, {**self.v2(), "extra": 1},
                    self.v2(version="0.2"), self.v2(spec_edition="1.2.3garbage"),
                    self.v2(module="Bad Name"), self.v2(namespace="https://"),
                    self.v2(namespace=OWN + "/"), self.v2(requires={"q": {"version": "0.2.0"}}),
                    self.v2(requires={ident("q"): "0.2.0"}),
                    self.v2(requires={ident("q"): {"version": "0.2.0", "extra": 1}}),
                    self.v2(requires={ident("q"): {"version": "0.2.0", "sha256": "abc"}})):
            self.assertNotEqual(lock.validate(bad), [], bad)


class PackageLayout(unittest.TestCase):
    def test_members_are_named_by_the_iri_without_its_scheme(self):
        source = Source({ident("m"): {"0.2.0": doc(ref("q", "0.2"))},
                         ident("q"): {"0.2.0": doc()}})
        prefix = OWN.removeprefix("https://")
        self.assertEqual(set(package.members(ident("m"), "0.2.0", source)), {
            f"{prefix}/m/0.2.0/T.schema.json", f"{prefix}/m/0.2/T.schema.json",
            f"{prefix}/m/0.2.0/oold.lock.json", f"{prefix}/m/0.2/oold.lock.json",
            f"{prefix}/q/0.2.0/T.schema.json", f"{prefix}/q/0.2/T.schema.json"})

    def test_two_namespaces_with_one_module_name_do_not_collide(self):
        source = Source({ident("m"): {"0.2.0": doc(ref("q", "0.2"), ref("q", "0.1", OTHER))},
                         ident("q"): {"0.2.0": doc("https://x.example.org/own")},
                         ident("q", OTHER): {"0.1.4": doc("https://x.example.org/other")}})
        built = package.members(ident("m"), "0.2.0", source, namespaces=[OWN, OTHER])
        mine = built[f"{OWN.removeprefix('https://')}/q/0.2/T.schema.json"]
        theirs = built[f"{OTHER.removeprefix('https://')}/q/0.1/T.schema.json"]
        self.assertIn(b"x.example.org/own", mine)
        self.assertIn(b"x.example.org/other", theirs)


@unittest.skipIf(validate_offline is None, "jsonschema and referencing are not installed")
class Reader(unittest.TestCase):
    def check(self, member: str, schema: str = "A.schema.json") -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            package_file = Path(tmp) / "m-1.0.0.zip"
            with zipfile.ZipFile(package_file, "w") as archive:
                archive.writestr(member, '{"type": "object"}')
            instance = Path(tmp) / "i.json"
            instance.write_text(json.dumps({"$schema": schema}))
            return validate_offline.validate(package_file, instance,
                                             base="https://example.org/ns/")

    def test_the_namespaced_and_the_older_layout_are_both_read(self):
        self.assertEqual(self.check("example.org/ns/m/1.0.0/A.schema.json"), [])
        self.assertEqual(self.check("m/1.0.0/A.schema.json"), [])

    def test_a_member_of_another_namespace_is_not_found_for_this_one(self):
        self.assertEqual(len(self.check("other.org/ns/m/1.0.0/A.schema.json")), 1)

    def test_an_absolute_schema_of_another_namespace_is_kept_as_it_is(self):
        self.assertEqual(self.check("other.org/ns/q/1.0.0/A.schema.json",
                                    "https://other.org/ns/q/1.0.0/A.schema.json"), [])


class Publishing(unittest.TestCase):
    def staged(self, requires: dict, **change) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        published, staged = Path(tmp.name) / "published", Path(tmp.name) / "staged"
        published.mkdir()
        (staged / "m" / "0.2.0").mkdir(parents=True)
        (staged / "m" / "0.2.0" / "oold.lock.json").write_text(json.dumps(
            {"lock_version": 2, "namespace": OWN, "module": "m", "version": "0.2.0",
             "spec_edition": "1.0.1", "requires": requires, "ontologies": [], **change}))
        return published, staged

    def problems(self, published, staged):
        return check_publish.lock_problems("m", "0.2.0", published, staged)

    def test_a_dependency_of_this_namespace_must_exist(self):
        published, staged = self.staged({ident("q"): {"version": "0.2.0"}})
        self.assertIn(ident("q"), self.problems(published, staged)[0])
        (published / "q" / "0.2.0").mkdir(parents=True)
        self.assertEqual(self.problems(published, staged), [])

    def test_a_v1_lock_is_still_checked(self):
        published, staged = self.staged({})
        (staged / "m" / "0.2.0" / "oold.lock.json").write_text(json.dumps(
            {**Formats.V1, "spec_edition": None}))
        self.assertEqual(len(self.problems(published, staged)), 1)

    def test_a_broken_or_foreign_lock_is_reported(self):
        for change in ({"module": "other"}, {"version": "0.9.9"}, {"namespace": OTHER},
                       {"ontologies": "no"}):
            published, staged = self.staged({}, **change)
            self.assertEqual(len(self.problems(published, staged)), 1, change)
        published, staged = self.staged({})
        (staged / "m" / "0.2.0" / "oold.lock.json").write_text("not json")
        self.assertEqual(len(self.problems(published, staged)), 1)


if __name__ == "__main__":
    unittest.main()
