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
import re
import shutil
from pathlib import Path

from _shared import (chain, context_of, mapping_sets, module_version, read, resolve,
                     set_name)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GENERATED = ROOT / "generated"
MODULES = ROOT / "modules"
LABELS = (read(GENERATED / "labels.json") if (GENERATED / "labels.json").exists() else {})


def terms(context: dict) -> dict:
    """Term names by IRI, so a schema's own placeholders read as the term that defines them.

    An ontology label is better where there is one, so these are the fallback: a node the
    pinned ontologies do not know still reads as ChemicalComponent rather than as `items`.
    """
    prefixes = {}
    for term, definition in context.items():
        target = definition.get("@id") if isinstance(definition, dict) else definition
        if not isinstance(target, str) or not target.startswith("http"):
            continue
        if (isinstance(definition, dict) and definition.get("@prefix")) or target[-1] in "#/":
            prefixes[term] = target

    def expand(target: str) -> str:
        head, sep, rest = target.partition(":")
        return prefixes[head] + rest if sep and head in prefixes else target

    out = {}
    for term, definition in context.items():
        if term.startswith("@"):
            continue
        target = definition.get("@id") if isinstance(definition, dict) else definition
        if not isinstance(target, str):
            continue
        iri = expand(target)
        if iri.startswith("http") and iri not in out:
            out[iri] = term
    return out


def own(names: dict) -> dict:
    """Keep the term names of this repository's own IRIs.

    A term name is what a schema calls something, which is the only name a placeholder has.
    For a term of a real vocabulary the ontology label, or failing that the local name, is
    what a reader expects: emmo:WeightPercent, not emmo:percent because a unit alias here
    happens to be spelled that way.
    """
    return {iri: name for iri, name in names.items()
            if iri.startswith("https://w3id.org/oo-ld/schemas/")}


def namespaces(context: dict) -> dict:
    """Prefix by namespace IRI, so a node can say which vocabulary it comes from."""
    out = {}
    for term, definition in context.items():
        if term.startswith('@'):
            continue
        target = definition.get('@id') if isinstance(definition, dict) else definition
        if not isinstance(target, str) or not target.startswith('http'):
            continue
        prefixed = isinstance(definition, dict) and definition.get('@prefix')
        if prefixed or target[-1] in '#/':
            out.setdefault(target, term)
    return out


def mermaid(graph, labels: dict, prefixes: dict | None = None) -> str:
    """The same reading as a picture.

    A Turtle block answers which triples there are; a reader comparing two mapping sets is
    asking what shape they make, and a diagram answers that at a glance. Labels come from
    the pinned ontologies, so a node reads as SingleComponentComposition rather than as an
    opaque identifier.
    """
    from rdflib import RDF, Literal  # noqa: PLC0415

    def name(term) -> str:
        text = str(term)
        if isinstance(term, Literal):
            return text
        if "/.well-known/genid/" in text:
            return "blank node"
        known = labels.get(text)
        label = (known["label"] if isinstance(known, dict) else str(known)) if known else (
            text.rsplit("#", 1)[-1].rsplit("/", 1)[-1] or text)
        # which vocabulary a term comes from is half of what a reading says, so the prefix
        # is part of the label rather than something to infer from the colour
        for namespace, prefix in sorted((prefixes or {}).items(), key=lambda p: -len(p[0])):
            if text.startswith(namespace):
                return f"{prefix}:{label}"
        return label

    types: dict[str, list[str]] = {}
    for subject, _, obj in graph.triples((None, RDF.type, None)):
        types.setdefault(str(subject), []).append(name(obj))

    ids: dict[str, str] = {}
    declarations: list[str] = []
    edges: list[str] = []

    def node(term) -> str:
        key = str(term)
        if key not in ids:
            ids[key] = f"n{len(ids)}"
            label = name(term).replace('"', "'")
            kinds = types.get(key)
            if isinstance(term, Literal):
                declarations.append(f'  {ids[key]}[/"{label}"/]')
            else:
                caption = f"{label}<br>{', '.join(sorted(kinds))}" if kinds else label
                declarations.append(f'  {ids[key]}["{caption}"]')
        return ids[key]

    for subject, predicate, obj in sorted(graph, key=lambda t: tuple(str(p) for p in t)):
        if predicate == RDF.type:
            continue
        edges.append(f"  {node(subject)} -->|{name(predicate)}| {node(obj)}")
    return chr(10).join(["flowchart LR", *declarations, *edges])


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
                prim = ctx.get(term)
                scoped = ({"@context": prim["@context"]}
                          if isinstance(prim, dict) and "@context" in prim else {})
                if "@reverse" in rest:
                    # the community states the edge in the other direction, so the synonym
                    # is the reverse property and carries no @id of its own. What it scopes
                    # is unaffected: the direction of an edge does not change which terms
                    # the object at its end may use.
                    ctx[term] = {**scoped, **rest}
                elif rest:
                    # a synonym states another IRI for the same JSON, so where the term
                    # scopes a context that scoping is a property of the shape and stays
                    ctx[term] = {"@id": iri, **scoped, **rest}
                else:
                    if isinstance(prim, dict):
                        inherited = {k: v for k, v in prim.items() if k != "@id"}
                        ctx[term] = {"@id": iri, **inherited} if inherited else iri
                    else:
                        ctx[term] = iri
                break
    return ctx


def inline_scoped(context: dict, origin: Path, set_id: str | None = None,
                  seen: tuple = ()) -> dict:
    """Replace a term's scoped context reference by the context it names.

    A scoped `@context` names another schema, and here that schema is a file: resolving it
    from the working tree keeps the generation offline and reads the version being edited,
    the same rule the rest of the build follows. A reference that leaves this repository, or
    one that closes a cycle, is left as written for the consumer to dereference.

    The mapping set applies inside the scope as well. A community reads the whole document,
    not the root object of it, so a scoped context that kept the consensus terms would make
    the embedded object speak a different vocabulary than the tree it hangs in.
    """
    out = {}
    for term, definition in context.items():
        target = (definition.get("@context")
                  if isinstance(definition, dict) else None)
        if not isinstance(target, str):
            out[term] = definition
            continue
        path = resolve(origin, target)
        if not path.is_file():
            out[term] = definition
            continue
        if path in seen or path == origin:
            # the scope names a document already being read, so its terms are active
            # anyway: flattening onto the enclosing context is what the specification
            # allows for a cyclic embed, and it keeps the reading self-contained
            out[term] = {k: v for k, v in definition.items() if k != "@context"}
            continue
        schemas = [read(f) for f in chain(path)]
        nested: dict = {}
        for schema in schemas:
            nested.update(context_of(schema))
        out[term] = {**definition,
                     "@context": inline_scoped(promote(nested, schemas, set_id), path,
                                               set_id, (*seen, path))}
    return out


def inherited(schema: dict, origin: Path) -> list[dict]:
    """A schema and what it extends, base first.

    Only `allOf`: a schema that points a property at another schema is not that schema, so
    the other one's example is an example of the property, not of this document.
    """
    out = []
    for ref in schema.get("allOf") or []:
        if isinstance(ref, dict) and isinstance(ref.get("$ref"), str):
            target = resolve(origin, ref["$ref"].partition("#")[0])
            if target.is_file():
                out += inherited(read(target), target)
    return [*out, schema]


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
                return {"$schema": f"{name}.schema.json",
                        "@context": f"{name}.schema.json",
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
    return {"$schema": f"{name}.schema.json", "@context": f"{name}.schema.json",
            "@id": "https://example.org/instance", **doc}


IRI_BASE = "https://w3id.org/oo-ld/schemas"
GENID = "https://schemas.oo-ld.org/.well-known/genid/"
# a pointer into a schema is a path: `properties` and `$defs` are how the path is written,
# while `items` says which thing it reaches and keeps two pointers apart
POINTER_NOISE = ("properties", "$defs", "definitions")


def named_namespaces(graph, context: dict) -> dict:
    """Names for the namespaces a serializer would otherwise call ns1, ns2 ...

    A term of this library is a JSON Pointer into a schema, and Turtle cannot write a slash
    in a local name, so the leading part of the pointer becomes a namespace of its own,
    which no context declares. Naming it after the prefix its schema does declare, plus the
    part of the pointer that carries meaning, keeps a reading legible and stable:
    `chem_components:` rather than `ns4:`, and the same name in every regeneration.
    """
    from rdflib import URIRef  # noqa: PLC0415

    declared = namespaces(context)
    found: dict[str, str] = {}
    for term in sorted({str(t) for triple in graph for t in triple
                        if isinstance(t, URIRef)}):
        if term.startswith(GENID):
            found[GENID] = "genid"
            continue
        namespace = term[: max(term.rfind("/"), term.rfind("#")) + 1]
        if not namespace or namespace in declared or namespace in found:
            continue
        module = re.fullmatch(rf"{re.escape(IRI_BASE)}/([^/]+)/[^/]+/", namespace)
        if module:
            # the module's own space, where its schemas are the classes
            candidate = module[1]
        else:
            base = max((i for i in declared if namespace.startswith(i)), key=len,
                       default=None)
            if base is None:
                # a namespace the data brings with it rather than the schema: the instances
                # here are documentation, and `ex:` is what a reader expects to see for them
                host, _, path = namespace.partition("//")[2].partition("/")
                head = "ex" if "example." in host else host.split(".")[0]
                candidate = "_".join([head, *[s for s in path.strip("/").split("/") if s]])
            else:
                path = [s for s in namespace[len(base):].strip("/").split("/") if s]
                rest = [s for s in path if s not in POINTER_NOISE] or path
                candidate = "_".join([declared[base], *rest])
        candidate = re.sub(r"[^A-Za-z0-9_]", "_", candidate)
        while candidate in found.values() or candidate in declared.values():
            candidate += "_"
        found[namespace] = candidate
    return found


def write_rdf(module: str, name: str, schema_files: list[Path], instance: Path | dict) -> int:
    """Render the instance to Turtle under each mapping set, for the schema page tabs.

    Needs pyld and rdflib. When they are unavailable the RDF tabs are simply omitted,
    so a plain `python scripts/build_docs.py` still works.
    """
    try:
        from pyld import jsonld  # noqa: PLC0415
        from rdflib import Graph, URIRef  # noqa: PLC0415
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
        payload = {**doc, "@context": inline_scoped(
            promote(base_ctx, schemas, set_id), schema_files[-1], set_id)}
        try:
            # canonical quads (URDNA2015): stable blank node labels and a stable
            # order, so a regenerated reading is byte-identical and check can diff it
            nq = jsonld.normalize(payload, {"algorithm": "URDNA2015",
                                            "format": "application/n-quads"})
            # rdflib gives every parsed blank node a fresh random identifier and orders
            # siblings by it, so the canonical labels are turned into IRIs first: the
            # reading then comes out byte-identical every time
            nq = re.sub(r"_:(c14n\d+)",
                        lambda m: f"<https://schemas.oo-ld.org/.well-known/genid/{m[1]}>", nq)
            graph = Graph().parse(data=nq, format="nquads")
            declared = {**namespaces(base_ctx), **namespaces(payload["@context"])}
            for iri, prefix in declared.items():
                graph.bind(prefix, iri)
            for iri, prefix in named_namespaces(graph, payload["@context"]).items():
                graph.bind(prefix, iri)
            # rdflib invents ns1, ns2 ... for whatever is left, numbered in the order
            # it meets them, which differs between machines. Resolving every term in
            # sorted order first pins that numbering to the data, not to the traversal.
            for term in sorted({str(t) for triple in graph for t in triple
                                if isinstance(t, URIRef)}):
                try:
                    graph.namespace_manager.compute_qname(term)
                except Exception:  # noqa: BLE001 - a term with no split point stays full
                    pass
            ttl = graph.serialize(format="longturtle")
        except Exception as exc:  # a broken mapping should fail loudly in CI, not here
            print(f"  ! {module}/{name} [{label}]: {exc}")
            continue
        (out_dir / f"{name}.{label}.ttl").write_text(ttl.strip() + "\n",
                                                     encoding="utf-8", newline="\n")
        (out_dir / f"{name}.{label}.mmd").write_text(
            mermaid(graph, {**own(terms(base_ctx)), **own(terms(payload["@context"])), **LABELS},
                    {**namespaces(base_ctx), **namespaces(payload["@context"])}) + chr(10),
            encoding="utf-8", newline=chr(10))
        written += 1
    return written


def write_module_versions() -> int:
    """Publish, for each module, the documentation snapshot that carries each of its
    versions, so a page can offer the reader a module version rather than a site version."""
    index = read(GENERATED / "versions.json") if (GENERATED / "versions.json").exists() else {}
    catalogue = {}
    for module in module_names():
        if not any((MODULES / module).glob("*.schema.json")):
            continue
        entries = [{"label": ".".join(e["module"].split(".")[:2]), "docs": e["docs"]}
                   for e in index.get(module, [])]
        entries.append({"label": "dev", "docs": "dev"})
        catalogue[module] = {"current": module_version(module), "versions": entries}
    (DOCS / "module-versions.json").write_text(json.dumps(catalogue, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    return len(catalogue)


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
        for directory in (DOCS / module / exact, DOCS / module / line):
            (directory / "index.md").write_text("\n".join(listing) + "\n",
                                                encoding="utf-8", newline="\n")

        # A manifest at the version directory itself. The schemas are files and resolve on
        # their own; the module is only ever this listing, so without it a conformance IRI
        # dereferences to nothing.
        meta_file = MODULES / module / "module.json"
        manifest = {
            "@context": {
                "dcterms": "http://purl.org/dc/terms/",
                "owl": "http://www.w3.org/2002/07/owl#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "title": "dcterms:title",
                "description": "dcterms:description",
                "version": "owl:versionInfo",
                "schemas": {"@id": "rdfs:member", "@type": "@id"},
            },
            "@id": f"https://w3id.org/oo-ld/schemas/{module}/{line}",
            "title": f"{title} {line}",
            "version": exact,
            "description": read(meta_file).get("scope", "") if meta_file.exists() else "",
            "schemas": [f.name for f in files if f.name.endswith(".schema.json")],
        }
        # Both directories: an exact release is a citable artefact of its own, and a reader
        # who pinned it should find the same description there.
        for directory in (DOCS / module / exact, DOCS / module / line):
            (directory / "index.json").write_text(json.dumps(manifest, indent=2) + "\n",
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
            built = synth_instance(name, schema, inherited(schema, sf))
            if not built:
                # a schema that can no longer be filled from its own examples must not keep
                # serving the instance and readings of an earlier run
                for stale in (GENERATED / module).glob(f"{name}.*"):
                    if stale.suffix in (".json", ".ttl", ".mmd"):
                        stale.unlink()
                continue
            gen_dir = GENERATED / module
            gen_dir.mkdir(parents=True, exist_ok=True)
            (gen_dir / f"{name}.instance.json").write_text(
                json.dumps(built, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")
            rdf += write_rdf(module, name, lineage, built)

    mappings = stage_mappings()
    write_module_versions()
    print(f"published {published} schema files, {rdf} RDF readings, "
          f"{mappings} mapping sets")


if __name__ == "__main__":
    main()
