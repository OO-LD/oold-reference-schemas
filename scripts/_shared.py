"""Helpers every generator needs, defined once.

Reading a module's version, merging a context and shortening a mapping set identifier are
each one line, which is exactly why they were copied into three scripts and then diverged:
one read the version from module.json and another from a member schema, so a bumped module
would have published its files at one path and advertised another.

macros.py deliberately keeps its own copies: it is written to move into the OO-LD core
unchanged, and importing repository-local helpers would tie it here.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def set_name(iri: str) -> str:
    """Short name of a mapping set, from its identifier."""
    return iri.rstrip("/").rsplit("/", 1)[-1].removesuffix(".sssom.tsv")


def module_version(module: str, full: bool = False) -> str:
    """The version a module publishes under.

    From module.json, which is the module's own statement about itself. A member schema's
    x-oold-version says when that schema last changed, which is a different question.
    """
    path = MODULES / module / "module.json"
    version = read(path).get("version", "0.1.0") if path.exists() else "0.1.0"
    return version if full else ".".join(version.split(".")[:2])


def context_of(schema: dict) -> dict:
    """The inline term definitions of a schema, with a list `@context` merged in order."""
    ctx = schema.get("@context")
    if isinstance(ctx, list):
        merged: dict = {}
        for part in ctx:
            if isinstance(part, dict):
                merged.update(part)
        return merged
    return ctx if isinstance(ctx, dict) else {}


def mapping_sets(schemas: list[dict]) -> list[str]:
    """Every mapping set the given schemas declare a synonym in.

    Taken over all of them, not just the most derived one: a subschema inherits the
    mappings of what it extends, so a reading exists for a set it never mentions itself.
    """
    found = set()
    for schema in schemas:
        for synonyms in (schema.get("x-oold-context") or {}).values():
            for fragment in (synonyms or {}).values():
                if isinstance(fragment, dict):
                    set_id = (fragment.get("x-oold-sssom") or {}).get("mapping_set_id")
                    if set_id:
                        found.add(set_id)
    return sorted(found)
