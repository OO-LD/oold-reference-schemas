"""Dependencies on another repository: pinned by digest, downloaded safely, locked."""

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_publish  # noqa: E402
import config  # noqa: E402
import lock  # noqa: E402
import package  # noqa: E402
import pins  # noqa: E402
import remote  # noqa: E402
from test_identity import OTHER, OWN, Source, doc, ident, ref  # noqa: E402

URL = "https://packages.example.org/q-0.1.4.zip"


def dep_package(modules: dict, name: str = "q", version: str = "0.1.4") -> bytes:
    """The package another repository would publish for a module."""
    return package.build(ident(name, OTHER), version, Source(modules), namespaces=[OTHER])


def pin(data: bytes, name: str = "q", version: str = "0.1.4") -> config.Dependency:
    return config.Dependency(OTHER, name, version, URL, hashlib.sha256(data).hexdigest())


class Opener:
    def __init__(self, data: bytes):
        self.data, self.calls = data, 0

    def open(self, url, timeout=None):
        self.calls += 1
        return io.BytesIO(self.data)


def public(host, port):
    return [(0, 0, 0, "", ("93.184.216.34", port))]


def private(host, port):
    return [(0, 0, 0, "", ("10.0.0.5", port))]


class Fetch(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache = Path(tmp.name)
        self.data = dep_package({ident("q", OTHER): {"0.1.4": doc()}})
        self.digest = hashlib.sha256(self.data).hexdigest()

    def test_a_verified_download_is_cached_by_its_digest(self):
        opener = Opener(self.data)
        for _ in range(2):
            got = remote.fetch(URL, self.digest, self.cache, opener=opener, resolve=public)
            self.assertEqual(got, self.data)
        self.assertEqual(opener.calls, 1)
        self.assertTrue((self.cache / f"{self.digest}.zip").is_file())

    def test_a_different_artifact_at_the_same_url_is_refused_and_not_cached(self):
        with self.assertRaisesRegex(remote.RemoteError, "digest"):
            remote.fetch(URL, self.digest, self.cache, opener=Opener(b"swapped"), resolve=public)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_a_cached_file_that_no_longer_matches_is_not_trusted(self):
        (self.cache / f"{self.digest}.zip").write_bytes(b"tampered")
        got = remote.fetch(URL, self.digest, self.cache, opener=Opener(self.data), resolve=public)
        self.assertEqual(got, self.data)

    def test_only_public_https_addresses_are_fetched(self):
        for url in ("http://packages.example.org/q.zip", "https://user@packages.example.org/q.zip",
                    "https://packages.example.org:8443/q.zip", "file:///etc/passwd"):
            with self.assertRaises(remote.RemoteError, msg=url):
                remote.check_url(url, resolve=public)
        with self.assertRaises(remote.RemoteError):
            remote.check_url(URL, resolve=private)

    def test_a_redirect_to_a_private_address_is_refused(self):
        handler = remote.redirects(private)
        with self.assertRaises(remote.RemoteError):
            handler.redirect_request(None, None, 302, "", {}, "https://internal.example.org/x")

    def test_a_failed_request_is_a_remote_error(self):
        class Down:
            def open(self, url, timeout=None):
                raise OSError("connection refused")
        with self.assertRaisesRegex(remote.RemoteError, "could not be fetched"):
            remote.fetch(URL, self.digest, self.cache, opener=Down(), resolve=public)

    def test_a_remote_problem_surfaces_as_a_lock_error(self):
        pinned = pins.Pinned([pin(b"x")], get=lambda d: remote.fetch(
            d.package, d.sha256, self.cache, opener=Opener(b"y"), resolve=public))
        with self.assertRaises(lock.LockError):
            pinned.files(pin(b"x").identity, "0.1.4")

    def test_a_download_over_the_size_limit_is_refused(self):
        original, remote.MAX_BYTES = remote.MAX_BYTES, 10
        self.addCleanup(setattr, remote, "MAX_BYTES", original)
        with self.assertRaisesRegex(remote.RemoteError, "larger"):
            remote.fetch(URL, self.digest, self.cache, opener=Opener(self.data), resolve=public)

    def test_an_archive_with_too_many_members_or_too_much_content_is_refused(self):
        for limit in ("MAX_MEMBERS", "MAX_UNPACKED"):
            original = getattr(remote, limit)
            setattr(remote, limit, 1)
            self.addCleanup(setattr, remote, limit, original)
            with self.assertRaises(remote.RemoteError, msg=limit):
                remote.documents(self.data)


class Config(unittest.TestCase):
    TOML = """
[project]
title = "t"
repository = "https://github.com/example/r"
[namespace]
iri = "https://example.org/ns"
host = "https://schemas.example.org"
"""
    DEP = """
[[dependency]]
namespace = "https://other.example.org/ns"
module = "q"
version = "0.1.4"
package = "https://packages.example.org/q-0.1.4.zip"
sha256 = "%s"
"""

    def load(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference-schemas.toml"
            path.write_text(text, encoding="utf-8")
            return config.load(path)

    def test_no_dependencies_is_the_default(self):
        self.assertEqual(self.load(self.TOML).dependencies, ())

    def test_a_pin_names_identity_version_package_and_digest(self):
        (found,) = self.load(self.TOML + self.DEP % ("a" * 64)).dependencies
        self.assertEqual(found.identity, "https://other.example.org/ns/q")
        self.assertEqual((found.version, found.sha256), ("0.1.4", "a" * 64))

    def test_a_package_url_may_carry_a_query(self):
        text = self.TOML + (self.DEP % ("a" * 64)).replace(".zip", ".zip?download=1")
        self.assertTrue(self.load(text).dependencies[0].package.endswith("?download=1"))

    def test_a_bad_pin_is_refused(self):
        bad = (self.DEP % "abc", self.DEP.replace('"0.1.4"', '"0.1"') % ("a" * 64),
               self.DEP.replace("https://packages", "http://packages") % ("a" * 64),
               self.DEP.replace('module = "q"', 'module = "Bad Name"') % ("a" * 64),
               (self.DEP % ("a" * 64)) * 2)
        for text in bad:
            with self.assertRaises(config.ConfigError, msg=text):
                self.load(self.TOML + text)


class Pinned(unittest.TestCase):
    def setUp(self):
        self.data = dep_package({ident("q", OTHER): {"0.1.4": doc()}})
        self.dep = pin(self.data)
        self.pinned = pins.Pinned([self.dep], get=lambda d: self.data)

    def test_it_serves_the_documents_of_the_pinned_version(self):
        self.assertEqual(self.pinned.versions(ident("q", OTHER)), ["0.1.4"])
        self.assertEqual(list(self.pinned.files(ident("q", OTHER), "0.1.4")), ["T.schema.json"])
        self.assertEqual(self.pinned.digest(ident("q", OTHER)), self.dep.sha256)

    def test_an_identity_that_is_not_pinned_is_named_in_the_error(self):
        with self.assertRaisesRegex(lock.LockError, "q/x"):
            self.pinned.versions(ident("x", OTHER).replace("/x", "/q/x"))

    def test_nothing_is_downloaded_until_something_is_asked(self):
        def boom(dep):
            raise AssertionError("downloaded")
        pins.Pinned([self.dep], get=boom)


class Locking(unittest.TestCase):
    def catalog(self, modules, **pinned_modules):
        data = dep_package(pinned_modules.get("dep") or {ident("q", OTHER): {"0.1.4": doc()}})
        dep = pin(data)
        return pins.Combined(Source(modules), pins.Pinned([dep], get=lambda d: data)), dep

    def test_the_lock_records_the_digest_of_a_package_from_another_repository(self):
        catalog, dep = self.catalog({ident("m"): {"0.2.0": doc(ref("q", "0.1", OTHER))}})
        built = lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)
        self.assertEqual(built["requires"],
                         {ident("q", OTHER): {"version": "0.1.4", "sha256": dep.sha256}})
        self.assertEqual(lock.validate(built), [])

    def test_a_pin_that_does_not_satisfy_the_cited_line_is_refused(self):
        catalog, _ = self.catalog({ident("m"): {"0.2.0": doc(ref("q", "0.2", OTHER))}})
        with self.assertRaisesRegex(lock.LockError, "0.1.4"):
            lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)

    def test_a_cited_module_that_is_not_pinned_is_refused(self):
        catalog, _ = self.catalog({ident("m"): {"0.2.0": doc(ref("r", "0.1", OTHER))}})
        with self.assertRaisesRegex(lock.LockError, "not pinned"):
            lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)

    def test_own_and_pinned_modules_lock_together(self):
        own = {ident("m"): {"0.2.0": doc(ref("a", "0.1"), ref("q", "0.1", OTHER))},
               ident("a"): {"0.1.0": doc()}}
        catalog, dep = self.catalog(own)
        built = lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)
        self.assertEqual(built["requires"], {ident("a"): {"version": "0.1.0"},
                                             ident("q", OTHER): {"version": "0.1.4",
                                                                 "sha256": dep.sha256}})

    def test_a_dependency_of_the_pinned_package_must_be_pinned_too(self):
        modules = {ident("q", OTHER): {"0.1.4": doc(ref("r", "0.3", OTHER))},
                   ident("r", OTHER): {"0.3.1": doc()}}
        data = package.build(ident("q", OTHER), "0.1.4", Source(modules), namespaces=[OTHER])
        catalog = pins.Combined(Source({ident("m"): {"0.2.0": doc(ref("q", "0.1", OTHER))}}),
                                pins.Pinned([pin(data)], get=lambda d: data))
        with self.assertRaisesRegex(lock.LockError, "r"):
            lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)

    def test_a_pinned_dependency_of_the_pinned_package_must_agree_on_the_version(self):
        q_modules = {ident("q", OTHER): {"0.1.4": doc(ref("r", "0.3", OTHER))},
                     ident("r", OTHER): {"0.3.1": doc()}}
        q = package.build(ident("q", OTHER), "0.1.4", Source(q_modules), namespaces=[OTHER])
        r = dep_package({ident("r", OTHER): {"0.3.2": doc()}}, "r", "0.3.2")
        blobs = {pin(q).identity: q, pin(r, "r", "0.3.2").identity: r}
        catalog = pins.Combined(
            Source({ident("m"): {"0.2.0": doc(ref("q", "0.1", OTHER), ref("r", "0.3", OTHER))}}),
            pins.Pinned([pin(q), pin(r, "r", "0.3.2")], get=lambda d: blobs[d.identity]))
        with self.assertRaisesRegex(lock.LockError, "0.3.1"):
            lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)


    def test_a_pinned_dependency_of_the_pinned_package_must_agree_on_the_digest(self):
        r = dep_package({ident("r", OTHER): {"0.3.1": doc()}}, "r", "0.3.1")
        modules = {ident("q", OTHER): {"0.1.4": doc(ref("r", "0.3", OTHER))},
                   ident("r", OTHER): {"0.3.1": doc()}}
        files = remote.documents(package.build(ident("q", OTHER), "0.1.4", Source(modules),
                                               namespaces=[OTHER]))
        name = f"{OTHER.removeprefix('https://')}/q/0.1.4/oold.lock.json"
        locked = json.loads(files[name])
        locked["requires"][ident("r", OTHER)]["sha256"] = "b" * 64  # some other build of r
        files[name] = json.dumps(locked).encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for member, content in files.items():
                archive.writestr(member, content)
        q = buffer.getvalue()
        blobs = {pin(q).identity: q, pin(r, "r", "0.3.1").identity: r}
        catalog = pins.Combined(
            Source({ident("m"): {"0.2.0": doc(ref("q", "0.1", OTHER), ref("r", "0.3", OTHER))}}),
            pins.Pinned([pin(q), pin(r, "r", "0.3.1")], get=lambda d: blobs[d.identity]))
        with self.assertRaisesRegex(lock.LockError, "was locked against"):
            lock.build(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)


class Packaging(unittest.TestCase):
    def test_a_package_carries_the_pinned_documents_unchanged_under_their_namespace(self):
        modules = {ident("q", OTHER): {"0.1.4": doc("https://x.example.org/q")}}
        data = dep_package(modules)
        catalog = pins.Combined(Source({ident("m"): {"0.2.0": doc(ref("q", "0.1", OTHER))}}),
                                pins.Pinned([pin(data)], get=lambda d: data))
        built = package.members(ident("m"), "0.2.0", catalog, namespaces=catalog.namespaces)
        name = f"{OTHER.removeprefix('https://')}/q/0.1/T.schema.json"
        want = Source(modules).files(ident("q", OTHER), "0.1.4")["T.schema.json"]
        self.assertEqual(built[name], want)
        self.assertIn(f"{OWN.removeprefix('https://')}/m/0.2.0/oold.lock.json", built)


class Guard(unittest.TestCase):
    def check(self, entry):
        with tempfile.TemporaryDirectory() as tmp:
            published, staged = Path(tmp) / "p", Path(tmp) / "s"
            published.mkdir()
            (staged / "m" / "0.2.0").mkdir(parents=True)
            (staged / "m" / "0.2.0" / "oold.lock.json").write_text(json.dumps(
                {"lock_version": 2, "namespace": OWN, "module": "m", "version": "0.2.0",
                 "spec_edition": "1.0.1", "requires": {ident("q", OTHER): entry},
                 "ontologies": []}))
            return check_publish.lock_problems("m", "0.2.0", published, staged)

    def test_a_dependency_of_another_namespace_needs_a_digest(self):
        self.assertIn("digest", self.check({"version": "0.1.4"})[0])
        self.assertEqual(self.check({"version": "0.1.4", "sha256": "a" * 64}), [])


if __name__ == "__main__":
    unittest.main()
