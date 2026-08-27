"""Extract human-readable labels for the ontology IRIs the schemas map to.

Several of the mapped ontologies use opaque identifiers: EMMO mints
`EMMO_c1c8ac3c_8a1c_4777_8e0b_14c1f9f9b0c6`, OBO mints `OBI_0001937`. Showing those raw in the
documentation is unreadable, and looking each one up by hand does not scale.

This reads the pinned ontology snapshots with rdflib and writes a committed label map for the
terms the schemas map, so the documentation build stays offline and deterministic and
refreshing labels is a deliberate act tied to an ontology version bump.

The snapshot directories are given on the command line: they are pinned per project and do not
live in this repository.

Usage:
  python scripts/extract_labels.py <ontology-dir-or-file> [...] [--fetch-missing]

Writes generated/labels.json:
  { "<full IRI>": {"label": "...", "source": "<file or ols4>"} }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "generated" / "labels.json"

# A term of this repository has no ontology label to find: it is a placeholder for a
# vocabulary that does not exist yet, and the schema is where it is described.
OWN = "https://w3id.org/oo-ld/schemas/"

QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?term ?label WHERE {
  { ?term skos:prefLabel ?label } UNION { ?term rdfs:label ?label }
  FILTER (isIRI(?term))
  FILTER (!bound(?label) || lang(?label) IN ("", "en"))
}
ORDER BY ?term DESC(?label)
"""

def mapped_iris() -> set[str]:
    """Every IRI the schemas map to, compact forms expanded with their own prefixes.

    Read from the schemas rather than listed here. A list would drift the moment a mapping
    is added, and it drifts silently: the only symptom is an unlabelled row in a table.
    """
    prefixes: dict[str, str] = {}
    contexts: list[dict] = []
    synonyms: list[dict] = []
    for path in sorted((ROOT / "modules").rglob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        ctx = schema.get("@context")
        parts = [c for c in ctx if isinstance(c, dict)] if isinstance(ctx, list) else [ctx]
        for part in parts:
            if isinstance(part, dict):
                contexts.append(part)
                prefixes.update({k: v for k, v in part.items()
                                 if isinstance(v, str) and v.endswith(("#", "/", ":"))})
        synonyms.append(schema.get("x-oold-context") or {})

    found: set[str] = set()

    def add(iri):
        # a prefix declaration is a namespace, not a term, and nothing can label it
        if not isinstance(iri, str) or iri.startswith("@") or iri.endswith(("#", "/", ":")):
            return
        if iri.startswith(("http://", "https://")):
            found.add(iri)
            return
        prefix, _, rest = iri.partition(":")
        if prefix in prefixes and rest:
            found.add(prefixes[prefix] + rest)

    for part in contexts:
        for value in part.values():
            add(value.get("@id") if isinstance(value, dict) else value)
    for block in synonyms:
        for entries in block.values():
            for iri in (entries or {}):
                add(iri)
    return found


def ontology_iri(graph) -> str:
    """The IRI of the ontology a file defines, for attributing a label to its owner."""
    from rdflib import OWL, RDF  # noqa: PLC0415

    for subject in graph.subjects(RDF.type, OWL.Ontology):
        return str(subject)
    return ""


def harvest(path: Path) -> tuple[dict[str, str], str]:
    """Every labelled subject in one ontology file.

    Parsed properly rather than by pattern: a Turtle document has multi-line strings,
    escapes and prefix scoping, and a regex over it silently drops terms whose comment
    happens to contain a line starting at column zero.
    """
    from rdflib import Graph  # noqa: PLC0415

    graph = Graph()
    graph.parse(str(path), format="xml" if path.suffix == ".owl" else "turtle")
    found: dict[str, str] = {}
    # prefLabel wins over label, English preferred, blank nodes skipped
    for row in graph.query(QUERY):
        iri = str(row.term)
        if iri.startswith(("http://", "https://")):
            found.setdefault(iri, str(row.label))
    return found, ontology_iri(graph)


def fetch_missing(labels: dict[str, dict[str, str]]) -> None:
    """Resolve mapped IRIs that no pinned snapshot carries, from OLS."""
    import urllib.parse  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    for iri in sorted(mapped_iris() - set(labels)):
        if iri.startswith(OWN):
            continue
        url = ("https://www.ebi.ac.uk/ols4/api/terms?iri="
               + urllib.parse.quote(iri, safe=""))
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                terms = json.load(response).get("_embedded", {}).get("terms", [])
            if not terms:
                print(f"  no label found for {iri}", file=sys.stderr)
                continue
            labels[iri] = {"label": terms[0]["label"], "source": "ols4"}
        except Exception as exc:
            print(f"  could not resolve {iri}: {exc}", file=sys.stderr)


def iri_prefix(ontology: str) -> str:
    """The namespace an ontology IRI covers, so a term can be matched to its owner.

    A build that leaves its version placeholder unsubstituted, as the QUDT release does with
    `$$QUDT_VERSION$$`, would otherwise cover nothing and let whichever importing file sorts
    first claim its terms.
    """
    if not ontology:
        return ""
    parts = [p for p in ontology.rstrip("/").split("/") if not p.startswith("$$")]
    return "/".join(parts[:-1]) + "/"


def owns(ontology: str, term: str) -> bool:
    """Whether an ontology is the one that defines a term.

    Namespace alone cannot decide it: every OBO ontology mints under
    `purl.obolibrary.org/obo/`, so a file that merely imports UO covers its terms as well
    as UO does. Where a local name carries its ontology as a prefix, `UO_0000010` or
    `EMMO_c1c8...`, that prefix decides; otherwise the namespace does.
    """
    if not ontology:
        return False
    short = (ontology.rstrip("/").rsplit("/", 1)[-1]
             .removesuffix(".owl").removesuffix(".ttl").lower())
    local = term.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if "_" in local:
        return local.split("_")[0].lower() == short
    return term.startswith(iri_prefix(ontology))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)

    labels: dict[str, dict[str, str]] = {}
    for arg in args:
        base = Path(arg)
        files = (sorted(f for f in base.rglob("*") if f.suffix in (".ttl", ".owl"))
                 if base.is_dir() else [base])
        for f in files:
            # named by ontology and version, so a label states which pin it came from
            prefix = "/".join(base.resolve().parts[-2:]) + "/" if base.is_dir() else ""
            source_path = prefix + (f.relative_to(base).as_posix() if base.is_dir() else f.name)
            try:
                found, source = harvest(f)
            except Exception as exc:
                print(f"  {f.name}: {exc}", file=sys.stderr)
                continue
            # An ontology that imports another carries its labels too, so prefer the file
            # whose own IRI covers the term: an EMMO term is labelled by EMMO, not by a
            # domain ontology that happens to include it.
            for iri, label in found.items():
                mine = owns(source, iri)
                if iri not in labels or (mine and not labels[iri].get("owner")):
                    labels[iri] = {"label": label, "source": source_path, "owner": mine}
            print(f"  {source_path}: {len(found)} labelled terms", file=sys.stderr)

    if "--fetch-missing" in sys.argv:
        fetch_missing(labels)

    # Only the terms the schemas actually map. A snapshot carries tens of thousands of
    # labels, and committing them all would bury the handful this documentation shows in
    # a megabyte that changes whenever an ontology is repinned.
    wanted = mapped_iris()
    labels = {iri: entry for iri, entry in labels.items() if iri in wanted}
    missing = sorted(i for i in wanted - set(labels) if not i.startswith(OWN))
    for iri in missing:
        print(f"  no label for {iri}", file=sys.stderr)

    # `owner` only serves to pick between two files claiming the same term
    written = {iri: {k: v for k, v in entry.items() if k != "owner"}
               for iri, entry in sorted(labels.items())}
    OUT.write_text(json.dumps(written, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {OUT} with {len(labels)} labels")


if __name__ == "__main__":
    main()
