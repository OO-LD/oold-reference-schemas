"""Keep every schema pinned to one exact edition of the OO-LD specification.

`latest` moves, so a schema published under an exact version would change meaning when
the spec does. The pin makes the dialect part of what an exact release freezes.

A module may move to a new edition on its own, but never mixes two: its schemas share a
context and are read together.

Usage:
  python scripts/spec_edition.py            report
  python scripts/spec_edition.py --check    fail on a floating or mixed pin
  python scripts/spec_edition.py --set X    pin every schema to edition X
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from _shared import MODULES, read

POINTER = re.compile(r"^https://oo-ld\.org/(\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)/meta/"
                     r"oold-meta-schema\.json$")
LINE = re.compile(r'("\$schema":\s*"https://oo-ld\.org/)[^/"]+(/meta/oold-meta-schema\.json")')


def edition_of(pointer: str | None) -> str | None:
    """The exact edition a `$schema` pointer names, or None if it floats or is foreign."""
    match = POINTER.match(pointer or "")
    return match.group(1) if match else None


def schemas(root: Path) -> dict[str, list[Path]]:
    return {d.name: sorted(d.glob("*.schema.json"))
            for d in sorted(root.iterdir()) if d.is_dir() and any(d.glob("*.schema.json"))}


def problems(root: Path = MODULES) -> list[str]:
    found = []
    for module, files in schemas(root).items():
        editions = {}
        for path in files:
            pointer = read(path).get("$schema")
            edition = edition_of(pointer)
            if edition is None:
                found.append(f"{module}/{path.name} is not pinned to an exact edition: {pointer}")
            else:
                editions.setdefault(edition, []).append(path.name)
        if len(editions) > 1:
            found.append(f"{module} mixes editions: " + ", ".join(sorted(editions)))
    return found


def set_edition(root: Path, edition: str) -> list[Path]:
    changed = []
    for files in schemas(root).values():
        for path in files:
            text = path.read_text(encoding="utf-8")
            new = LINE.sub(rf"\g<1>{edition}\g<2>", text, count=1)
            if new != text:
                path.write_text(new, encoding="utf-8", newline="\n")
                changed.append(path)
    return changed


def main() -> None:
    args = sys.argv[1:]
    if "--set" in args:
        for path in set_edition(MODULES, args[args.index("--set") + 1]):
            print(f"  pinned {path.relative_to(MODULES)}")
        return
    found = problems()
    for problem in found:
        print(f"  ! {problem}")
    if not found:
        print("every module is pinned to one exact edition")
    if found and "--check" in args:
        sys.exit(1)


if __name__ == "__main__":
    main()
