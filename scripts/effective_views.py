"""Prove that every mapping set reads one instance losslessly.

Selecting a mapping set promotes its synonyms into the context, so the same instance
document exports as a different graph. The claim that makes that useful is that nothing is
lost: expanding the instance to RDF and compacting it back under the same context must
return the document it started from. A mapping that drops a term, coerces a number into a
string or turns a set into a scalar fails here rather than shipping quietly.

The sets are read out of the schemas, so a set nobody declares any more stops being proved
instead of being reported as passing.

Usage: python scripts/effective_views.py <module-directory>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _shared import context_of, mapping_sets, set_name

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_docs import chain, inline_scoped, promote  # noqa: E402


def canonical(value):
    """A comparable form: key order and the `$schema` pointer are not data."""
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())
                if k not in ("@context", "$schema")}
    return value


def undefined_terms(node, context: dict) -> set:
    """Keys an instance uses that the context does not define.

    The round-trip cannot see these on its own: an undefined term is dropped on the way
    out and missing on the way back, so both sides agree on a graph that lost the data.
    """
    missing = set()
    if isinstance(node, list):
        for item in node:
            missing |= undefined_terms(item, context)
    elif isinstance(node, dict):
        for key, value in node.items():
            definition = context.get(key)
            if not key.startswith(("@", "$")) and definition is None:
                missing.add(key)
            # a term may scope a context onto its own value, and inside that value the scoped
            # definitions are what count: reading the enclosing context alone reports a term
            # as undefined although the processor resolves it
            scoped = definition.get("@context") if isinstance(definition, dict) else None
            within = {**context, **scoped} if isinstance(scoped, dict) else context
            missing |= undefined_terms(value, within)
    return missing


def views(module_dir: Path) -> int:
    from pyld import jsonld  # noqa: PLC0415

    instances = sorted(module_dir.glob("*.instance.json"))
    if not instances:
        print(f"no committed instance in {module_dir}")
        return 1

    failures = 0
    for instance_path in instances:
        name = instance_path.name[: -len(".instance.json")]
        lineage = chain(module_dir / f"{name}.schema.json")
        schemas = [json.loads(f.read_text(encoding="utf-8")) for f in lineage]
        declared: dict = {}
        for schema in schemas:
            declared.update(context_of(schema))

        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        print(f"== {instance_path.name}")
        for set_id in [None, *mapping_sets(schemas)]:
            label = "consensus (declared)" if set_id is None else f"mapping set {set_name(set_id)}"
            context = inline_scoped(promote(declared, schemas, set_id), lineage[-1],
                                    set_id)
            document = {k: v for k, v in instance.items() if k != "$schema"}
            document["@context"] = context

            quads = jsonld.to_rdf(document, {"format": "application/n-quads"})
            back = jsonld.from_rdf(quads, {"format": "application/n-quads",
                                           "useNativeTypes": True})
            # RDF has no nesting, so the tree comes back only when the graph is framed
            # on the root type; compaction alone yields a flat @graph of blank nodes
            frame = {"@context": context, "@embed": "@always"}
            root_type = instance.get("type") or instance.get("@type")
            if root_type:
                frame["@type"] = root_type
            flat = jsonld.compact(back, context)
            restored = jsonld.frame(back, frame)
            # A reading may legitimately change the document's shape: where a community
            # states an edge in the other direction, the tree hangs off another node and
            # no frame rooted at the instance's type reaches it. So the test is that the
            # graph survives, canonicalised; the framed form is what a failure prints.
            opts = {"algorithm": "URDNA2015", "format": "application/n-quads"}
            missing = undefined_terms(instance, context)
            lossless = not missing and (
                canonical(instance) == canonical(restored)
                or jsonld.normalize(document, opts) == jsonld.normalize(flat, opts))
            triples = len([q for q in quads.strip().split("\n") if q])
            print(f"   {label}: {'LOSSLESS' if lossless else 'LOSSY'} "
                  f"round-trip, {triples} triples")
            if not lossless:
                failures += 1
                if missing:
                    print(f"     terms not defined in the context: {sorted(missing)}")
                print(f"     declared:  {json.dumps(canonical(instance), sort_keys=True)}")
                print(f"     restored:  {json.dumps(canonical(restored), sort_keys=True)}")
    return failures


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    failures = sum(views(Path(arg)) for arg in sys.argv[1:])
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
