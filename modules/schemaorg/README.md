# schemaorg

The schema.org class hierarchy as OO-LD schemas: 901 generated Types plus the 18
hand-authored DataType leaves they reference.

- status: draft
- owner: unassigned
- conformance IRI: `https://w3id.org/oo-ld/schemas/schemaorg/0.1`

Standalone. The module mirrors an external vocabulary instead of modelling a domain, so
nothing else in this repository builds on it and it declares no mappings.

| file | what it is |
|---|---|
| `module.json` | the module's own metadata, including the version it publishes under |
| `Thing.schema.json` | the root class, carrying the shared vocabulary every other schema inherits |
| `<Class>.schema.json` | one schema per schema.org Type, 901 of them |
| `Text.schema.json`, `Number.schema.json`, ... | the 18 DataType leaves the Types reference |

## How these were generated

From [OO-LD/schemaorg-parsing](https://github.com/OO-LD/schemaorg-parsing), against the
current schema.org JSON-LD dump:

```bash
python scripts/generate.py partial --all --no-partial --out schemas/generated
```

Three fields were rewritten on the way in, to match how this repository identifies a
schema. Nothing else was touched.

| field | value here |
|---|---|
| `$schema` | `https://oo-ld.org/latest/meta/oold-meta-schema.json` |
| `$id` | the bare file name, as in every other module |
| `x-oold-uuid` | UUID5 of `https://w3id.org/oo-ld/schemas/schemaorg/<file>` in the URL namespace |
| `x-oold-version` | the module version at the time of import |

Regenerating the module means running the generator again and reapplying those four
fields. The schemas are not edited here: a fix belongs in the generator.

## What the schemas say

- Every class carries `allOf` over all of its schema.org superclasses, so a class with
  several parents inherits from each of them.
- A property is an array unless schema.org makes it singular, and every array term
  declares `@container: "@set"` so a single-element array survives an RDF round trip.
- A range over entity classes is an IRI reference typed by `x-oold-range`. A range over
  value types embeds the object. A range over DataTypes references the leaf schema.
- An `Enumeration` subclass lists its member instances under `$defs/member`, and a
  property whose range is entirely enumerations references that list.
