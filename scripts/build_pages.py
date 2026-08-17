"""Seed and check the schema pages against the schemas.

The schemas are the source of truth. This mirrors them into docs/modules as a page tree:
a directory per module, then a directory per schema nested along the `allOf` chain, so the
documentation tree is the inheritance tree and neither can drift from the other.

A page is seeded once and never overwritten, because prose belongs to whoever wrote it.
What is checked on every run is that the page still documents the schema its location
claims: a page whose `oold_schema_renderer` call names another schema, or no schema at all, is
reported, as is a page whose schema has been deleted.

Every schema gets its own directory with an `index.md`, including schemas that have no
subschemas. A leaf page written as `<name>.md` would have to move the day someone extends
it, and moving a file that has acquired hand-written prose is a migration that gets done
badly once. A page found anywhere other than its computed location is moved there rather
than re-seeded, so its prose travels with it.

Usage:
  python scripts/build_pages.py            seed missing pages, report problems
  python scripts/build_pages.py --check    report only, exit non-zero on any problem
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
PAGES = ROOT / "docs" / "modules"
MAPPINGS = ROOT / "docs" / "mappings"
SETS = ROOT / "generated" / "mappings"
CONFIG = ROOT / "zensical.toml"

NAV_BEGIN = "    # BEGIN generated nav"
NAV_END = "    # END generated nav"

CALL = re.compile(r"""oold_schema_renderer\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']""")
SET_CALL = re.compile(r"""sssom_table\(\s*["']([^"']+)["']""")

STUB = """---
hide:
  - toc
---

# {title}

{description}

{{{{ oold_schema_meta_data("{module}", "{name}") }}}}

{{{{ oold_schema_renderer("{module}", "{name}") }}}}
"""


CROSSWALK_STUB = """# Crosswalks

What two communities call the same thing, chained through the terms they both map. These are
derived from the curated sets, never authored, so every row records the term the chain went
through and carries the `semapv:MappingChaining` justification.

A chain composes only when at least one of its two links is an `exactMatch`. Two
`closeMatch` links do not compose, so those pairs are omitted rather than weakened.

{{ mapping_crosswalks() }}
"""

# A set's short name is its identifier; its display title is not derivable from it.
TITLES = {
    "consensus": "Consensus",
    "emmo": "EMMO",
    "pmdco": "PMDco",
    "schemaorg": "schema.org",
}

SET_STUB = """# {title} mappings

{lead}

Generated from the mappings declared in the schemas, so this page and the schemas cannot
disagree.

## Stated mappings

Each row maps a term of this library, defined by the schema it links to, onto its
counterpart in {title}, with the ontology version the mapping was checked against.

{{{{ download("/mappings/{name}.sssom.tsv", "SSSOM TSV") }}}}

{{{{ sssom_table("{name}") }}}}

## Derived crosswalks

What {title} and another vocabulary call the same thing, chained through the terms both map
here. Derived rather than stated: every row carries the `semapv:MappingChaining`
justification and names the term the chain went through. The rule and the full set are on
the [Crosswalks](../crosswalks/) page.

{{{{ mapping_crosswalks("{name}") }}}}
"""


def mapping_sets() -> list[str]:
    if not SETS.is_dir():
        return []
    return sorted(f.name[: -len(".sssom.tsv")] for f in SETS.glob("*.sssom.tsv"))


def seed_mapping_pages(check: bool, problems: list[str]) -> int:
    """One page per generated mapping set, plus one for all crosswalks together."""
    seeded = 0
    if (SETS / "crosswalks").is_dir():
        target = MAPPINGS / "crosswalks" / "index.md"
        if not target.exists():
            if check:
                problems.append(f"{target.relative_to(ROOT)} is missing")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(CROSSWALK_STUB, encoding="utf-8", newline="\n")
                seeded += 1
        elif "mapping_crosswalks()" not in target.read_text(encoding="utf-8"):
            problems.append(f"{target.relative_to(ROOT)} has no mapping_crosswalks() call")
    for name in mapping_sets():
        target = MAPPINGS / name / "index.md"
        if target.exists():
            if name not in SET_CALL.findall(target.read_text(encoding="utf-8")):
                problems.append(f'{target.relative_to(ROOT)} has no sssom_table("{name}") call')
            continue
        if check:
            problems.append(f"{target.relative_to(ROOT)} is missing")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        title = TITLES.get(name, name)
        lead = ("The reading an instance has when no mapping set is selected."
                if name == "consensus" else
                f"How the terms of this library are named in {title}.")
        target.write_text(SET_STUB.format(name=name, title=title, lead=lead),
                          encoding="utf-8", newline="\n")
        seeded += 1
    return seeded


def check_instances(problems: list[str]) -> None:
    """`$schema` must be the first key of an instance.

    Editors pick up validation from it, and some stop looking after the first key, so an
    instance that carries it late is an instance nobody gets help editing. Cheap to keep
    right, invisible when it is wrong.
    """
    for path in sorted(MODULES.rglob("*.instance.json")):
        text = path.read_text(encoding="utf-8")
        keys = list(json.loads(text).keys())
        if "$schema" not in keys:
            problems.append(f"{path.relative_to(ROOT)} has no $schema")
        elif keys[0] != "$schema":
            problems.append(f"{path.relative_to(ROOT)} starts with `{keys[0]}`: $schema must "
                            "come first, or an editor will not validate it")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def modules() -> list[str]:
    return sorted(d.name for d in MODULES.iterdir()
                  if d.is_dir() and any(d.glob("*.schema.json")))


def lineage(module: str) -> dict[str, list[str]]:
    """Each schema of a module with its ancestors, outermost first.

    The first `$ref` of an `allOf` owns the tree position. A schema may extend several,
    but a page can only live in one place, and the first is the one authors write first.
    """
    base = MODULES / module
    parent: dict[str, str | None] = {}
    for path in sorted(base.glob("*.schema.json")):
        name = path.name[: -len(".schema.json")]
        refs = [r.get("$ref") for r in (read(path).get("allOf") or []) if isinstance(r, dict)]
        first = next((r for r in refs if isinstance(r, str) and r.endswith(".schema.json")), None)
        parent[name] = first[: -len(".schema.json")] if first else None

    chains: dict[str, list[str]] = {}
    for name in parent:
        chain, seen, current = [], set(), parent[name]
        while current and current in parent and current not in seen:
            seen.add(current)
            chain.insert(0, current)
            current = parent[current]
        chains[name] = chain
    return chains


def page_path(module: str, name: str, chain: list[str]) -> Path:
    return PAGES.joinpath(module, *[a.lower() for a in chain], name.lower(), "index.md")


def existing_pages() -> dict[tuple[str, str], Path]:
    """Where each schema is currently documented, read off the pages themselves."""
    found: dict[tuple[str, str], Path] = {}
    for path in sorted(PAGES.rglob("*.md")):
        for module, name in CALL.findall(path.read_text(encoding="utf-8")):
            found.setdefault((module, name), path)
    return found


def move(src: Path, dst: Path) -> None:
    """Move a page, keeping it under version control where git is available."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True,
                       capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        src.rename(dst)


def nav_entry(module: str, name: str, children: dict[str, list[str]], depth: int) -> list[str]:
    """One nav entry per schema, nested like the pages, as zensical.toml lines."""
    pad = "    " * (depth + 2)
    rel = "/".join(["modules", module, *[a.lower() for a in children["chains"][name]],
                    name.lower(), "index.md"])
    kids = sorted(k for k, chain in children["chains"].items() if chain and chain[-1] == name)
    if not kids:
        return [f'{pad}{{ "{name}" = "{rel}" }},']
    lines = [f'{pad}{{ "{name}" = [', f'{pad}    "{rel}",']
    for kid in kids:
        lines += nav_entry(module, kid, children, depth + 1)
    lines.append(f"{pad}]}},")
    return lines


def nav(all_chains: dict[str, dict[str, list[str]]]) -> str:
    lines = [NAV_BEGIN, '    { "Modules" = [',
             '        { "Overview" = "modules/index.md" },']
    for module, chains in all_chains.items():
        roots = sorted(n for n, chain in chains.items() if not chain)
        title = read(MODULES / module / "module.json")["title"] if (
            MODULES / module / "module.json").exists() else module
        lines.append(f'        {{ "{title}" = [')
        for root in roots:
            lines += nav_entry(module, root, {"chains": chains}, 1)
        lines.append("        ]},")
    lines.append("    ]},")
    lines.append('    { "Mapping sets" = [')
    lines.append('        { "Overview" = "mapping-sets.md" },')
    for name in mapping_sets():
        lines.append(f'        {{ "{TITLES.get(name, name)}" = '
                     f'"mappings/{name}/index.md" }},')
    if (SETS / "crosswalks").is_dir():
        lines.append('        { "Crosswalks" = "mappings/crosswalks/index.md" },')
    lines += ["    ]},", NAV_END]
    return "\n".join(lines)


def write_nav(text: str) -> bool:
    """Replace the generated region of the nav. Returns True if the file changed."""
    config = CONFIG.read_text(encoding="utf-8")
    if NAV_BEGIN not in config or NAV_END not in config:
        print(f"  ! {CONFIG.name} has no generated nav region, nav not updated")
        return False
    head = config[: config.index(NAV_BEGIN)]
    tail = config[config.index(NAV_END) + len(NAV_END):]
    updated = head + text + tail
    if updated == config:
        return False
    CONFIG.write_text(updated, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    check = "--check" in sys.argv
    pages = existing_pages()
    problems: list[str] = []
    seeded = moved = 0
    all_chains: dict[str, dict[str, list[str]]] = {}

    for module in modules():
        chains = lineage(module)
        all_chains[module] = chains
        for name, chain in sorted(chains.items()):
            target = page_path(module, name, chain)
            current = pages.pop((module, name), None)

            if current and current != target:
                if check:
                    problems.append(f"{current.relative_to(ROOT)} belongs at "
                                    f"{target.relative_to(ROOT)}")
                else:
                    if target.exists():
                        problems.append(f"{target.relative_to(ROOT)} and "
                                        f"{current.relative_to(ROOT)} both document "
                                        f"{module}/{name}")
                        continue
                    move(current, target)
                    moved += 1
                continue

            if current:
                continue

            if target.exists():
                # the page is there but does not embed its schema, so it documents
                # nothing that can be checked
                problems.append(f"{target.relative_to(ROOT)} has no "
                                f'oold_schema_renderer("{module}", "{name}") call')
                continue

            if check:
                problems.append(f"{target.relative_to(ROOT)} is missing")
                continue

            schema = read(MODULES / module / f"{name}.schema.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(STUB.format(
                title=schema.get("title") or name,
                description=" ".join((schema.get("description") or "").split()),
                module=module, name=name), encoding="utf-8", newline="\n")
            seeded += 1

    for (module, name), path in sorted(pages.items()):
        problems.append(f"{path.relative_to(ROOT)} documents {module}/{name}, "
                        "which no longer exists")

    seeded += seed_mapping_pages(check, problems)
    check_instances(problems)
    text = nav(all_chains)
    if check:
        changed = text not in CONFIG.read_text(encoding="utf-8")
        if changed:
            problems.append("zensical.toml nav does not match the schema tree")
    else:
        changed = write_nav(text)

    print(f"pages: {sum(len(c) for c in all_chains.values())} schemas, "
          f"{seeded} pages seeded, {moved} moved, nav {'updated' if changed else 'unchanged'}")
    for problem in problems:
        print(f"  ! {problem}")
    if problems and check:
        sys.exit(1)


if __name__ == "__main__":
    main()
