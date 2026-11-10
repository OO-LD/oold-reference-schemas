"""Refuse to publish over what has already been published.

Rules, and they differ because the paths promise different things.

An exact release, `<module>/<major.minor.patch>/`, is written once. Anyone may have fetched
it, cited it or pinned it, so rewriting it would change the meaning of a citation after the
fact. Republishing identical bytes is fine; anything else is refused. Its lock follows the
same rule, except that a release published before locks existed may gain one.

The line is `major.minor` below 1.0 and `major` from 1.0 on (see `_shared.line`).

A compatibility line, `<module>/<line>/`, moves, but only within what its name promises.
Below 1.0 a break and an addition both raise the minor, so the line takes patches only: a
clearer description, a fixed typo. From 1.0 the line is the major, so additions must reach
it and only a break is refused. Either way, a change the line does not allow is being
smuggled in and deserves its own version.

A lock may only pin versions that exist, either already published or published by the same
release. The package of an exact release is written once, judged by its documents rather
than its bytes, since compression may differ between machines.

Run against a checkout of the published branch, before anything is copied into it.

Usage: python scripts/check_publish.py <published-root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import level
import package
from _shared import MODULES, module_version

ROOT = Path(__file__).resolve().parent.parent
STAGED = ROOT / "docs"
LOCK = "oold.lock.json"


def schemas_in(directory: Path) -> dict[str, dict]:
    return {p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.schema.json"))}


def compare(published: Path, staged: Path) -> list[tuple[str, str]]:
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


def refused(line: str) -> set[str]:
    """The levels a compatibility line may not carry."""
    return {"major"} if "." not in line else {"minor", "major"}


def line_problems(module: str, line: str, published: Path, staged: Path) -> list[str]:
    above = [reason for result, reason in compare(published, staged) if result in refused(line)]
    if not above:
        return []
    return [f"{module} {line} carries changes it does not allow: " + "; ".join(above)
            + ". A compatibility line only moves within itself."]


def lock_problems(module: str, exact: str, published_root: Path,
                  staged_root: Path) -> list[str]:
    """A published lock is written once, and a lock only pins versions that exist."""
    problems = []
    staged = staged_root / module / exact / LOCK
    published = published_root / module / exact / LOCK
    if not staged.is_file():
        return problems
    if published.is_file() and published.read_bytes() != staged.read_bytes():
        problems.append(f"{module} {exact} is already published with a different {LOCK}. "
                        "An exact release is written once; bump the version.")
    for dep, version in json.loads(staged.read_text(encoding="utf-8"))["requires"].items():
        if not ((published_root / dep / version).is_dir()
                or (staged_root / dep / version).is_dir()):
            problems.append(f"{module} {exact} requires {dep} {version}, "
                            "which is neither published nor part of this release.")
    return problems


def package_problems(module: str, exact: str, published_root: Path,
                     staged_root: Path) -> list[str]:
    """A published package is written once."""
    name = Path("packages") / f"{module}-{exact}.zip"
    published, staged = published_root / name, staged_root / name
    if not (published.is_file() and staged.is_file()):
        return []
    if package.same_documents(published.read_bytes(), staged.read_bytes()):
        return []
    return [f"{name} is already published with different documents. "
            "An exact release is written once; bump the version."]


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

        found = lock_problems(module, exact, published_root, STAGED)
        problems += found
        if not found and (STAGED / module / exact / LOCK).is_file():
            print(f"  ok   {module} {exact} lock pins versions that exist")

        found = package_problems(module, exact, published_root, STAGED)
        problems += found
        if not found and (STAGED / "packages" / f"{module}-{exact}.zip").is_file():
            print(f"  ok   {module} {exact} package holds the documents it did")

        published = published_root / module / line
        staged = STAGED / module / line
        if published.is_dir() and staged.is_dir():
            found = line_problems(module, line, published, staged)
            problems += found
            if not found:
                print(f"  ok   {module} {line} moves within its compatibility line")

    for problem in problems:
        print(f"  ! {problem}")
    if problems:
        sys.exit(1)
    print("published paths are safe to write")


if __name__ == "__main__":
    main()
