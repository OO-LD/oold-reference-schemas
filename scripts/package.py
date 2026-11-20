"""Build the offline package of a module version: a zip of unmodified documents.

The zip holds the module and every module its lock pins, under the exact directory and
under the line directory. The line directory is what a schema cites, so it is what a
consumer reads. Nothing is rewritten, so a document in the zip is byte for byte the one at
its published path.

A member is named by the IRI of its document without the scheme, so
`<host>/<namespace path>/<module>/<line>/<file>`. Two namespaces may both hold a module of
the same name and still sit side by side. A consumer maps an IRI to a member by dropping
`https://`, and validates with no network. Spec meta-schemas are not part of it: they are
not read when validating.

The build is deterministic. Timestamps and permissions are fixed and members are sorted, so
the same input gives the same bytes, and two packages are compared by their documents.

Usage:
  python scripts/package.py    write docs/packages/<module>-<version>.zip for every module
"""

from __future__ import annotations

import io
import sys
import zipfile
from collections.abc import Iterable
from typing import Protocol

import lock
import pins
from _shared import ROOT, line
from config import CONFIG

OUT = ROOT / "docs" / "packages"
STAMP = (1980, 1, 1, 0, 0, 0)


class Source(lock.Catalog, Protocol):
    def files(self, identity: str, version: str) -> dict[str, bytes]: ...


def members(name: str, version: str, source: Source,
            namespaces: Iterable[str] | None = None) -> dict[str, bytes]:
    """Every document of the package, by path. `name` is the module's identity."""
    built = lock.build(name, version, source, namespaces=namespaces)
    found: dict[str, bytes] = {}

    def place(identity: str, pinned: str, documents: dict[str, bytes]) -> None:
        for directory in (pinned, line(pinned)):
            for file, data in documents.items():
                found[f"{identity.removeprefix('https://')}/{directory}/{file}"] = data

    own = source.files(name, version)
    own[lock.FILE] = lock.render(built).encode("utf-8")
    place(name, version, own)
    for dep, entry in built["requires"].items():
        place(dep, entry["version"], source.files(dep, entry["version"]))
    return found


def build(name: str, version: str, source: Source,
          namespaces: Iterable[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for member, data in sorted(members(name, version, source, namespaces).items()):
            info = zipfile.ZipInfo(member, STAMP)
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
    index = lock.Repository()
    pinned = pins.Pinned(CONFIG.dependencies)
    OUT.mkdir(parents=True, exist_ok=True)
    for module in lock.modules():
        version = index.tree_version(module)
        catalog = pins.Combined(lock.Repository(lock.released_docs(index.released, module,
                                                                   version)), pinned)
        path = OUT / f"{module}-{version}.zip"
        path.write_bytes(build(lock.identity(CONFIG.namespace, module), version, catalog,
                               catalog.namespaces))
        print(f"  {path.relative_to(ROOT)}: {len(read(path.read_bytes()))} documents")


if __name__ == "__main__":
    try:
        main()
    except lock.LockError as error:
        sys.exit(str(error))
