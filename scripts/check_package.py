"""Validate each module's instances using only its offline package.

A plain JSON Schema validator reads every schema from the zip and is given no other way to
fetch one, so a document the package lacks is an error rather than a network request. That
is what makes the package a proof of offline use and not just a copy.

Usage:
  uv run --with jsonschema --with referencing scripts/check_package.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://w3id.org/oo-ld/schemas/"


def validate(package: Path, module: str, version: str, instance: Path) -> list[str]:
    archive = zipfile.ZipFile(package)
    names = set(archive.namelist())

    def retrieve(uri: str) -> Resource:
        member = uri[len(BASE):] if uri.startswith(BASE) else ""
        if member not in names:
            raise LookupError(f"not in the package: {uri}")
        return Resource.from_contents(json.loads(archive.read(member)),
                                      default_specification=DRAFT202012)

    data = json.loads(instance.read_text(encoding="utf-8"))
    schema = f"{BASE}{module}/{version}/{data['$schema']}"
    validator = Draft202012Validator({"$ref": schema}, registry=Registry(retrieve=retrieve))
    return [f"{instance.name}: {error.message[:160]}" for error in validator.iter_errors(data)]


def main() -> None:
    failures = []
    checked = 0
    for package in sorted((ROOT / "docs" / "packages").glob("*.zip")):
        module, _, version = package.stem.rpartition("-")
        for instance in sorted((ROOT / "modules" / module).glob("*.instance.json")):
            problems = validate(package, module, version, instance)
            checked += 1
            print(f"  {'ok  ' if not problems else 'FAIL'} {package.name} {instance.name}")
            failures += problems
    for failure in failures:
        print(f"  ! {failure}")
    if not checked:
        sys.exit("no package or instance found: run make generate first")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
