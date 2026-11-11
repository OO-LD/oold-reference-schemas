"""Validate each module's instances using only its offline package.

The validation is the example consumers copy, `examples/versioning/validate_offline.py`, so
CI exercises the same recipe the guide teaches. It reads every schema from the zip and has
no other way to fetch one, so a document the package lacks is an error rather than a
network request. That is what makes the package a proof of offline use and not just a copy.

Usage:
  uv run --with jsonschema --with referencing scripts/check_package.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples" / "versioning"))

from validate_offline import validate  # noqa: E402


def main() -> None:
    failures = []
    checked = 0
    for package in sorted((ROOT / "docs" / "packages").glob("*.zip")):
        module = package.stem.rpartition("-")[0]
        for instance in sorted((ROOT / "modules" / module).glob("*.instance.json")):
            problems = validate(package, instance)
            checked += 1
            print(f"  {'ok  ' if not problems else 'FAIL'} {package.name} {instance.name}")
            failures += [f"{instance.name}: {problem}" for problem in problems]
    for failure in failures:
        print(f"  ! {failure}")
    if not checked:
        sys.exit("no package or instance found: run make generate first")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
