"""The version the commits since the last release imply, checked against what the schemas need.

semantic-release writes a release version from commit messages. level.py works out the lowest
version the schema changes allow, from the diff. A `fix:` on a change that breaks documents
would release a patch the diff forbids, so this fails it on the pull request, before anyone
merges. On the release candidate `level.py --check` makes the same comparison against the
version that was actually written.

Usage: python scripts/bump.py --check [--baseline REF]
"""

from __future__ import annotations

import re
import subprocess
import sys

import level
from _shared import MODULES, ROOT, read

HEADER = re.compile(r"(?P<type>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:")
BREAKING = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)
RELEASES = {"feat": "minor", "fix": "patch", "perf": "patch"}


def commit_level(message: str) -> str | None:
    """The level a Conventional Commit message releases, None if it releases nothing."""
    match = HEADER.match(message.strip().splitlines()[0]) if message.strip() else None
    if not match:
        return None
    if match["bang"] or BREAKING.search(message):
        return "major"
    return RELEASES.get(match["type"])


def implied(messages: list[str]) -> str | None:
    levels = [lv for lv in map(commit_level, messages) if lv]
    return max(levels, key=level.LEVELS.index) if levels else None


def predicted(version: str, messages: list[str]) -> str:
    """The version semantic-release would write: below 1.0 a break raises the minor."""
    return level.raise_to(version, implied(messages))


def problems(module: str, version: str, messages: list[str], floor: str) -> list[str]:
    got = predicted(version, messages)
    if not level.below(got, floor):
        return []
    return [f"{module}: the commits imply {got} but the schema changes need {floor}. Write the "
            "change as feat (feat! or BREAKING CHANGE for a break) so the release is big enough."]


def baseline_problem(ref: str | None, declared: dict[str, str]) -> str | None:
    """Without a release tag, only a module that was never released may be compared to nothing."""
    released = sorted(m for m, v in declared.items() if v != "0.0.0")
    if ref is None and released:
        return f"no release tag to compare against, but {', '.join(released)} already has a version"
    return None


def main(argv: list[str]) -> int:
    ref = level.baseline_ref(argv[argv.index("--baseline") + 1] if "--baseline" in argv else None)
    names = [d.name for d in sorted(MODULES.iterdir()) if (d / "module.json").is_file()]
    declared = {m: read(MODULES / m / "module.json")["version"] for m in names}
    if (message := baseline_problem(ref, declared)):
        print(f"  ! {message}")
        return 1
    if ref is None:
        print("nothing released yet, so nothing to enforce")
        return 0
    log = subprocess.run(["git", "log", "--format=%B%x00", f"{ref}..HEAD"], cwd=ROOT,
                         check=True, capture_output=True, text=True).stdout
    messages = [m.strip() for m in log.split("\0") if m.strip()]
    found = []
    for module in names:
        report = level.module_report(module, ref)
        old = (level.at(ref, MODULES / module / "module.json") or {}).get("version", "0.0.0")
        if report["level"] != "none":
            found += problems(module, old, messages, report["floor"])
    for problem in found:
        print(f"  ! {problem}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
