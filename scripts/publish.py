"""Prepare a release and publish it from its record, so an interrupted release can be finished.

`prepare` lists what a release consists of, with digests, before anything is tagged or
uploaded. `publish` reads only that record: no bump is calculated again, a file that is already
in place with the recorded content is accepted, and a fixed path holding other content is
refused. The line directory moves last, so a half finished release never points the line at
documents whose exact path is missing.

Usage:
  python scripts/publish.py prepare MODULE          write dist/<module>-<version>.release.json
  python scripts/publish.py publish RECORD TARGET   copy the release under TARGET, safely
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from _shared import ROOT, line, module_version

STAGED = ROOT / "docs"
DIST = ROOT / "dist"


class PublishError(Exception):
    """A release that cannot be published as recorded."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def listing(staged: Path, directory: Path) -> dict[str, str]:
    return {p.relative_to(staged).as_posix(): digest(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def prepare(module: str, version: str, staged: Path = STAGED) -> dict:
    """The files of a release: fixed ones are written once, the line moves with each release."""
    package = staged / "packages" / f"{module}-{version}.zip"
    if not package.is_file():
        raise PublishError(f"no package for {module} {version}: run make generate first")
    return {"module": module, "version": version,
            "fixed": {**listing(staged, staged / module / version),
                      package.relative_to(staged).as_posix(): digest(package)},
            "moving": listing(staged, staged / module / line(version))}


def publish(record: dict, staged: Path, target: Path) -> list[str]:
    """Write the release under `target`, returning what was written."""
    files = [(rel, want, True) for rel, want in sorted(record["fixed"].items())]
    files += [(rel, want, False) for rel, want in sorted(record["moving"].items())]
    for rel, want, _ in files:
        if not (staged / rel).is_file() or digest(staged / rel) != want:
            raise PublishError(f"{rel} changed since the release was prepared")
    written = []
    for rel, want, fixed in files:
        dest = target / rel
        if dest.is_file() and digest(dest) == want:
            continue
        if fixed and dest.exists():
            raise PublishError(f"{rel} is already published with different content")
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        shutil.copyfile(staged / rel, part)
        os.replace(part, dest)
        written.append(rel)
    return written


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["prepare"] and len(argv) == 2:
            record = prepare(argv[1], module_version(argv[1], full=True))
            DIST.mkdir(exist_ok=True)
            path = DIST / f"{record['module']}-{record['version']}.release.json"
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            count = len(record["fixed"]) + len(record["moving"])
            print(f"  {path.relative_to(ROOT)}: {count} files")
            return 0
        if argv[:1] == ["publish"] and len(argv) == 3:
            record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
            written = publish(record, STAGED, Path(argv[2]))
            print(f"  wrote {len(written)} file(s), the rest was already in place")
            return 0
    except PublishError as error:
        sys.exit(str(error))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
