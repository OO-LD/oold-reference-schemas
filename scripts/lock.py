"""Write oold.lock.json: the exact versions a module version was released against.

A schema cites its dependencies by compatibility line (`quantities/0.2/`), which keeps
patches flowing. The line says which versions may be used, not which one was. The lock
records the exact version each line resolved to, transitively, plus the spec edition and
the ontology versions the mappings were checked against.

Plain JSON Schema validators ignore it. It serves the offline package, the release checks
and any tool that wants a reproducible closure.

Usage:
  python scripts/lock.py            write generated/locks/<module>/oold.lock.json
  python scripts/lock.py --check    fail if a committed lock is stale
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
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


def edition(module: str, schemas: Iterable[dict]) -> str:
    editions = {edition_of(s.get("$schema")) for s in schemas}
    if len(editions) != 1 or None in editions:
        raise LockError(f"{module} is not pinned to one exact spec edition")
    return editions.pop()


def build(module: str, version: str, catalog: Catalog) -> dict:
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
        "spec_edition": edition(module, own),
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
    for key in ("version", "spec_edition"):
        if not isinstance(lock[key], str) or not re.match(r"^\d+\.\d+\.\d+", lock[key]):
            problems.append(f"{key} is not an exact version: {lock[key]!r}")
    for name, pinned in (lock["requires"] or {}).items():
        if not EXACT.match(str(pinned)):
            problems.append(f"requires {name} is not an exact version: {pinned!r}")
    if not isinstance(lock["ontologies"], list):
        problems.append("ontologies is not a list")
    return problems


class Repository:
    """The working tree for the version being edited, git tags for released ones."""

    def __init__(self) -> None:
        index = ROOT / "generated" / "versions.json"
        self.released = read(index) if index.exists() else {}

    def tree_version(self, module: str) -> str | None:
        if any((MODULES / module).glob("*.schema.json")):
            return module_version(module, full=True)
        return None

    def versions(self, module: str) -> list[str]:
        found = {entry["module"] for entry in self.released.get(module, [])}
        current = self.tree_version(module)
        return sorted(found | ({current} if current else set()), key=order)

    def schemas(self, module: str, version: str) -> dict[str, dict]:
        if version == self.tree_version(module):
            return {p.name: read(p) for p in sorted((MODULES / module).glob("*.schema.json"))}
        docs = next((e["docs"] for e in self.released.get(module, [])
                     if e["module"] == version), None)
        if docs is None:
            raise LockError(f"{module} {version} is neither in the tree nor released")
        tag = f"v{docs}"
        listing = level.git("ls-tree", "--name-only", tag, f"modules/{module}/") or ""
        names = [n for n in listing.split() if n.endswith(".schema.json")]
        if not names:
            raise LockError(f"{module} {version} has no schemas at {tag}")
        return {n.rsplit("/", 1)[-1]: json.loads(level.git("show", f"{tag}:{n}") or "{}")
                for n in names}


def modules() -> list[str]:
    return sorted(d.name for d in MODULES.iterdir()
                  if d.is_dir() and any(d.glob("*.schema.json")))


def main() -> None:
    check = "--check" in sys.argv
    repo = Repository()
    stale = []
    for module in modules():
        built = build(module, module_version(module, full=True), repo)
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
