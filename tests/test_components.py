"""The registry of components: strict entries, a package that has to hold up, a safe page."""

import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import components  # noqa: E402
import config  # noqa: E402
import lock  # noqa: E402

CORE = config.CONFIG.namespace
NAMESPACE = "https://example.org/acme"
BASE = "example.org/acme/widgets/1.0.0"


def package(members: dict[str, bytes] | None = None, **changes) -> bytes:
    """A package as a component would publish it, with the lock fields it names changed."""
    found = {"lock_version": lock.LOCK_VERSION, "namespace": NAMESPACE, "module": "widgets",
             "version": "1.0.0", "spec_edition": "1.0.1", "requires": {}, "ontologies": []}
    found.update(changes)
    documents = {f"{BASE}/{lock.FILE}": json.dumps(found).encode(),
                 f"{BASE}/Widget.schema.json": b"{}"}
    documents.update(members or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in documents.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def table(data: bytes, **changes) -> dict:
    entry = {"title": "Acme widgets", "description": "Widgets, as schemas.",
             "repository": "https://github.com/acme/widgets", "site": "https://acme.example.org/w",
             "license": "MIT", "namespace": NAMESPACE, "module": "widgets", "version": "1.0.0",
             "package": "https://acme.example.org/w/packages/widgets-1.0.0.zip",
             "sha256": hashlib.sha256(data).hexdigest()}
    entry.update(changes)
    return entry


def entry(data: bytes, **changes) -> components.Component:
    (found,) = components.parse({"component": [table(data, **changes)]})
    return found


class Registry(unittest.TestCase):
    def setUp(self):
        self.data = package()

    def test_an_empty_registry_lists_nothing(self):
        self.assertEqual(components.parse({}), ())
        self.assertIn("No components are listed yet", components.render([]))

    def test_a_valid_entry_is_read(self):
        found = entry(self.data)
        self.assertEqual(found.pin.identity, f"{NAMESPACE}/widgets")
        self.assertEqual(found.license, "MIT")

    def test_unknown_fields_and_other_tables_are_refused(self):
        with self.assertRaises(components.ComponentError):
            entry(self.data, colour="red")
        with self.assertRaises(components.ComponentError):
            components.parse({"project": {}})

    def test_text_is_one_short_line(self):
        for key, value in (("title", "two\nlines"), ("title", "x" * 81), ("description", ""),
                           ("license", "not a licence")):
            with self.subTest(key=key), self.assertRaises(components.ComponentError):
                entry(self.data, **{key: value})

    def test_links_must_be_https_and_carry_no_markup(self):
        for key, value in (("site", "http://acme.example.org"), ("repository", "ftp://x.org/y"),
                           ("site", "https://acme.example.org/a)b")):
            with self.subTest(key=key), self.assertRaises(components.ComponentError):
                entry(self.data, **{key: value})

    def test_the_namespace_must_not_overlap_the_core(self):
        for namespace in (CORE, CORE + "/sub", CORE.rsplit("/", 1)[0]):
            with self.subTest(namespace=namespace), self.assertRaises(components.ComponentError):
                entry(self.data, namespace=namespace)

    def test_one_namespace_is_one_component(self):
        other = table(self.data, module="gadgets")
        for second in (other, table(self.data, namespace=NAMESPACE + "/inner", module="gadgets")):
            with self.subTest(namespace=second["namespace"]), \
                    self.assertRaises(components.ComponentError):
                components.parse({"component": [table(self.data), second]})

    def test_the_same_module_name_in_two_namespaces_is_allowed(self):
        second = table(self.data, namespace="https://example.com/beta")
        found = components.parse({"component": [table(self.data), second]})
        self.assertEqual([c.pin.module for c in found], ["widgets", "widgets"])


class Package(unittest.TestCase):
    def test_a_matching_package_is_accepted(self):
        data = package()
        found = components.verify(entry(data), data)
        self.assertEqual((found.spec_edition, found.requires), ("1.0.1", ()))

    def test_a_release_candidate_edition_is_accepted(self):
        data = package(spec_edition="1.0.0-rc.5")
        self.assertEqual(components.verify(entry(data), data).spec_edition, "1.0.0-rc.5")

    def test_it_may_cite_modules_of_the_core(self):
        cited = f"{CORE}/quantities"
        data = package({f"{cited.removeprefix('https://')}/0.2.0/Length.schema.json": b"{}"},
                       requires={cited: {"version": "0.2.0"}})
        self.assertEqual(components.verify(entry(data), data).requires, ("quantities 0.2.0",))

    def test_a_changed_package_is_refused(self):
        data = package()
        with self.assertRaisesRegex(components.ComponentError, "digest"):
            components.verify(entry(data), data + b"x")

    def test_the_lock_must_agree_with_the_entry(self):
        for change in ({"module": "gadgets"}, {"version": "1.0.1"},
                       {"namespace": "https://example.org/other"}, {"lock_version": 1}):
            data = package(**change)
            with self.subTest(change=change), self.assertRaises(components.ComponentError):
                components.verify(entry(data), data)

    def test_a_module_that_is_not_the_core_may_not_be_cited(self):
        data = package(requires={"https://example.com/other/mod": {"version": "1.0.0"}})
        with self.assertRaisesRegex(components.ComponentError, "may cite only"):
            components.verify(entry(data), data)

    def test_a_member_of_an_undeclared_module_is_refused(self):
        data = package({"evil.example/x/1.0.0/Y.schema.json": b"{}"})
        with self.assertRaisesRegex(components.ComponentError, "not under a module"):
            components.verify(entry(data), data)

    def test_a_missing_lock_or_a_bad_archive_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(f"{BASE}/Widget.schema.json", b"{}")
        for data in (buffer.getvalue(), b"not a zip"):
            with self.subTest(size=len(data)), self.assertRaises(components.ComponentError):
                components.verify(entry(data), data)


class Page(unittest.TestCase):
    def test_text_from_the_registry_cannot_inject_markup(self):
        data = package()
        found = entry(data, title="<script>alert(1)</script> [x](http://evil)",
                      description="*bold* `code` <img src=x onerror=y>")
        page = components.render([(found, components.verify(found, data))])
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img", page)
        self.assertNotIn("[x](http", page)
        self.assertIn("&lt;script&gt;", page)

    def test_a_card_shows_the_verified_facts_and_links(self):
        data = package()
        found = entry(data)
        page = components.render([(found, components.verify(found, data))])
        for expected in ("Acme widgets", f"`{NAMESPACE}`", "1.0.1", "<https://acme.example.org/w>",
                         "<https://github.com/acme/widgets>", "does not make its identifiers"):
            self.assertIn(expected, page)

    def test_build_verifies_every_entry_before_writing_anything(self):
        data = package()
        with self.assertRaises(components.ComponentError):
            components.build((entry(data),), get=lambda pin: package(module="gadgets"))
        self.assertIn("Acme widgets", components.build((entry(data),), get=lambda pin: data))

    def test_the_shipped_registry_is_valid(self):
        components.load()


if __name__ == "__main__":
    unittest.main()
