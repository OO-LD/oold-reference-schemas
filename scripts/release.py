"""Cut a release: stamp the date, freeze the module versions, record what documented what.

The repository is released by date because it aggregates modules that version
independently, and one semver level cannot describe eleven of them at once. Modules and
schemas keep semver, where the level is a promise about compatibility that
`scripts/level.py` can check.

The link between the two lines is the only thing that cannot be recomputed later: once
`quantities` moves to 0.2.0, nothing in the repository still says which dated release
documented 0.1.0. So it is written down here, at the moment it is known, and the catalog
pages read it back.

Usage:
  python scripts/release.py               cut a release dated today
  python scripts/release.py --date D      cut a release dated D (YYYY-MM-DD)
  python scripts/release.py --check       verify the recorded versions match the modules
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import level

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
VERSION = ROOT / "VERSION"
INDEX = ROOT / "generated" / "versions.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def stamp(date: str, taken: set[str]) -> str:
    """A release name for a date, suffixed only when the day already has one."""
    base = date.replace("-", ".")
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def modules() -> list[str]:
    return sorted(d.name for d in MODULES.iterdir()
                  if d.is_dir() and any(d.glob("*.schema.json")))


def main() -> None:
    args = sys.argv[1:]
    index = read(INDEX)
    check = "--check" in args

    if check:
        problems = []
        for module in modules():
            declared = read(MODULES / module / "module.json").get("version")
            recorded = [entry["module"] for entry in index.get(module, [])]
            if declared and recorded and declared not in recorded:
                problems.append(f"{module} is at {declared}, which no release recorded")
        for problem in problems:
            print(f"  ! {problem}")
        sys.exit(1 if problems else 0)

    date = args[args.index("--date") + 1] if "--date" in args else \
        datetime.date.today().isoformat()
    taken = {entry["docs"] for entries in index.values() for entry in entries}
    release = stamp(date, taken)

    ref = level.baseline_ref(None)
    for module in modules():
        if ref:
            report = level.module_report(module, ref)
            for line in level.apply(module, report):
                print(f"  {module}: {line}")
        version = read(MODULES / module / "module.json").get("version")
        if not version:
            continue
        entries = index.setdefault(module, [])
        if not any(entry["module"] == version for entry in entries):
            entries.append({"module": version, "docs": release})
            print(f"  {module} {version} documented in {release}")

    VERSION.write_text(release + "\n", encoding="utf-8", newline="\n")
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"release {release}")
    print(f"next: make generate, commit, then tag v{release}")


if __name__ == "__main__":
    main()
