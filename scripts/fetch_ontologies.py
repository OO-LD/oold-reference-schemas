"""Fetch the pinned ontology files named in ontologies.lock.json and verify them.

The ontologies are not carried in this repository: they are large, they belong to other
projects, and nothing in the documentation build reads them, because the labels they supply
are committed. They are needed to refresh those labels or to re-check a mapping.

What is carried instead is the pin: version, repository, ref and a SHA-256 per file. That
turns a silent problem into a loud one. A published build that lags its own branch, a moved
tag, a file edited in place: each shows up here as a hash mismatch rather than as a mapping
that quietly means something else. The EMMO pin names a commit for exactly that reason.

Maintaining the lock. Pin a versioned artefact, never a "latest" URL: a moving target makes
every upstream release look like tampering and trains everyone to ignore the check. Add an
ontology by writing its entry with the version, repository, ref, base URL, licence and the
files needed, then run --update to fill in the hashes. Change a pin the same way: edit the
ref, run --update, re-check the mappings that target it, and record the new
object_source_version on each synonym.

Usage:
  python scripts/fetch_ontologies.py           download what is missing, verify everything
  python scripts/fetch_ontologies.py --check   verify what is present, download nothing
  python scripts/fetch_ontologies.py --update  refetch and rewrite the hashes in the lock
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "ontologies.lock.json"
TARGET = ROOT / ".ontologies"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, attempts: int = 4) -> bytes:
    """Fetch a file, retrying with backoff while a host rate-limits."""
    # some publishers refuse a request without a user agent, and an ontology that cannot be
    # fetched cannot be pinned
    request = urllib.request.Request(
        url, headers={"User-Agent": "oold-reference-schemas", "Accept": "text/turtle, */*"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == attempts - 1:
                raise
            wait = 5 * 2 ** attempt
            print(f"  {error.code} for {url}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(url)


def update(lock: dict) -> None:
    """Refetch every file in the lock and write back its hash and size.

    Deliberate, never automatic: it reports what moved, and a maintainer decides whether
    the mappings still hold before the new hash is committed.
    """
    for name, entry in sorted(lock.items()):
        for relative, spec in sorted(entry["files"].items()):
            url = entry["base"] + spec["path"]
            data = fetch(url)
            new = digest(data)
            state = "unchanged" if new == spec.get("sha256") else "CHANGED"
            print(f"  {name}/{relative}: {len(data) / 1024 / 1024:.1f} MB, {state}")
            spec["sha256"], spec["bytes"] = new, len(data)
    LOCK.write_text(json.dumps(dict(sorted(lock.items())), indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def prune(lock: dict, check: bool) -> tuple[int, list[str]]:
    """Drop a snapshot the lock no longer pins.

    The cache is read as a whole, by the label extractor among others, so a version left
    behind by a repin keeps answering for terms the lock no longer describes, and the older
    label silently wins wherever it sorts first.
    """
    problems, removed = [], 0
    for directory in sorted(TARGET.glob("*/*")):
        if not directory.is_dir():
            continue
        if lock.get(directory.parent.name, {}).get("version") == directory.name:
            continue
        if check:
            problems.append(f"{directory.relative_to(ROOT)} is not pinned by the lock")
            continue
        shutil.rmtree(directory)
        if not any(directory.parent.iterdir()):
            directory.parent.rmdir()
        removed += 1
    return removed, problems


def main() -> None:
    check = "--check" in sys.argv
    if not LOCK.exists():
        sys.exit(f"{LOCK.name} not found")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if "--update" in sys.argv:
        update(lock)
        return

    problems: list[str] = []
    fetched = verified = 0
    for name, entry in sorted(lock.items()):
        for relative, spec in sorted(entry["files"].items()):
            local = TARGET / name / entry["version"] / relative
            if local.exists():
                if digest(local.read_bytes()) == spec["sha256"]:
                    verified += 1
                else:
                    problems.append(f"{local.relative_to(ROOT)} does not match the lock")
                continue
            if check:
                problems.append(f"{local.relative_to(ROOT)} is missing")
                continue

            url = entry["base"] + spec["path"]
            data = fetch(url)
            if digest(data) != spec["sha256"]:
                problems.append(f"{url} does not match the lock: upstream has changed under "
                                f"the pin, so the mappings need re-checking before the lock "
                                f"is updated")
                continue
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
            fetched += 1

    removed, unpinned = prune(lock, check)
    problems += unpinned

    print(f"ontologies: {fetched} fetched, {verified} verified, "
          f"{removed} stale removed, in {TARGET.name}/")
    for problem in problems:
        print(f"  ! {problem}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
