"""The engine reads its identity from reference-schemas.toml and hard codes none of it."""

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _shared  # noqa: E402
import config  # noqa: E402
import lock  # noqa: E402

TOML = """
[project]
title = "Example schemas"
repository = "https://github.com/example/schemas"

[namespace]
iri = "https://example.org/ns/"
host = "https://schemas.example.org"
"""


def load(text: str) -> config.Config:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reference-schemas.toml"
        path.write_text(text, encoding="utf-8")
        return config.load(path)


class Loading(unittest.TestCase):
    def test_reads_the_values_and_drops_trailing_slashes(self):
        cfg = load(TOML)
        self.assertEqual(cfg.namespace, "https://example.org/ns")
        self.assertEqual(cfg.host, "https://schemas.example.org")
        self.assertEqual(cfg.title, "Example schemas")
        self.assertEqual(cfg.repository, "https://github.com/example/schemas")

    def test_derives_the_genid_base_and_module_iris(self):
        cfg = load(TOML)
        self.assertEqual(cfg.genid, "https://schemas.example.org/.well-known/genid/")
        self.assertEqual(cfg.iri("quantities", "0.2"), "https://example.org/ns/quantities/0.2")

    def test_knows_which_iris_it_owns(self):
        cfg = load(TOML)
        self.assertTrue(cfg.owns("https://example.org/ns/quantities/0.2/Time.schema.json"))
        self.assertFalse(cfg.owns("https://example.org/nsx/quantities"))
        self.assertFalse(cfg.owns("https://w3id.org/oo-ld/schemas/quantities"))

    def test_a_missing_file_says_what_to_create(self):
        with self.assertRaises(config.ConfigError) as caught:
            config.load(Path("/nonexistent/reference-schemas.toml"))
        self.assertIn("reference-schemas.toml", str(caught.exception))

    def test_a_missing_key_names_it(self):
        with self.assertRaises(config.ConfigError) as caught:
            load(TOML.replace('host = "https://schemas.example.org"', ""))
        self.assertIn("namespace.host", str(caught.exception))

    def test_an_iri_must_be_https(self):
        with self.assertRaises(config.ConfigError):
            load(TOML.replace("https://example.org/ns/", "http://example.org/ns/"))

    def test_the_repository_config_reproduces_todays_identity(self):
        cfg = config.load()
        self.assertEqual(cfg.namespace, "https://w3id.org/oo-ld/schemas")
        self.assertEqual(cfg.host, "https://schemas.oo-ld.org")


class OtherNamespace(unittest.TestCase):
    def test_a_lock_finds_dependencies_in_the_configured_namespace(self):
        ours = "https://example.org/ns/quantities/0.2/T.schema.json"
        theirs = "https://w3id.org/oo-ld/schemas/units/1/U.schema.json"
        schema = {"properties": {"a": {"$ref": ours}, "b": {"$ref": theirs}}}
        self.assertEqual(lock.dependencies("m", schema, "https://example.org/ns"),
                         {("quantities", "0.2")})

    def test_resolve_reads_a_module_of_this_tree_by_its_configured_iri(self):
        origin = ROOT / "modules" / "materials" / "Material.schema.json"
        iri = "https://example.org/ns/quantities/0.2/Time.schema.json"
        found = _shared.resolve(origin, iri, "https://example.org/ns")
        self.assertEqual(found, ROOT / "modules" / "quantities" / "Time.schema.json")
        other = "https://w3id.org/oo-ld/schemas/quantities/0.2/Time.schema.json"
        self.assertNotEqual(_shared.resolve(origin, other, "https://example.org/ns"),
                            ROOT / "modules" / "quantities" / "Time.schema.json")


class NothingIsHardCoded(unittest.TestCase):
    """No script carries the oo-ld identity in code. Docstrings may describe it."""

    LITERALS = ("w3id.org/oo-ld", "schemas.oo-ld.org", "github.com/OO-LD/oold-reference")

    def strings(self, path: Path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                first = node.body[0] if node.body else None
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings):
                yield node.lineno, node.value

    def test_scripts_read_identity_from_the_config(self):
        offenders = []
        for path in sorted((ROOT / "scripts").glob("*.py")):
            if path.name == "config.py":
                continue
            for line, value in self.strings(path):
                if any(literal in value for literal in self.LITERALS):
                    offenders.append(f"{path.name}:{line}: {value[:60]!r}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
