"""The engine reads its identity from reference-schemas.toml and hard codes none of it."""

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
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


class OtherNamespace(unittest.TestCase):
    def test_a_lock_finds_dependencies_in_the_configured_namespace(self):
        ours = "https://example.org/ns/quantities/0.2/T.schema.json"
        theirs = "https://w3id.org/oo-ld/schemas/units/1/U.schema.json"
        schema = {"properties": {"a": {"$ref": ours}, "b": {"$ref": theirs}}}
        self.assertEqual(lock.dependencies("https://example.org/ns/m", schema,
                                           ["https://example.org/ns"]),
                         {("https://example.org/ns/quantities", "0.2")})

    def test_resolve_reads_a_module_of_this_tree_by_its_configured_iri(self):
        origin = ROOT / "modules" / "materials" / "Material.schema.json"
        iri = "https://example.org/ns/quantities/0.2/Time.schema.json"
        found = _shared.resolve(origin, iri, "https://example.org/ns")
        self.assertEqual(found, ROOT / "modules" / "quantities" / "Time.schema.json")
        other = "https://w3id.org/oo-ld/schemas/quantities/0.2/Time.schema.json"
        self.assertNotEqual(_shared.resolve(origin, other, "https://example.org/ns"),
                            ROOT / "modules" / "quantities" / "Time.schema.json")


def folded(node: ast.AST) -> str | None:
    """The text a string expression evaluates to, for constants joined by `+` or in an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = folded(node.left), folded(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.FormattedValue):
        plain = node.conversion == -1 and node.format_spec is None
        inner = folded(node.value) if plain else None
        return inner if inner is not None else "{}"
    if isinstance(node, ast.JoinedStr):
        return "".join(folded(v) or "{}" for v in node.values)
    return None


HOSTS = ("w3id.org/oo-ld", "schemas.oo-ld.org", "github.com/oo-ld")


def offending(source: str) -> list[str]:
    """Strings in a source file that name the core identity.

    Case is ignored, regex escapes are removed, and constants joined with `+` or placed in
    an f-string are folded first. Docstrings count. A string assembled at runtime cannot be
    seen, so this is a guard against carelessness and not against a determined bypass.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        text = folded(node)
        if text is None:
            continue
        plain = text.replace("\\", "").lower()
        if any(host in plain for host in HOSTS):
            found.append(text[:60])
    return found


class TheGuard(unittest.TestCase):
    """The guard below is only worth having if it catches the ways an identity sneaks in."""

    def test_plain_and_f_string_literals(self):
        self.assertTrue(offending('x = "https://schemas.oo-ld.org/a"'))
        self.assertTrue(offending('x = f"https://w3id.org/oo-ld/schemas/{m}"'))

    def test_escaped_regex(self):
        self.assertTrue(offending(r'x = r"^https://w3id\.org/oo-ld/schemas/"'))

    def test_other_case(self):
        self.assertTrue(offending('x = "https://github.com/OO-LD/oold-reference-schemas"'))

    def test_a_split_expression(self):
        self.assertTrue(offending('x = "https://schemas." + "oo-ld.org"'))

    def test_a_constant_inside_an_f_string(self):
        self.assertTrue(offending("x = f\"https://schemas.{'oo-ld.org'}\""))

    def test_a_docstring(self):
        self.assertTrue(offending('"""Served at https://schemas.oo-ld.org/x."""'))

    def test_unrelated_strings_pass(self):
        self.assertEqual(offending('x = "https://example.org/ns"; y = "OO-LD spec"'), [])
        self.assertEqual(offending('x = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"'), [])


class NothingIsHardCoded(unittest.TestCase):
    def test_no_script_names_the_core_identity(self):
        offenders = []
        for path in sorted((ROOT / "scripts").rglob("*.py")):
            offenders += [f"{path.relative_to(ROOT)}: {text!r}"
                          for text in offending(path.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])


INVALID_BASES = ("https://?x", "https://example.org/ns#frag", "https://example.org/n s",
                 "https://", "https:///path", "example.org/ns", "http://example.org/ns",
                 "https://example.org/ns?x=1", "https://:443/ns", "https://user@/ns",
                 "https://user:pw@example.org/ns", "https://example.org:notaport/ns",
                 "https://example.org/ns\x7f", "https://exa\x00mple.org/ns")


class Validation(unittest.TestCase):
    def test_a_table_of_the_wrong_type_is_a_config_error(self):
        with self.assertRaises(config.ConfigError):
            load('project = "bad"\n[namespace]\niri = "https://a.org"\nhost = "https://a.org"')

    def test_unusable_bases_are_refused(self):
        for bad in INVALID_BASES:
            with self.assertRaises(config.ConfigError, msg=repr(bad)):
                load(TOML.replace("https://example.org/ns/", bad))

    def test_a_scheme_in_capitals_is_accepted_and_normalised(self):
        cfg = load(TOML.replace("https://example.org/ns/", "HTTPS://Example.org/ns//"))
        self.assertEqual(cfg.namespace, "https://Example.org/ns")

    def test_a_file_that_cannot_be_decoded_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference-schemas.toml"
            path.write_bytes(b"\xff\xfe\x00bad")
            with self.assertRaises(config.ConfigError):
                config.load(path)

    def test_an_override_with_a_trailing_slash_still_works(self):
        schema = {"properties": {"a": {"$ref": "https://example.org/ns/q/0.2/T.schema.json"}}}
        self.assertEqual(lock.dependencies("https://example.org/ns/m", schema,
                                           ["https://example.org/ns/"]),
                         {("https://example.org/ns/q", "0.2")})
        origin = ROOT / "modules" / "materials" / "Material.schema.json"
        iri = "https://example.org/ns/quantities/0.2/Time.schema.json"
        self.assertEqual(_shared.resolve(origin, iri, "https://example.org/ns/"),
                         ROOT / "modules" / "quantities" / "Time.schema.json")

    def test_a_missing_default_file_exits_with_a_message_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(ROOT / "scripts", Path(tmp) / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
            result = subprocess.run([sys.executable, "-c", "import config"],
                                    cwd=Path(tmp) / "scripts", capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: reference-schemas.toml not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class StandaloneLoader(unittest.TestCase):
    """macros.py carries its own loader, which must judge identities the same way."""

    def identity(self, text: bytes) -> str:
        import macros
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "reference-schemas.toml").write_bytes(text)
            before = macros.ROOT
            macros.ROOT = tmp
            try:
                return macros._identity()
            finally:
                macros.ROOT = before

    def test_it_refuses_what_the_shared_loader_refuses(self):
        import json
        for bad in INVALID_BASES:
            toml = f'[namespace]\niri = {json.dumps(bad)}\n'.encode()
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                self.identity(toml)

    def test_it_accepts_and_normalises_like_the_shared_loader(self):
        self.assertEqual(self.identity(b'[namespace]\niri = "https://example.org/ns//"\n'),
                         "https://example.org/ns")

    def test_unreadable_files_give_an_actionable_error(self):
        for text in (b"not = [valid", b"\xff\xfe\x00bad", b'namespace = "x"'):
            with self.assertRaises(RuntimeError, msg=text):
                self.identity(text)


class AnotherIdentity(unittest.TestCase):
    """The engine run end to end under a namespace that is not the core's."""

    def test_the_mapping_sets_follow_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(ROOT / "scripts", work / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "modules", work / "modules")
            (work / "generated").mkdir()
            shutil.copy(ROOT / "generated" / "labels.json", work / "generated" / "labels.json")
            shutil.copy(ROOT / "generated" / "versions.json", work / "generated" / "versions.json")
            shutil.copy(ROOT / "VERSION", work / "VERSION")
            (work / "reference-schemas.toml").write_text(TOML, encoding="utf-8")
            done = subprocess.run([sys.executable, "scripts/build_mappings.py"], cwd=work,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            header = (work / "generated" / "mappings" / "emmo.sssom.tsv").read_text()
            self.assertIn("# mapping_set_id: https://example.org/ns/mappings/emmo.sssom.tsv",
                          header)
            self.assertIn("# mapping_provider: https://github.com/example/schemas", header)
            self.assertIn("for the Example schemas", header)
            self.assertNotIn("oo-ld", header.lower())


class OfflineRecipe(unittest.TestCase):
    def test_validate_offline_reads_a_package_of_another_namespace(self):
        sys.path.insert(0, str(ROOT / "examples" / "versioning"))
        try:
            import validate_offline
        except ImportError:
            self.skipTest("jsonschema and referencing are not installed")
        schema = b'{"type": "object", "properties": {"x": {"type": "number"}}}'
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "m-1.0.0.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("m/1.0.0/A.schema.json", schema)
            good, bad = Path(tmp) / "good.json", Path(tmp) / "bad.json"
            good.write_text('{"$schema": "A.schema.json", "x": 1}')
            bad.write_text('{"$schema": "A.schema.json", "x": "no"}')
            base = "https://example.org/ns/"
            self.assertEqual(validate_offline.validate(package, good, base=base), [])
            self.assertEqual(len(validate_offline.validate(package, bad, base=base)), 1)
            full = "https://example.org/ns/m/1.0.0/A.schema.json"
            self.assertEqual(validate_offline.validate(package, good, full, base), [])


if __name__ == "__main__":
    unittest.main()
