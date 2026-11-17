"""Write oold.lock.json: the exact versions a module version was released against.

A schema cites its dependencies by compatibility line (`quantities/0.2/`), which keeps
patches flowing. The line says which versions may be used, not which one was. The lock
records the exact version each line resolved to, transitively, plus the spec edition and
the ontology versions the mappings were checked against.

Plain JSON Schema validators ignore it. It serves the offline package, the release checks
and any tool that wants a reproducible closure.

A lock is a pure function of the module version and its release: a dependency is resolved
among the versions released no later than the module itself. Regenerating it later, after a
dependency has had a patch, gives the same bytes, which is what lets a release stay frozen.

Usage:
  python scripts/lock.py                  write generated/locks/<module>/oold.lock.json
  python scripts/lock.py --check          fail if a committed lock is stale
  python scripts/lock.py --backfill ROOT  add the lock to released versions published without
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import level
from _shared import MODULES, ROOT, line, module_version, read
from config import CONFIG
from spec_edition import edition_of

LOCK_VERSION = 2
OUT = ROOT / "generated" / "locks"
FILE = "oold.lock.json"

EXACT = re.compile(r"\d+\.\d+\.\d+")
EDITION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?")
NAME = re.compile(r"[a-z0-9_-]+")
SHA256 = re.compile(r"[0-9a-f]{64}")
BASE = r"https://[^/?#\s]+(?:/[^?#\s]*[^/?#\s])?"  # an https base IRI, no trailing slash
IDENTITY = re.compile(rf"{BASE}/[a-z0-9_-]+")
FIELDS = ("lock_version", "namespace", "module", "version", "spec_edition", "requires",
          "ontologies")
V1_FIELDS = tuple(f for f in FIELDS if f != "namespace")


class LockError(Exception):
    """A closure that cannot be pinned."""


class Catalog(Protocol):
    def versions(self, identity: str) -> list[str]: ...
    def schemas(self, identity: str, version: str) -> dict[str, dict]: ...


def identity(namespace: str, module: str) -> str:
    """The canonical name of a module: its namespace and its own name, two namespaces may
    both hold a `quantities`."""
    return f"{namespace.rstrip('/')}/{module}"


def split(name: str) -> tuple[str, str]:
    namespace, _, module = name.rpartition("/")
    return namespace, module


def order(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


# Example data and constants are values, not references: a `$ref` inside them is text
DATA = {"examples", "const", "default", "enum"}
# maps of name to subschema: the keys are names, never keywords
NAMED = {"properties", "patternProperties", "$defs", "definitions"}


def strings(node, key: str) -> Iterable[str]:
    """Every string under `key`, at any depth, whether given alone or in a list.

    Example data and constants are skipped: a `$ref` written inside them is not a reference.
    """
    if isinstance(node, dict):
        for name, value in node.items():
            if name in DATA:
                continue
            if name == key:
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, str):
                        yield item
            if name in NAMED and isinstance(value, dict):
                for sub in value.values():
                    yield from strings(sub, key)
            else:
                yield from strings(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value, key)


def dependencies(own: str, schema: dict,
                 namespaces: Iterable[str] | None = None) -> set[tuple[str, str]]:
    """The (identity, line or exact version) pairs a schema reaches by `$ref` or `@context`.

    Only the given namespaces are followed: a schema may cite anything, but only what is
    declared can be locked. `own` is the identity of the module the schema belongs to.
    """
    found = set()
    texts = [*strings(schema, "$ref"), *strings(schema, "@context")]
    for namespace in [CONFIG.namespace] if namespaces is None else namespaces:
        base = namespace.rstrip("/")
        pattern = re.compile(rf"^{re.escape(base)}/([a-z0-9_-]+)/"
                             r"(\d+(?:\.\d+){0,2})/[^/#]+\.schema\.json(?:#.*)?$")
        for text in texts:
            match = pattern.fullmatch(text)
            if match and identity(base, match.group(1)) != own:
                found.add((identity(base, match.group(1)), match.group(2)))
    return found


def resolve_line(name: str, wanted: str, versions: Iterable[str]) -> str:
    """The newest exact version on a line, or the exact version itself when one is cited."""
    if EXACT.fullmatch(wanted):
        if wanted not in list(versions):
            raise LockError(f"{name} has no version {wanted}")
        return wanted
    fits = [v for v in versions if EXACT.fullmatch(v) and line(v) == wanted]
    if not fits:
        raise LockError(f"no version of {name} on line {wanted}")
    return max(fits, key=order)


def docs_key(docs: str) -> tuple[str, int]:
    """Order of dated releases: `2026.08.24-2` is the second release of that day."""
    base, _, suffix = docs.partition("-")
    return (base, int(suffix) if suffix else 1)


def visible(entries: list[dict], as_of: str | None, tree: str | None) -> list[str]:
    """The versions of a module a lock may resolve to.

    Without a cutoff every release and the version in the tree. With one, only releases up
    to and including it, so a module released before a dependency's patch keeps its pins.
    """
    found = [e["module"] for e in entries
             if as_of is None or docs_key(e["docs"]) <= docs_key(as_of)]
    if as_of is None and tree:
        found.append(tree)
    return sorted(set(found), key=order)


def released_docs(released: dict, module: str, version: str) -> str | None:
    return next((e["docs"] for e in released.get(module, []) if e["module"] == version), None)


def sources(schemas: Iterable[dict]) -> set[str]:
    """Ontology versions named by the mappings of these schemas."""
    found = set()
    for schema in schemas:
        for synonyms in (schema.get("x-oold-context") or {}).values():
            for fragment in (synonyms or {}).values():
                if isinstance(fragment, dict):
                    version = (fragment.get("x-oold-sssom") or {}).get("object_source_version")
                    if version:
                        found.add(version)
    return found


def edition(name: str, schemas: Iterable[dict], lenient: bool = False) -> str | None:
    """The one edition a module is pinned to.

    A release made before editions were pinned pointed at `latest`, which names no edition.
    Only a backfill may record that, as None, and only when nothing is pinned at all.
    """
    editions = {edition_of(s.get("$schema")) for s in schemas}
    if lenient and editions == {None}:
        return None
    if len(editions) != 1 or None in editions:
        raise LockError(f"{name} is not pinned to one exact spec edition")
    return editions.pop()


def build(name: str, version: str, catalog: Catalog, lenient: bool = False,
          namespaces: Iterable[str] | None = None) -> dict:
    """The lock of one module version. `name` is the module's identity."""
    namespace, module = split(name)
    followed = [namespace] if namespaces is None else list(namespaces)
    own = list(catalog.schemas(name, version).values())
    pinned: dict[str, str] = {}
    closure = {name: own}
    pending = [(name, own)]
    while pending:
        current, schemas = pending.pop()
        for schema in schemas:
            for dep, wanted in sorted(dependencies(current, schema, followed)):
                if dep == name:
                    continue
                exact = resolve_line(dep, wanted, catalog.versions(dep))
                if pinned.setdefault(dep, exact) != exact:
                    raise LockError(f"{name} reaches {dep} at two versions: "
                                    f"{pinned[dep]} and {exact}")
                if dep not in closure:
                    closure[dep] = list(catalog.schemas(dep, exact).values())
                    pending.append((dep, closure[dep]))
    return {
        "lock_version": LOCK_VERSION,
        "namespace": namespace,
        "module": module,
        "version": version,
        "spec_edition": edition(name, own, lenient),
        "requires": {dep: {"version": exact} for dep, exact in sorted(pinned.items())},
        "ontologies": sorted(sources(s for group in closure.values() for s in group)),
    }


def render(lock: dict) -> str:
    ordered = {key: lock[key] for key in FIELDS if key in lock}
    return json.dumps(ordered, indent=2) + "\n"


def read_lock(lock: dict) -> dict:
    """A lock in the current shape, whichever format it was written in.

    A v1 lock has no namespace and names its dependencies by module: it was written for the
    namespace of the repository that published it, which is the one reading it here. The
    result is a view for reading `requires`, not a lock: validate the original.
    """
    if lock.get("lock_version") != 1:
        return lock
    namespace = CONFIG.namespace
    return {**lock, "namespace": namespace,
            "requires": {identity(namespace, name): {"version": pinned}
                         for name, pinned in (lock.get("requires") or {}).items()}}


def ok(value, pattern: re.Pattern) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def validate(lock: dict) -> list[str]:
    """What is wrong with a lock of either format, empty when it is well formed."""
    if not isinstance(lock, dict) or lock.get("lock_version") not in (1, LOCK_VERSION):
        return ["not a lock of a known version"]
    current = lock["lock_version"] == LOCK_VERSION
    fields = FIELDS if current else V1_FIELDS
    if set(lock) != set(fields):
        return [f"keys differ from {sorted(fields)}"]
    problems = [name for name, good in {
        "version": ok(lock["version"], EXACT), "module": ok(lock["module"], NAME),
        "spec_edition": lock["spec_edition"] is None or ok(lock["spec_edition"], EDITION),
        "namespace": not current or ok(lock["namespace"], re.compile(BASE)),
        "ontologies": isinstance(lock["ontologies"], list),
        "requires": isinstance(lock["requires"], dict),
    }.items() if not good]
    if problems:
        return [f"invalid {', '.join(problems)}"]
    for key, pin in lock["requires"].items():
        entry = pin if current else {"version": pin}
        good = (ok(key, IDENTITY if current else NAME) and isinstance(entry, dict)
                and set(entry) <= {"version", "sha256"} and ok(entry.get("version"), EXACT)
                and ("sha256" not in entry or ok(entry["sha256"], SHA256)))
        if not good:
            problems.append(f"invalid requires entry {key}")
    return problems


class Repository:
    """The working tree for the version being edited, git tags for released ones.

    It knows the modules of this repository, which live in its own namespace. A name in
    another namespace has no source here.
    """

    def __init__(self, as_of: str | None = None) -> None:
        index = ROOT / "generated" / "versions.json"
        self.released = read(index) if index.exists() else {}
        self.as_of = as_of

    def module(self, name: str) -> str:
        namespace, module = split(name)
        if namespace != CONFIG.namespace:
            raise LockError(f"{name} is outside this repository's namespace and has no "
                            "source here")
        return module

    def tree_version(self, module: str) -> str | None:
        if any((MODULES / module).glob("*.schema.json")):
            return module_version(module, full=True)
        return None

    def versions(self, name: str) -> list[str]:
        module = self.module(name)
        return visible(self.released.get(module, []), self.as_of, self.tree_version(module))

    def files(self, name: str, version: str) -> dict[str, bytes]:
        """The schema files of a module version, byte for byte as they were released."""
        module = self.module(name)
        if version == self.tree_version(module):
            return {p.name: p.read_bytes()
                    for p in sorted((MODULES / module).glob("*.schema.json"))}
        docs = next((e["docs"] for e in self.released.get(module, [])
                     if e["module"] == version), None)
        if docs is None:
            raise LockError(f"{name} {version} is neither in the tree nor released")
        tag = f"v{docs}"
        listing = level.git("ls-tree", "--name-only", tag, f"modules/{module}/") or ""
        names = [n for n in listing.split() if n.endswith(".schema.json")]
        if not names:
            raise LockError(f"{name} {version} has no schemas at {tag}")
        return {n.rsplit("/", 1)[-1]: subprocess.run(
                    ["git", "show", f"{tag}:{n}"], cwd=ROOT, check=True,
                    capture_output=True).stdout
                for n in names}

    def schemas(self, name: str, version: str) -> dict[str, dict]:
        return {n: json.loads(data) for n, data in self.files(name, version).items()}


def modules() -> list[str]:
    return sorted(d.name for d in MODULES.iterdir()
                  if d.is_dir() and any(d.glob("*.schema.json")))


def backfill(root: Path, released: dict, catalog_for: Callable[[str], Catalog]) -> list[Path]:
    """Add a lock to released versions that were published without one.

    The lock is built as of the version's own release, so it says what it would have said
    then. A version that already has a lock is left alone: a published lock is never
    rewritten. The line directory gets it too when it still holds that version.
    """
    written = []
    for module, entries in sorted(released.items()):
        for entry in entries:
            version = entry["module"]
            exact = root / module / version
            if not exact.is_dir() or (exact / FILE).exists():
                continue
            built = build(identity(CONFIG.namespace, module), version,
                          catalog_for(entry["docs"]), lenient=True)
            text = render(built)
            targets = [exact]
            alias = root / module / line(version)
            newest = resolve_line(module, line(version), [e["module"] for e in entries])
            if alias.is_dir() and not (alias / FILE).exists() and newest == version:
                targets.append(alias)
            for directory in targets:
                (directory / FILE).write_text(text, encoding="utf-8", newline="\n")
                written.append(directory / FILE)
    return written


def main() -> None:
    if "--backfill" in sys.argv:
        root = Path(sys.argv[sys.argv.index("--backfill") + 1])
        released = Repository().released
        for path in backfill(root, released, lambda docs: Repository(as_of=docs)):
            print(f"  added {path.relative_to(root)}")
        return
    check = "--check" in sys.argv
    index = Repository().released
    stale = []
    for module in modules():
        version = module_version(module, full=True)
        built = build(identity(CONFIG.namespace, module), version,
                      Repository(released_docs(index, module, version)))
        problems = validate(built)
        if problems:
            sys.exit(f"{module}: " + "; ".join(problems))
        path = OUT / module / FILE
        text = render(built)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(module)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        names = [split(dep)[1] for dep in built["requires"]]
        print(f"  {module} {built['version']} requires {names or 'nothing'}")
    if stale:
        print("stale locks, run make generate: " + ", ".join(stale), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
