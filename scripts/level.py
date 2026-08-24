"""Work out how far a version has to be bumped, from what actually changed.

A version number is a promise about compatibility, and a promise nobody checks drifts.
This compares the schemas against the last release and computes the *lowest* level each
one may legitimately claim: a removed property or a changed consensus mapping is major, an
added optional property or a new synonym is minor, a description is a patch.

It computes a floor, not the level. Whether a change that looks additive is really additive
is a judgement the author makes, and the check only refuses a bump that is provably too
small. Anything it cannot classify counts as major, so unknown changes fail towards safety.

Both halves of a schema matter. A changed `@context` target breaks consumers without
changing one byte of structure: documents still validate and now mean something else, which
no ordinary JSON Schema differ would notice.

Levels are computed from the baseline, never from the current value, so running this twice
lands on the same number. That is what makes it safe in a pre-commit hook.

Usage:
  python scripts/level.py                  report what each module owes
  python scripts/level.py --check          fail if a declared version is below the floor
  python scripts/level.py --apply          write the computed versions
  python scripts/level.py --baseline REF   compare against REF instead of the last release
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _shared import context_of

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"

LEVELS = ["patch", "minor", "major"]


def git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.decode("utf-8")


def baseline_ref(explicit: str | None) -> str | None:
    """The release to compare against: the newest version tag, unless one is given."""
    if explicit:
        return explicit
    tags = (git("tag", "--list", "v*", "--sort=-v:refname") or "").split()
    return tags[0] if tags else None


def at(ref: str, path: Path) -> dict | None:
    text = git("show", f"{ref}:{path.relative_to(ROOT).as_posix()}")
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


def surface(schema: dict) -> dict:
    """The parts of a schema a consumer can break against.

    Descriptions, titles and examples are deliberately absent: changing them is a patch,
    and including them here would inflate every prose fix into a minor release.
    """
    required = set(schema.get("required") or [])
    props = {}
    for name, spec in (schema.get("properties") or {}).items():
        # `{}` constrains nothing, so adding or removing it changes nothing a consumer can
        # observe; counting it as a property would make a tidy-up look like a break
        if not isinstance(spec, dict) or not spec:
            continue
        props[name] = {
            "type": spec.get("type"),
            "format": spec.get("format"),
            "enum": sorted(spec["enum"]) if isinstance(spec.get("enum"), list) else None,
            "required": name in required,
        }
    synonyms = {}
    for term, entries in (schema.get("x-oold-context") or {}).items():
        for iri, fragment in (entries or {}).items():
            if isinstance(fragment, dict):
                meta = fragment.get("x-oold-sssom") or {}
                synonyms[f"{term} {iri}"] = {
                    "predicate": meta.get("predicate_id", "skos:exactMatch"),
                    # which set a mapping belongs to is what a consumer selects by, so
                    # moving it between sets is a change they can observe
                    "set": meta.get("mapping_set_id", ""),
                }
    return {
        "id": schema.get("$id"),
        "extends": [r.get("$ref") for r in (schema.get("allOf") or []) if isinstance(r, dict)],
        "properties": props,
        "context": {t: (d.get("@id") if isinstance(d, dict) else d)
                    for t, d in context_of(schema).items()},
        "synonyms": synonyms,
    }


def compare(old: dict, new: dict) -> tuple[str, list[str]]:
    """Minimum level for one schema, with the reasons that forced it."""
    reasons: list[str] = []
    before, after = surface(old), surface(new)

    if before["id"] != after["id"]:
        reasons.append("major: $id changed")
    if before["extends"] != after["extends"]:
        reasons.append("major: what it extends changed")

    for name, spec in before["properties"].items():
        now = after["properties"].get(name)
        if now is None:
            reasons.append(f"major: property {name} removed")
            continue
        if not spec["required"] and now["required"]:
            reasons.append(f"major: property {name} became required")
        if spec["type"] != now["type"] or spec["format"] != now["format"]:
            reasons.append(f"major: property {name} changed its type or format")
        old_enum, new_enum = spec["enum"], now["enum"]
        if old_enum is None and new_enum is not None:
            reasons.append(f"major: property {name} gained an enum")
        elif old_enum and new_enum and set(old_enum) - set(new_enum):
            reasons.append(f"major: property {name} lost permitted values")
        elif old_enum and new_enum and set(new_enum) - set(old_enum):
            reasons.append(f"minor: property {name} gained permitted values")
    for name, spec in after["properties"].items():
        if name not in before["properties"]:
            level = "major" if spec["required"] else "minor"
            reasons.append(f"{level}: property {name} added")

    # The semantic half: a term that maps somewhere else means the same document says
    # something different, which is a break even though nothing structural moved.
    for term, target in before["context"].items():
        if term not in after["context"]:
            reasons.append(f"major: context term {term} removed")
        elif after["context"][term] != target:
            reasons.append(f"major: context term {term} now maps to another IRI")
    for term in after["context"]:
        if term not in before["context"]:
            reasons.append(f"minor: context term {term} added")

    for key, entry in before["synonyms"].items():
        now = after["synonyms"].get(key)
        if now is None:
            reasons.append(f"major: mapping {key} removed")
            continue
        if now["predicate"] != entry["predicate"]:
            reasons.append(f"minor: mapping {key} changed its predicate")
        if now["set"] != entry["set"]:
            reasons.append(f"minor: mapping {key} moved to another set")
    for key in after["synonyms"]:
        if key not in before["synonyms"]:
            reasons.append(f"minor: mapping {key} added")

    if not reasons:
        return ("patch", []) if old != new else ("none", [])
    return max((r.split(":")[0] for r in reasons), key=LEVELS.index), reasons


def raise_to(version: str, level: str) -> str:
    major, minor, patch = (int(p) for p in version.split(".")[:3])
    if level == "major":
        # Below 1.0.0 nothing is promised yet, so a break raises the minor rather than
        # declaring the module stable, which is what 1.0.0 would say.
        return f"{major + 1}.0.0" if major else f"0.{minor + 1}.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return version


def module_report(module: str, ref: str) -> dict:
    """What a module owes: the floor for each schema and for the module itself."""
    base = MODULES / module
    current = {p.name: json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(base.glob("*.schema.json"))}
    old_names = [ln.rsplit("/", 1)[-1] for ln in
                 (git("ls-tree", "--name-only", ref, f"{base.relative_to(ROOT).as_posix()}/")
                  or "").split() if ln.endswith(".schema.json")]

    schemas: dict[str, dict] = {}
    levels = []
    for fname, schema in current.items():
        old = at(ref, base / fname)
        if old is None:
            level, reasons = "minor", ["minor: schema added"]
            declared = schema.get("x-oold-version", "0.0.0")
            floor = declared
        else:
            level, reasons = compare(old, schema)
            declared = schema.get("x-oold-version", "0.0.0")
            floor = raise_to(old.get("x-oold-version", "0.0.0"), level)
        schemas[fname] = {"level": level, "reasons": reasons,
                          "declared": declared, "floor": floor}
        levels.append(level)
    for fname in old_names:
        if fname not in current:
            levels.append("major")
            schemas[fname] = {"level": "major", "reasons": ["major: schema removed"],
                              "declared": "", "floor": ""}

    known = [lv for lv in levels if lv != "none"]
    module_level = max(known, key=LEVELS.index) if known else "none"
    meta = base / "module.json"
    old_meta = at(ref, meta)
    declared = json.loads(meta.read_text(encoding="utf-8")).get("version", "0.0.0") \
        if meta.exists() else "0.0.0"
    floor = raise_to((old_meta or {}).get("version", "0.0.0"), module_level) \
        if old_meta else declared
    return {"schemas": schemas, "level": module_level, "declared": declared, "floor": floor}


def below(declared: str, floor: str) -> bool:
    """True when a declared version does not reach the floor."""
    def parts(v):
        return tuple(int(p) for p in (v.split(".") + ["0", "0", "0"])[:3])
    return parts(declared) < parts(floor)


def apply(module: str, report: dict) -> list[str]:
    written = []
    base = MODULES / module
    for fname, info in report["schemas"].items():
        path = base / fname
        if not path.exists() or not info["floor"] or not below(info["declared"], info["floor"]):
            continue
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(f'"x-oold-version": "{info["declared"]}"',
                         f'"x-oold-version": "{info["floor"]}"'),
            encoding="utf-8", newline="\n")
        written.append(f"{fname} {info['declared']} -> {info['floor']}")
    meta = base / "module.json"
    if meta.exists() and report["floor"] and below(report["declared"], report["floor"]):
        text = meta.read_text(encoding="utf-8")
        meta.write_text(text.replace(f'"version": "{report["declared"]}"',
                                     f'"version": "{report["floor"]}"'),
                        encoding="utf-8", newline="\n")
        written.append(f"module.json {report['declared']} -> {report['floor']}")
    return written


def main() -> None:
    args = sys.argv[1:]
    explicit = args[args.index("--baseline") + 1] if "--baseline" in args else None
    ref = baseline_ref(explicit)
    if not ref:
        print("no release to compare against yet, so nothing to enforce")
        return

    problems = []
    for module_dir in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        module = module_dir.name
        if not any(module_dir.glob("*.schema.json")):
            continue
        report = module_report(module, ref)
        if report["level"] == "none":
            print(f"{module}: unchanged since {ref}")
            continue
        print(f"{module}: {report['level']} since {ref}, "
              f"declared {report['declared']}, floor {report['floor']}")
        for fname, info in sorted(report["schemas"].items()):
            if info["level"] != "none":
                print(f"  {fname}: {info['level']}")
                for reason in info["reasons"][:4]:
                    print(f"    {reason}")

        if "--apply" in args:
            for line in apply(module, report):
                print(f"  wrote {line}")
        elif below(report["declared"], report["floor"]):
            problems.append(f"{module} declares {report['declared']}, "
                            f"but {report['level']} changes require {report['floor']}")
        for fname, info in sorted(report["schemas"].items()):
            if ("--apply" not in args and info["floor"]
                    and below(info["declared"], info["floor"])):
                problems.append(f"{module}/{fname} declares {info['declared']}, "
                                f"but {info['level']} changes require {info['floor']}")

    for problem in problems:
        print(f"  ! {problem}")
    if problems and "--check" in args:
        sys.exit(1)


if __name__ == "__main__":
    main()
