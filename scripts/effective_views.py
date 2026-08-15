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
from build_docs import chain, promote  # noqa: E402


def canonical(value):
    """A comparable form: key order and the `$schema` pointer are not data."""
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())
                if k not in ("@context", "$schema")}
    return value


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
            context = promote(declared, schemas, set_id)
            document = {k: v for k, v in instance.items() if k != "$schema"}
            document["@context"] = context

            quads = jsonld.to_rdf(document, {"format": "application/n-quads"})
            back = jsonld.from_rdf(quads, {"format": "application/n-quads",
                                           "useNativeTypes": True})
            restored = jsonld.compact(back, context)
            lossless = canonical(instance) == canonical(restored)
            triples = len([q for q in quads.strip().split("\n") if q])
            print(f"   {label}: {'LOSSLESS' if lossless else 'LOSSY'} "
                  f"round-trip, {triples} triples")
            if not lossless:
                failures += 1
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
