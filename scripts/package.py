"""Build the offline package of a module version: a zip of unmodified documents.

The zip holds the module and every module its lock pins, laid out exactly as the host
serves them, under the exact directory and under the line directory. The line directory is
what a schema cites, so it is what a consumer reads. Nothing is rewritten, so a document
in the zip is byte for byte the one at its published path.

A consumer maps the identity IRI `https://w3id.org/oo-ld/schemas/<path>` to the member
`<path>` and validates with no network. Spec meta-schemas are not part of it: they are not
read when validating.

The build is deterministic. Timestamps and permissions are fixed and members are sorted, so
the same input gives the same bytes, and two packages are compared by their documents.

Usage:
  python scripts/package.py    write docs/packages/<module>-<version>.zip for every module
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from typing import Protocol

import lock
from _shared import ROOT, line

OUT = ROOT / "docs" / "packages"
STAMP = (1980, 1, 1, 0, 0, 0)


class Source(lock.Catalog, Protocol):
    def files(self, module: str, version: str) -> dict[str, bytes]: ...


def members(module: str, version: str, source: Source) -> dict[str, bytes]:
    """Every document of the package, by path."""
    built = lock.build(module, version, source)
    found: dict[str, bytes] = {}

    def place(name: str, pinned: str, documents: dict[str, bytes]) -> None:
        for directory in (pinned, line(pinned)):
            for file, data in documents.items():
                found[f"{name}/{directory}/{file}"] = data

    own = source.files(module, version)
    own[lock.FILE] = lock.render(built).encode("utf-8")
    place(module, version, own)
    for dep, pinned in built["requires"].items():
        place(dep, pinned, source.files(dep, pinned))
    return found


def build(module: str, version: str, source: Source) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members(module, version, source).items()):
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def read(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def same_documents(a: bytes, b: bytes) -> bool:
    """Whether two packages hold the same documents, whatever the compression."""
    return read(a) == read(b)


def main() -> None:
    repo = lock.Repository()
    OUT.mkdir(parents=True, exist_ok=True)
    for module in lock.modules():
        version = repo.tree_version(module)
        path = OUT / f"{module}-{version}.zip"
        path.write_bytes(build(module, version, repo))
        print(f"  {path.relative_to(ROOT)}: {len(read(path.read_bytes()))} documents")


if __name__ == "__main__":
    try:
        main()
    except lock.LockError as error:
        sys.exit(str(error))
