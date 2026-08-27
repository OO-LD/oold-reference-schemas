"""Bundle the mappings carried by the schemas into SSSOM mapping sets.

Every schema states its correspondences inline: one consensus mapping per term in
`@context`, and any number of community synonyms in `x-oold-context`, each tagged with the
mapping set it belongs to. That is the right place to author them, because a mapping is
only meaningful next to the term it maps. It is the wrong place to *consume* them: a tool
that wants "everything the EMMO community says about this library" would have to walk every
schema and filter.

So the sets are derived, not maintained: this collects the inline mappings, groups them by
`mapping_set_id`, and writes one SSSOM TSV per set. The consensus mappings are emitted as a
set of their own, so the reading an instance has without any selection is described in the
same form as the alternatives to it.

SSSOM specifies TSV with a commented YAML preamble, which is what is written here.

Usage: python scripts/build_mappings.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from _shared import context_of, module_version, read, set_name

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
GENERATED = ROOT / "generated"
OUT = GENERATED / "mappings"

IRI_BASE = "https://w3id.org/oo-ld/schemas"
LICENSE = "https://creativecommons.org/publicdomain/zero/1.0/"


def release() -> str:
    """The repository release these sets were generated for.

    The sets are derived from the whole library, so their version is the library's, not one
    module's. Stamped here rather than written into the schemas, so a release does not have
    to touch every mapping_set_id.
    """
    path = ROOT / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "dev"

COLUMNS = [
    "subject_id", "subject_label", "predicate_id", "object_id", "object_label",
    "mapping_justification", "subject_source", "subject_source_version", "object_source",
    "object_source_version", "comment",
]


def labels() -> dict[str, dict[str, str]]:
    path = GENERATED / "labels.json"
    return read(path) if path.exists() else {}


def prefixes(ctx: dict) -> dict[str, str]:
    """The namespaces a context declares, in both forms it may declare them.

    A schema declares its own namespace as a term definition with `@prefix`, not as a plain
    string, and those are exactly the namespaces this library's placeholder terms live in:
    reading only the string form leaves every one of its own terms unexpandable.
    """
    out = {}
    for term, definition in ctx.items():
        if term.startswith("@") or not term.isalnum():
            continue
        if isinstance(definition, str):
            target_iri, declared = definition, False
        elif isinstance(definition, dict):
            target_iri, declared = definition.get("@id"), bool(definition.get("@prefix"))
        else:
            continue
        if isinstance(target_iri, str) and (declared or target_iri.endswith(("#", "/", ":"))):
            out[term] = target_iri
    return out


def expand(iri: str, curie_map: dict[str, str]) -> str:
    if not isinstance(iri, str) or ":" not in iri or iri.startswith(("http://", "https://")):
        return iri
    prefix, rest = iri.split(":", 1)
    return curie_map[prefix] + rest if prefix in curie_map else iri


def target(defn) -> str | None:
    """The IRI a @context term maps to, ignoring the keyword aliases."""
    iri = defn.get("@id") if isinstance(defn, dict) else defn
    return iri if isinstance(iri, str) and not iri.startswith("@") else None


# Chaining two curated mappings through the term they share gives a mapping between two
# communities that nobody authored. It is worth publishing, and worth keeping apart from
# what was curated, so it lands in its own files with the chaining justification.
#
# Only chains with an exact link on at least one side survive. Two close matches do not
# compose: "roughly the same as X" and "X is roughly the same as Y" says nothing reliable
# about Y, and a mapping commons that grades a guess like a curation is worse than one
# with fewer rows.

INVERSE = {
    "skos:exactMatch": "skos:exactMatch",
    "skos:closeMatch": "skos:closeMatch",
    "skos:relatedMatch": "skos:relatedMatch",
    "skos:broadMatch": "skos:narrowMatch",
    "skos:narrowMatch": "skos:broadMatch",
}

EXACT = "skos:exactMatch"


def compose(left: str, right: str) -> str | None:
    """Predicate of a chain, or None when the chain proves nothing."""
    if left == EXACT:
        return right
    if right == EXACT:
        return left
    return None


def crosswalk(a: str, rows_a: list[dict], b: str, rows_b: list[dict],
              curie_map: dict[str, str]) -> list[dict]:
    """Mappings between two communities, chained through the terms they both map."""
    by_term: dict[str, list[dict]] = {}
    for row in rows_b:
        by_term.setdefault(row["subject_id"], []).append(row)

    out = []
    for left in rows_a:
        for right in by_term.get(left["subject_id"], []):
            if left["object_id"] == right["object_id"]:
                continue
            predicate = compose(INVERSE.get(left["predicate_id"], left["predicate_id"]),
                                right["predicate_id"])
            if not predicate:
                continue
            out.append({
                "subject_id": expand(left["object_id"], curie_map),
                "subject_label": left["object_label"],
                "predicate_id": predicate,
                "object_id": expand(right["object_id"], curie_map),
                "object_label": right["object_label"],
                "mapping_justification": "semapv:MappingChaining",
                "subject_source": f"{IRI_BASE}/mappings/{a}.sssom.tsv",
                "subject_source_version": left.get("object_source_version", ""),
                "object_source": f"{IRI_BASE}/mappings/{b}.sssom.tsv",
                "object_source_version": right["object_source_version"],
                "comment": f'chained through {left["subject_label"]}',
            })
    return out


def collect() -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Every mapping in the library, grouped by mapping set."""
    sets: dict[str, list[dict]] = {}
    curie_map: dict[str, str] = {}
    label_map = labels()

    for module_dir in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        module = module_dir.name
        schemas = sorted(module_dir.glob("*.schema.json"))
        if not schemas:
            continue
        # The IRI identifies the term, which keeps its identity across releases; the
        # version it was written for goes in the SSSOM slot that exists for it. Putting the
        # version in the IRI would make one term look like two whenever a set from an
        # earlier release is merged with a later one.
        subject_source = f"{IRI_BASE}/{module}"
        subject_version = module_version(module, full=True)

        merged_ctx: dict = {}
        for path in schemas:
            merged_ctx.update(context_of(read(path)))
        curie_map.update(prefixes(merged_ctx))

        def row(term, subject, predicate, obj, comment="", source="", version=""):
            full = expand(obj, curie_map)
            entry = label_map.get(full) or {}
            return {
                "subject_id": subject,
                "subject_label": term,
                "predicate_id": predicate,
                "object_id": obj,
                "object_label": entry.get("label", ""),
                "mapping_justification": "semapv:ManualMappingCuration",
                "subject_source": subject_source,
                "subject_source_version": subject_version,
                "object_source": source,
                "object_source_version": version,
                "comment": comment,
            }

        def subject_of(ctx, term):
            """What the row is about.

            A term name alone does not identify a term: two schemas of one module may spell
            the same key and mean different edges, and joining their mappings on the name
            would chain two communities through a term neither of them shares. Where the
            term maps to a placeholder of this library, that placeholder is the identity,
            since it belongs to exactly one schema.
            """
            iri = expand(target(ctx.get(term)) or "", curie_map)
            if not iri.startswith(f"{IRI_BASE}/"):
                return f"{subject_source}#{term}"
            # without the version, for the reason the module subject drops it: a term keeps
            # its identity across releases, and the version has its own SSSOM column
            return re.sub(rf"^({re.escape(IRI_BASE)}/[^/]+)/[^/]+/", r"/", iri)

        for path in schemas:
            schema = read(path)
            ctx = context_of(schema)
            for term, defn in ctx.items():
                iri = target(defn)
                if iri and not iri.endswith(("#", "/", ":")):
                    subject = subject_of(ctx, term)
                    # a placeholder is its own subject, and stating that it matches itself
                    # would say nothing
                    if expand(iri, curie_map) != subject:
                        sets.setdefault("consensus", []).append(
                            row(term, subject, "skos:exactMatch", iri))
            for term, synonyms in (schema.get("x-oold-context") or {}).items():
                for iri, fragment in (synonyms or {}).items():
                    if not isinstance(fragment, dict):
                        continue
                    meta = fragment.get("x-oold-sssom") or {}
                    set_id = meta.get("mapping_set_id")
                    if not set_id:
                        continue
                    name = set_name(set_id)
                    sets.setdefault(name, []).append(row(
                        term,
                        subject_of(ctx, term),
                        meta.get("predicate_id", "skos:exactMatch"),
                        iri,
                        meta.get("comment", ""),
                        meta.get("object_source", ""),
                        meta.get("object_source_version", ""),
                    ))
    return sets, curie_map


def write_set(name: str, rows: list[dict], curie_map: dict[str, str],
              derived: bool = False) -> Path:
    used = sorted({iri.split(":", 1)[0] for row in rows for iri in
                   (row["object_id"], row["predicate_id"], row["mapping_justification"])
                   if ":" in iri and not iri.startswith("http")})
    known = {
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "semapv": "https://w3id.org/semapv/vocab/",
        **curie_map,
    }
    preamble = [
        f"# mapping_set_id: {IRI_BASE}/mappings/{'crosswalks/' if derived else ''}{name}.sssom.tsv",
        f"# mapping_set_version: {release()}",
        f"# mapping_set_title: {name} mappings for the OO-LD reference schemas",
        *(["# comment: derived by chaining the curated sets, not curated"]
          if derived else []),
        f"# license: {LICENSE}",
        "# mapping_provider: https://github.com/OO-LD/oold-reference-schemas",
        "# curie_map:",
    ]
    preamble += [f"#   {p}: {known[p]}" for p in used if p in known]

    lines = preamble + ["\t".join(COLUMNS)]
    for row in sorted(rows, key=lambda r: (r["subject_label"], r["object_id"])):
        lines.append("\t".join(str(row[c]).replace("\t", " ") for c in COLUMNS))

    out_dir = OUT / "crosswalks" if derived else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.sssom.tsv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> None:
    sets, curie_map = collect()
    for name, rows in sorted(sets.items()):
        path = write_set(name, rows, curie_map)
        print(f"  {path.relative_to(ROOT)}: {len(rows)} mappings")

    names = sorted(sets)
    walks = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rows = crosswalk(a, sets[a], b, sets[b], curie_map)
            if not rows:
                continue
            write_set(f"{a}-{b}", rows, curie_map, derived=True)
            walks += 1
            print(f"  crosswalks/{a}-{b}: {len(rows)} chained mappings")
    print(f"wrote {len(sets)} mapping sets and {walks} crosswalks")


if __name__ == "__main__":
    main()
