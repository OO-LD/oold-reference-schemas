"""Every value alias needs a stable, code-safe name.

An `enum` on a term coerced with `@vocab` lists vocabulary entries, not free text: the
enum value is the vocabulary's local name (`SEC`, `PERCENT`) and the generated binding
needs a name that is legal in a language. There is no standardised representation that is
both canonical and ASCII for arbitrary units, so the name is written out, once, next to the
enum: same length, same order, unique, and a valid identifier.

Usage: python scripts/check_enums.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _shared import MODULES, context_of, read

NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def chain(schema_file: Path) -> list[Path]:
    """A schema and everything it extends, base first."""
    out: list[Path] = []

    def walk(f: Path) -> None:
        if not f.is_file() or f in out:
            return
        for ref in (read(f).get("allOf") or []):
            if isinstance(ref, dict) and isinstance(ref.get("$ref"), str):
                walk(f.parent / ref["$ref"])
        out.append(f)

    walk(schema_file)
    return out


def coercion(context: dict, term: str) -> str | None:
    definition = context.get(term)
    return definition.get("@type") if isinstance(definition, dict) else None


def enums(node, context: dict, path: str = "") -> list[tuple[str, str, dict]]:
    """Every property subschema carrying an enum, with the term it belongs to."""
    found = []
    if isinstance(node, dict):
        for term, spec in (node.get("properties") or {}).items():
            if isinstance(spec, dict) and isinstance(spec.get("enum"), list):
                found.append((term, f"{path}/properties/{term}", spec))
        for key in ("properties", "$defs", "items", "allOf", "anyOf", "oneOf"):
            child = node.get(key)
            if isinstance(child, dict):
                for name, value in child.items():
                    found += enums(value, context, f"{path}/{key}/{name}")
            elif isinstance(child, list):
                for index, value in enumerate(child):
                    found += enums(value, context, f"{path}/{key}/{index}")
    return found


def check(schema_file: Path) -> tuple[list[str], int]:
    lineage = chain(schema_file)
    context: dict = {}
    for f in lineage:
        context.update(context_of(read(f)))

    problems, seen = [], 0
    schema = read(schema_file)
    for term, path, spec in enums(schema, context):
        # only value aliases: a plain enum is data, and needs no name
        if coercion(context, term) != "@vocab":
            continue
        seen += 1
        members = spec["enum"]
        names = spec.get("x-enum-varnames")
        if names is None:
            # the value may already be the name, which is the normalised unit case
            unnamed = [m for m in members if not (isinstance(m, str) and NAME.match(m))]
            if unnamed:
                problems.append(f"{path}: {unnamed} are not identifiers and have no "
                                f"x-enum-varnames")
            continue
        if len(names) != len(members):
            problems.append(f"{path}: {len(names)} names for {len(members)} enum members")
        if len(set(names)) != len(names):
            problems.append(f"{path}: x-enum-varnames are not unique")
        for name in names:
            if not isinstance(name, str) or not NAME.match(name):
                problems.append(f"{path}: {name!r} is not a lower case ASCII identifier")
    return problems, seen


def main() -> None:
    problems, checked = [], 0
    for module in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        for schema_file in sorted(module.glob("*.schema.json")):
            found, seen = check(schema_file)
            checked += seen
            for problem in found:
                problems.append(f"{module.name}/{schema_file.name} {problem}")
    for problem in problems:
        print(f"  ! {problem}")
    print(f"enums: {checked} value aliases checked, "
          f"{'ok' if not problems else str(len(problems)) + ' problems'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
