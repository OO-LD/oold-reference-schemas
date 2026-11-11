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
from spec_edition import edition_of

LOCK_VERSION = 1
OUT = ROOT / "generated" / "locks"
FILE = "oold.lock.json"

DEPENDENCY = re.compile(r"^https://w3id\.org/oo-ld/schemas/([a-z0-9_-]+)/(\d+(?:\.\d+)?)/"
                        r"[^/#]+\.schema\.json")
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
FIELDS = ("lock_version", "module", "version", "spec_edition", "requires", "ontologies")
KEYS = set(FIELDS)


class LockError(Exception):
    """A closure that cannot be pinned."""


class Catalog(Protocol):
    def versions(self, module: str) -> list[str]: ...
    def schemas(self, module: str, version: str) -> dict[str, dict]: ...


def order(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def strings(node, key: str) -> Iterable[str]:
    """Every string under `key`, at any depth, whether given alone or in a list."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, str):
                        yield item
            yield from strings(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value, key)


def dependencies(module: str, schema: dict) -> set[tuple[str, str]]:
    """The (module, line) pairs a schema reaches by `$ref` or `@context`."""
    found = set()
    for text in (*strings(schema, "$ref"), *strings(schema, "@context")):
        match = DEPENDENCY.match(text)
        if match and match.group(1) != module:
            found.add((match.group(1), match.group(2)))
    return found


def resolve_line(module: str, wanted: str, versions: Iterable[str]) -> str:
    """The newest exact version on a line."""
    fits = [v for v in versions if EXACT.match(v) and line(v) == wanted]
    if not fits:
        raise LockError(f"no version of {module} on line {wanted}")
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


def edition(module: str, schemas: Iterable[dict], lenient: bool = False) -> str | None:
    """The one edition a module is pinned to.

    A release made before editions were pinned pointed at `latest`, which names no edition.
    Only a backfill may record that, as None, and only when nothing is pinned at all.
    """
    editions = {edition_of(s.get("$schema")) for s in schemas}
    if lenient and editions == {None}:
        return None
    if len(editions) != 1 or None in editions:
        raise LockError(f"{module} is not pinned to one exact spec edition")
    return editions.pop()


def build(module: str, version: str, catalog: Catalog, lenient: bool = False) -> dict:
    """The lock of one module version."""
    own = list(catalog.schemas(module, version).values())
    pinned: dict[str, str] = {}
    closure = {module: own}
    pending = [(module, own)]
    while pending:
        current, schemas = pending.pop()
        for schema in schemas:
            for dep, wanted in sorted(dependencies(current, schema)):
                if dep == module:
                    continue
                exact = resolve_line(dep, wanted, catalog.versions(dep))
                if pinned.setdefault(dep, exact) != exact:
                    raise LockError(f"{module} reaches {dep} on two lines: "
                                    f"{pinned[dep]} and {exact}")
                if dep not in closure:
                    closure[dep] = list(catalog.schemas(dep, exact).values())
                    pending.append((dep, closure[dep]))
    return {
        "lock_version": LOCK_VERSION,
        "module": module,
        "version": version,
        "spec_edition": edition(module, own, lenient),
        "requires": dict(sorted(pinned.items())),
        "ontologies": sorted(sources(s for group in closure.values() for s in group)),
    }


def render(lock: dict) -> str:
    ordered = {key: lock[key] for key in FIELDS if key in lock}
    return json.dumps(ordered, indent=2) + "\n"


def validate(lock: dict) -> list[str]:
    """Structural problems of a lock, empty when it is well formed."""
    problems = []
    if set(lock) != KEYS:
        problems.append(f"keys differ from {sorted(KEYS)}: {sorted(set(lock) ^ KEYS)}")
        return problems
    if lock["lock_version"] != LOCK_VERSION:
        problems.append(f"unknown lock_version {lock['lock_version']}")
    if not isinstance(lock["version"], str) or not EXACT.match(lock["version"]):
        problems.append(f"version is not an exact version: {lock['version']!r}")
    if lock["spec_edition"] is not None and (
            not isinstance(lock["spec_edition"], str)
            or not re.match(r"^\d+\.\d+\.\d+", lock["spec_edition"])):
        problems.append(f"spec_edition is not an exact version: {lock['spec_edition']!r}")
    for name, pinned in (lock["requires"] or {}).items():
        if not EXACT.match(str(pinned)):
            problems.append(f"requires {name} is not an exact version: {pinned!r}")
    if not isinstance(lock["ontologies"], list):
        problems.append("ontologies is not a list")
    return problems


class Repository:
    """The working tree for the version being edited, git tags for released ones."""

    def __init__(self, as_of: str | None = None) -> None:
        index = ROOT / "generated" / "versions.json"
        self.released = read(index) if index.exists() else {}
        self.as_of = as_of

    def tree_version(self, module: str) -> str | None:
        if any((MODULES / module).glob("*.schema.json")):
            return module_version(module, full=True)
        return None

    def versions(self, module: str) -> list[str]:
        return visible(self.released.get(module, []), self.as_of, self.tree_version(module))

    def files(self, module: str, version: str) -> dict[str, bytes]:
        """The schema files of a module version, byte for byte as they were released."""
        if version == self.tree_version(module):
            return {p.name: p.read_bytes()
                    for p in sorted((MODULES / module).glob("*.schema.json"))}
        docs = next((e["docs"] for e in self.released.get(module, [])
                     if e["module"] == version), None)
        if docs is None:
            raise LockError(f"{module} {version} is neither in the tree nor released")
        tag = f"v{docs}"
        listing = level.git("ls-tree", "--name-only", tag, f"modules/{module}/") or ""
        names = [n for n in listing.split() if n.endswith(".schema.json")]
        if not names:
            raise LockError(f"{module} {version} has no schemas at {tag}")
        return {n.rsplit("/", 1)[-1]: subprocess.run(
                    ["git", "show", f"{tag}:{n}"], cwd=ROOT, check=True,
                    capture_output=True).stdout
                for n in names}

    def schemas(self, module: str, version: str) -> dict[str, dict]:
        return {name: json.loads(data) for name, data in self.files(module, version).items()}


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
            text = render(build(module, version, catalog_for(entry["docs"]), lenient=True))
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
        built = build(module, version, Repository(released_docs(index, module, version)))
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
        print(f"  {module} {built['version']} requires {built['requires'] or 'nothing'}")
    if stale:
        print("stale locks, run make generate: " + ", ".join(stale), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
