"""oold.lock.json: exact pins for the closure of one module version."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lock  # noqa: E402

BASE = "https://w3id.org/oo-ld/schemas"
SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"


def ref(module: str, line: str, name: str) -> str:
    return f"{BASE}/{module}/{line}/{name}.schema.json"


def schema(refs=(), contexts=(), sources=(), spec=SPEC) -> dict:
    out = {"$schema": spec, "properties": {f"p{i}": {"$ref": r} for i, r in enumerate(refs)}}
    if contexts:
        out["@context"] = list(contexts)
    if sources:
        out["x-oold-context"] = {"t": {f"x:{i}": {"x-oold-sssom": {"object_source_version": s}}
                                       for i, s in enumerate(sources)}}
    return out


class Catalog:
    def __init__(self, modules):
        self.modules = modules

    def versions(self, module):
        return list(self.modules.get(module, {}))

    def schemas(self, module, version):
        return self.modules[module][version]


class Dependencies(unittest.TestCase):
    def test_finds_refs_and_contexts_of_other_modules(self):
        s = schema(refs=[ref("quantities", "0.2", "Time")],
                   contexts=[ref("devices", "1", "Cell"), "Local.schema.json"])
        self.assertEqual(lock.dependencies("materials", s),
                         {("quantities", "0.2"), ("devices", "1")})

    def test_ignores_own_module_relative_refs_and_mapping_sets(self):
        s = schema(refs=[ref("materials", "0.2", "Composition"), "Composition.schema.json",
                         f"{BASE}/mappings/emmo.sssom.tsv"])
        self.assertEqual(lock.dependencies("materials", s), set())

    def test_finds_refs_nested_in_defs(self):
        s = {"$defs": {"A": {"items": {"$ref": ref("quantities", "0.2", "Time")}}}}
        self.assertEqual(lock.dependencies("m", s), {("quantities", "0.2")})


class Resolve(unittest.TestCase):
    def test_newest_patch_of_the_line(self):
        self.assertEqual(lock.resolve_line("q", "0.2", ["0.1.0", "0.2.0", "0.2.3", "0.3.0"]),
                         "0.2.3")

    def test_major_line(self):
        self.assertEqual(lock.resolve_line("q", "1", ["0.9.0", "1.0.0", "1.4.2", "2.0.0"]),
                         "1.4.2")

    def test_numeric_order_not_text_order(self):
        self.assertEqual(lock.resolve_line("q", "0.2", ["0.2.9", "0.2.10"]), "0.2.10")

    def test_unsatisfied_line_is_an_error(self):
        with self.assertRaises(lock.LockError):
            lock.resolve_line("q", "0.4", ["0.2.0", "0.3.0"])


class Build(unittest.TestCase):
    def catalog(self):
        return Catalog({
            "quantities": {"0.2.0": {"Time": schema(sources=["https://w3id.org/emmo/1.0.4"])},
                           "0.3.0": {"Time": schema()}},
            "units": {"1.0.0": {"Unit": schema(sources=["https://w3id.org/pmd/co/3.1.0"])}},
            "materials": {"0.2.0": {
                "Material": schema(refs=[ref("quantities", "0.2", "Time")],
                                   sources=["https://w3id.org/emmo/1.0.4"])}},
        })

    def test_pins_exact_versions_from_the_line(self):
        built = lock.build("materials", "0.2.0", self.catalog())
        self.assertEqual(built["requires"], {"quantities": "0.2.0"})
        self.assertEqual(built["version"], "0.2.0")
        self.assertEqual(built["spec_edition"], "1.0.1")
        self.assertEqual(built["lock_version"], 1)

    def test_closure_is_transitive(self):
        catalog = self.catalog()
        catalog.modules["quantities"]["0.2.0"]["Time"] = schema(
            refs=[ref("units", "1", "Unit")])
        built = lock.build("materials", "0.2.0", catalog)
        self.assertEqual(built["requires"], {"quantities": "0.2.0", "units": "1.0.0"})

    def test_ontologies_are_collected_over_the_closure(self):
        catalog = self.catalog()
        catalog.modules["quantities"]["0.2.0"]["Time"] = schema(
            refs=[ref("units", "1", "Unit")], sources=["https://w3id.org/emmo/1.0.4"])
        built = lock.build("materials", "0.2.0", catalog)
        self.assertEqual(built["ontologies"],
                         ["https://w3id.org/emmo/1.0.4", "https://w3id.org/pmd/co/3.1.0"])

    def test_two_lines_of_one_module_conflict(self):
        catalog = self.catalog()
        catalog.modules["materials"]["0.2.0"]["Other"] = schema(
            refs=[ref("quantities", "0.3", "Time")])
        with self.assertRaises(lock.LockError):
            lock.build("materials", "0.2.0", catalog)

    def test_a_cycle_does_not_loop(self):
        catalog = self.catalog()
        catalog.modules["quantities"]["0.2.0"]["Time"] = schema(
            refs=[ref("materials", "0", "Material")])
        catalog.modules["materials"]["0.0.1"] = {}
        catalog.modules["materials"]["0.2.0"]["Material"] = schema(
            refs=[ref("quantities", "0.2", "Time")])
        built = lock.build("materials", "0.2.0", catalog)
        self.assertNotIn("materials", built["requires"])

    def test_a_module_mixing_editions_is_an_error(self):
        catalog = self.catalog()
        catalog.modules["materials"]["0.2.0"]["Other"] = schema(
            spec="https://oo-ld.org/1.0.0/meta/oold-meta-schema.json")
        with self.assertRaises(lock.LockError):
            lock.build("materials", "0.2.0", catalog)

    def test_output_is_deterministic(self):
        built = lock.build("materials", "0.2.0", self.catalog())
        text = lock.render(built)
        self.assertEqual(text, lock.render(dict(reversed(list(built.items())))))
        self.assertTrue(text.endswith("}\n"))


class Visible(unittest.TestCase):
    ENTRIES = [{"module": "0.2.0", "docs": "2026.08.17"}, {"module": "0.2.1", "docs": "2026.08.24"},
               {"module": "0.3.0", "docs": "2026.08.24-2"}, {"module": "0.4.0", "docs": "2026.09.01"}]

    def test_without_a_cutoff_everything_and_the_tree_version_is_visible(self):
        self.assertEqual(lock.visible(self.ENTRIES, None, "0.5.0"),
                         ["0.2.0", "0.2.1", "0.3.0", "0.4.0", "0.5.0"])

    def test_a_cutoff_hides_later_releases_and_the_tree_version(self):
        self.assertEqual(lock.visible(self.ENTRIES, "2026.08.24", "0.5.0"), ["0.2.0", "0.2.1"])

    def test_a_same_day_second_release_comes_after_the_first(self):
        self.assertEqual(lock.visible(self.ENTRIES, "2026.08.24-2", None),
                         ["0.2.0", "0.2.1", "0.3.0"])


class Lenient(unittest.TestCase):
    def test_an_unpinned_edition_is_an_error_unless_lenient(self):
        catalog = Catalog({"m": {"0.1.0": {"A": schema(spec="https://oo-ld.org/latest/meta/"
                                                            "oold-meta-schema.json")}}})
        with self.assertRaises(lock.LockError):
            lock.build("m", "0.1.0", catalog)
        built = lock.build("m", "0.1.0", catalog, lenient=True)
        self.assertIsNone(built["spec_edition"])
        self.assertEqual(lock.validate(built), [])


class Validate(unittest.TestCase):
    GOOD = {"lock_version": 1, "module": "m", "version": "0.2.0", "spec_edition": "1.0.1",
            "requires": {"q": "0.2.0"}, "ontologies": ["https://w3id.org/emmo/1.0.4"]}

    def test_accepts_a_built_lock(self):
        self.assertEqual(lock.validate(self.GOOD), [])

    def test_rejects_ranges_and_missing_keys(self):
        bad = dict(self.GOOD, requires={"q": "0.2"})
        self.assertEqual(len(lock.validate(bad)), 1)
        missing = {k: v for k, v in self.GOOD.items() if k != "spec_edition"}
        self.assertEqual(len(lock.validate(missing)), 1)

    def test_rejects_unknown_keys(self):
        self.assertEqual(len(lock.validate(dict(self.GOOD, extra=1))), 1)


if __name__ == "__main__":
    unittest.main()
