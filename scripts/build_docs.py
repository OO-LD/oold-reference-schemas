"""Publish the schemas into the documentation site at their dereferenceable paths.

Documentation is written by hand; the schema pages embed the schema files rather than
paraphrasing them, so nothing about a schema is retyped into prose. The one thing that must
be derived is this: a conformance IRI has to resolve to the schema JSON itself, so every schema is
copied to its versioned path under the site root before the site is built.

    https://schemas.oo-ld.org/<module>/<version>/<Name>.schema.json

Usage: python scripts/build_docs.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from _shared import context_of, mapping_sets, module_version, read, set_name

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GENERATED = ROOT / "generated"
MODULES = ROOT / "modules"


def module_names() -> list[str]:
    """Every module in the tree. Read from disk rather than listed, so adding one is
    adding a directory."""
    return sorted(d.name for d in MODULES.iterdir() if d.is_dir())


def promote(base_ctx: dict, schemas: list[dict], set_id: str | None) -> dict:
    """The effective @context for a mapping set: promote the synonyms tagged with it,
    leave every other term on its consensus mapping."""
    ctx = dict(base_ctx)
    if not set_id:
        return ctx
    for schema in schemas:
        for term, syns in (schema.get("x-oold-context") or {}).items():
            for iri, frag in (syns or {}).items():
                if not isinstance(frag, dict):
                    continue
                if (frag.get("x-oold-sssom") or {}).get("mapping_set_id") != set_id:
                    continue
                rest = {k: v for k, v in frag.items() if k != "x-oold-sssom"}
                if rest:
                    ctx[term] = {"@id": iri, **rest}
                else:
                    prim = ctx.get(term)
                    if isinstance(prim, dict):
                        inherited = {k: v for k, v in prim.items() if k != "@id"}
                        ctx[term] = {"@id": iri, **inherited} if inherited else iri
                    else:
                        ctx[term] = iri
                break
    return ctx


def synth_instance(name: str, schema: dict, schemas: list[dict]) -> dict | None:
    """Build an instance from the schema's own `examples` and `default` values.

    A committed *.instance.json is authoritative where one exists; this covers the schemas
    that do not have one, so every schema page can show an instance and its RDF readings.
    Only authored values are used: a property with neither an example nor a default is left
    out, and a schema that cannot fill its required properties yields nothing rather than an
    invented instance.
    """
    # a root-level `examples` entry is a whole example instance, which is exactly what
    # this needs; per-property examples are the fallback
    for s in reversed(schemas):
        if isinstance(s.get("examples"), list) and s["examples"]:
            ex = s["examples"][0]
            if isinstance(ex, dict):
                return {"@context": f"{name}.schema.json", "$schema": f"{name}.schema.json",
                        "@id": "https://example.org/instance", **ex}

    props: dict = {}
    for s in schemas:
        props.update(s.get("properties") or {})
    required = {r for s in schemas for r in (s.get("required") or [])}

    doc: dict = {}
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("examples"):
            doc[name] = spec["examples"][0]
        elif "default" in spec:
            doc[name] = spec["default"]
        elif spec.get("enum"):
            doc[name] = spec["enum"][0]
    if not required <= doc.keys():
        return None
    if not doc:
        return None
    return {"@context": f"{name}.schema.json", "$schema": f"{name}.schema.json",
            "@id": "https://example.org/instance", **doc}


def chain(schema_file: Path) -> list[Path]:
    """A schema's inheritance chain, base first, by following allOf $refs.

    The RDF readings need the whole chain: a subschema inherits the terms and the mappings
    of everything it extends, and expanding an instance against its own context alone
    produces an empty graph.
    """
    out: list[Path] = []

    def walk(f: Path) -> None:
        if not f.is_file() or f in out:
            return
        d = json.loads(f.read_text(encoding="utf-8"))
        for ref in (d.get("allOf") or []):
            if isinstance(ref, dict) and isinstance(ref.get("$ref"), str):
                walk(f.parent / ref["$ref"])
        out.append(f)

    walk(schema_file)
    return out


def write_rdf(module: str, name: str, schema_files: list[Path], instance: Path | dict) -> int:
    """Render the instance to Turtle under each mapping set, for the schema page tabs.

    Needs pyld and rdflib. When they are unavailable the RDF tabs are simply omitted,
    so a plain `python scripts/build_docs.py` still works.
    """
    try:
        from pyld import jsonld  # noqa: PLC0415
        from rdflib import Graph  # noqa: PLC0415
    except ImportError:
        return 0

    schemas = [json.loads(f.read_text(encoding="utf-8")) for f in schema_files]
    base_ctx: dict = {}
    for s in schemas:
        base_ctx.update(context_of(s))

    doc = (json.loads(instance.read_text(encoding="utf-8"))
           if isinstance(instance, Path) else dict(instance))
    doc.pop("$schema", None)

    out_dir = GENERATED / module
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for set_id in [None, *mapping_sets(schemas)]:
        label = "consensus" if set_id is None else set_name(set_id)
        payload = {**doc, "@context": promote(base_ctx, schemas, set_id)}
        try:
            nq = jsonld.to_rdf(payload, {"format": "application/n-quads"})
            graph = Graph().parse(data=nq, format="nquads")
            for prefix, iri in base_ctx.items():
                if isinstance(iri, str) and iri.endswith(("#", "/", ":")) and prefix.isalpha():
                    graph.bind(prefix, iri)
            ttl = graph.serialize(format="turtle")
        except Exception as exc:  # a broken mapping should fail loudly in CI, not here
            print(f"  ! {module}/{name} [{label}]: {exc}")
            continue
        (out_dir / f"{name}.{label}.ttl").write_text(ttl.strip() + "\n",
                                                     encoding="utf-8", newline="\n")
        written += 1
    return written


def stage_mappings() -> int:
    """Copy the generated SSSOM sets to the path their mapping_set_id points at."""
    src = GENERATED / "mappings"
    if not src.is_dir():
        return 0
    target = DOCS / "mappings"
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(src.rglob("*.sssom.tsv")):
        dest = target / f.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        count += 1
    return count


def main() -> None:
    published = 0
    rdf = 0
    for module in module_names():
        files = sorted((MODULES / module).glob("*.json"))
        if not files:
            continue
        # Two paths, one immutable and one moving. The exact release is written once and
        # never rewritten, so a consumer who needs reproducibility can pin it. The
        # major.minor path is an alias for the newest patch of that compatibility line,
        # which is what a conformance IRI names, so a typo fix reaches everyone pinned to
        # it without minting a version nobody asked for.
        exact = module_version(module, full=True)
        line = module_version(module)
        for version in (exact, line):
            target = DOCS / module / version
            target.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copy2(f, target / f.name)
                published += 1
        version = line
        target = DOCS / module / line
        title = (read(MODULES / module / "module.json").get("title", module)
                 if (MODULES / module / "module.json").exists() else module)
        listing = [
            f"# {title} {exact}",
            "",
            f"Referenced by the conformance IRI",
            f"`https://w3id.org/oo-ld/schemas/{module}/{line}`, which tracks the newest patch of",
            f"{line}. A release publishes these files at `https://schemas.oo-ld.org/{module}/{line}/`",
            f"and, immutably, at `https://schemas.oo-ld.org/{module}/{exact}/`; until then the tip",
            f"of main is served at `https://schemas.oo-ld.org/{module}/dev/`.",
            "",
            "| file |",
            "|---|",
        ]
        listing += [f"| [`{f.name}`]({f.name}) |" for f in files]
        (target / "index.md").write_text("\n".join(listing) + "\n",
                                         encoding="utf-8", newline="\n")

        # Instance and RDF readings for the schema page tabs, one reading per mapping set.
        # A committed instance wins; otherwise one is built from the schema's own examples
        # and defaults, so every schema page can show the same four views.
        schema_files = sorted((MODULES / module).glob("*.schema.json"))
        for sf in schema_files:
            name = sf.name[: -len(".schema.json")]
            lineage = chain(sf)
            committed = MODULES / module / f"{name}.instance.json"
            if committed.is_file():
                rdf += write_rdf(module, name, lineage, committed)
                continue
            schema = json.loads(sf.read_text(encoding="utf-8"))
            built = synth_instance(name, schema,
                                   [json.loads(f.read_text(encoding="utf-8")) for f in lineage])
            if not built:
                continue
            gen_dir = GENERATED / module
            gen_dir.mkdir(parents=True, exist_ok=True)
            (gen_dir / f"{name}.instance.json").write_text(
                json.dumps(built, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")
            rdf += write_rdf(module, name, lineage, built)

    mappings = stage_mappings()
    print(f"published {published} schema files, {rdf} RDF readings, "
          f"{mappings} mapping sets")


if __name__ == "__main__":
    main()
