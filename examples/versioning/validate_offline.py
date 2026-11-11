# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema", "referencing"]
# ///
"""Validate an instance against an offline package, with no network.

    uv run validate_offline.py materials-0.2.0.zip my-material.json

The instance names its schema in `$schema`. That can be an identity IRI, for example
https://w3id.org/oo-ld/schemas/materials/0.2/Material.schema.json, or a bare file name,
which is read from the module the package is named after. Pass --schema to override it.

The one rule: the IRI minus https://w3id.org/oo-ld/schemas/ is a member of the zip. The
registry below has no other way to fetch a document, so a missing one is an error and
never a request.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

BASE = "https://w3id.org/oo-ld/schemas/"


def validate(package: Path, instance: Path, schema: str | None = None) -> list[str]:
    """The problems of an instance, empty when it is valid."""
    archive = zipfile.ZipFile(package)
    members = set(archive.namelist())

    def retrieve(iri: str) -> Resource:
        member = iri[len(BASE):] if iri.startswith(BASE) else ""
        if member not in members:
            raise LookupError(f"not in the package: {iri}")
        return Resource.from_contents(json.loads(archive.read(member)),
                                      default_specification=DRAFT202012)

    data = json.loads(instance.read_text(encoding="utf-8"))
    iri = schema or data["$schema"]
    if not iri.startswith(BASE):
        module, _, version = package.stem.rpartition("-")
        iri = f"{BASE}{module}/{version}/{iri}"
    validator = Draft202012Validator({"$ref": iri}, registry=Registry(retrieve=retrieve))
    try:
        return [error.message[:160] for error in validator.iter_errors(data)]
    except Unresolvable as missing:
        return [f"not in the package: {missing.ref}"]


def main(argv: list[str]) -> int:
    schema = argv[argv.index("--schema") + 1] if "--schema" in argv else None
    paths = [a for i, a in enumerate(argv) if not a.startswith("--") and
             (i == 0 or argv[i - 1] != "--schema")]
    if len(paths) != 2:
        print(__doc__)
        return 2
    problems = validate(Path(paths[0]), Path(paths[1]), schema)
    for problem in problems:
        print(f"  ! {problem}")
    print("valid" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
