"""Refuse to publish over what has already been published.

Two rules, and they differ because the paths promise different things.

An exact release, `<module>/<major.minor.patch>/`, is written once. Anyone may have fetched
it, cited it or pinned it, so rewriting it would change the meaning of a citation after the
fact. Republishing identical bytes is fine; anything else is refused.

A compatibility line, `<module>/<major.minor>/`, moves, but only where movement is invisible
to an instance: a clearer description, a fixed typo. If what is about to replace it differs
at minor or major level, the line is being used to smuggle a change that deserves its own
version, and that is refused too.

Run against a checkout of the published branch, before anything is copied into it.

Usage: python scripts/check_publish.py <published-root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import level
from _shared import MODULES, module_version

ROOT = Path(__file__).resolve().parent.parent
STAGED = ROOT / "docs"


def schemas_in(directory: Path) -> dict[str, dict]:
    return {p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.schema.json"))}


def compare(published: Path, staged: Path) -> list[str]:
    """Levels of the differences between a published directory and what would replace it."""
    old, new = schemas_in(published), schemas_in(staged)
    levels = []
    for name, schema in new.items():
        if name not in old:
            levels.append(("minor", f"{name} is new"))
            continue
        result, reasons = level.compare(old[name], schema)
        if result != "none":
            levels.append((result, f"{name}: {reasons[0] if reasons else result}"))
    for name in old:
        if name not in new:
            levels.append(("major", f"{name} was removed"))
    return levels


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    published_root = Path(sys.argv[1])

    problems: list[str] = []
    for module_dir in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        module = module_dir.name
        if not any(module_dir.glob("*.schema.json")):
            continue
        exact, line = module_version(module, full=True), module_version(module)

        published = published_root / module / exact
        staged = STAGED / module / exact
        if published.is_dir() and staged.is_dir():
            changed = [name for name, schema in schemas_in(staged).items()
                       if schemas_in(published).get(name) != schema]
            if changed:
                problems.append(f"{module} {exact} is already published and would change: "
                                + ", ".join(changed)
                                + ". An exact release is written once; bump the version.")
            else:
                print(f"  ok   {module} {exact} republishes identical bytes")

        published = published_root / module / line
        staged = STAGED / module / line
        if published.is_dir() and staged.is_dir():
            levels = compare(published, staged)
            above = [reason for result, reason in levels if result in ("minor", "major")]
            if above:
                problems.append(f"{module} {line} carries changes above patch level: "
                                + "; ".join(above)
                                + ". A compatibility line only moves within itself.")
            else:
                print(f"  ok   {module} {line} moves within its compatibility line")

    for problem in problems:
        print(f"  ! {problem}")
    if problems:
        sys.exit(1)
    print("published paths are safe to write")


if __name__ == "__main__":
    main()
