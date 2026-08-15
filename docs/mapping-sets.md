# Mapping sets

Community readings of the schemas, expressed as per-term synonyms in `x-oold-context`. They
round-trip to SSSOM, so a mapping set can be reviewed, cited and reused outside OO-LD. The sets
are generated from the schemas and published as SSSOM TSV at the identifier each
`mapping_set_id` names, so nothing about a mapping is maintained twice.

| mapping set | vocabulary | notes |
|---|---|---|
| `consensus` | whatever the module takes as agreed, general vocabularies here | the reading with nothing selected |
| `schemaorg` | schema.org | broad-web consumers |
| `pmdco` | PMDco / OBO | holds `obo:` terms (OBI, IAO, UO) as well as `pmd:` ones, which is why selection is by set rather than by namespace |
| `emmo` | EMMO | validated against the 1.0.4 branch snapshot, commit 1249265 |

Every synonym carries `object_source` and `object_source_version`, so a mapping states exactly
which ontology version it was checked against. A pin may name a commit or snapshot rather than
only an `owl:versionIRI`: the published `w3id.org/emmo/1.0.4` build was stale relative to its
own branch when the EMMO mappings were validated.

## How a mapping is carried

1. **Consensus.** The default `@context` maps each term to the vocabulary the module takes as
   agreed, which is the reading a consumer gets without asking for anything. Neutral modules
   use general, widely deployed vocabularies (QUDT for quantities, DCAT and CSVW for datasets,
   PROV for provenance, schema.org where it fits). A domain module can put its domain ontology
   in that position instead: consensus is a position in the tiering, not a fixed vocabulary.
2. **Community synonyms.** Every further mapping lives under `x-oold-context`, per term, as a
   promotable JSON-LD term definition plus an `x-oold-sssom` block. Each synonym records the mapping
   set it belongs to, the ontology it targets and the ontology version it was validated against.
3. **Selection.** Choosing a mapping set promotes its synonyms into the context, producing an
   effective context that differs from the declared one only in what its terms expand to. The
   instance document is untouched; only its RDF reading changes.

The same instance exports as EMMO-flavoured or PMDco-flavoured RDF, and both are exact readings
of one document rather than approximations of each other. Terms with no synonym in the selected
set fall back to the consensus mapping, so a partial alignment stays usable.

## Limits

- **Structure is bridged in the document, not in the graph.** A mapping set decides which graph
  a document produces, including a differently shaped one, as
  [Shapes, not only names](#shapes-not-only-names) shows. It cannot reshape a graph that already
  exists, so arriving RDF is framed with the schema first. Where a schema states a term as a
  literal and another community needs a node, the correspondence belongs to the schema that
  carries the node: this one keeps its consensus reading, and the pair is recorded in SSSOM.
- **Vocabulary coercion needs guards.** Value-level aliases use `@type: @vocab`, which mints an
  IRI from an unknown string. A schema that uses it constrains the values with an `enum`.
- **A mapping is only as current as its pin.** Synonyms carry the exact ontology version they
  were checked against, because an upstream release can move a term out from under a mapping.

## Shapes, not only names

Communities disagree about structure as well as vocabulary. EMMO models a quantity value as a
node carrying a numerical part; QUDT puts the number on the quantity itself. A mapping set can
carry that difference too, because JSON structure is not semantics: a term defined as `@nest`
groups keys in the document and contributes nothing to the graph.

A synonym fragment may therefore carry `@nest`, and selection promotes it like any other term
definition. The same document then produces either shape:

```json
{ "@id": "https://example.org/m1", "value": { "numerical": 12.7 } }
```

| selected | graph |
|---|---|
| the schema's own context, `value` an object property | `m1 emmo:hasQuantityValuePart _:b0`, `_:b0 emmo:hasNumericalValue 12.7` |
| a set defining `value` as `@nest` and `numerical` as `qudt:value` | `m1 qudt:value 12.7` |

The reverse import works the same way: a schema whose `value` is an object declares, in its
mapping set for the flat vocabulary, that `qudt:value` nests under `value`. Flat data then
compacts into the nested document that schema expects.

### What has to be a graph operation

A context can decide which graph a document produces. It cannot rewrite a graph you already
have: `@nest` may only point at a term that is itself `@nest`, and a processor rejects anything
else with `invalid @nest value`. Dropping an intermediate node and reattaching its literal is an
assertion, not a reformatting.

Arriving RDF is therefore framed first, into the document shape the schema expects, and read
from there. The frame follows from the schema, so this is a build step rather than a decision:

```
nested RDF  ->  frame with the schema  ->  document  ->  read under a mapping set  ->  either graph
```

Compaction alone does not do it: it yields a flat list of node objects, with the inner node
still separate. What makes the flat reading legitimate is that the schema declares the
correspondence, so the assertion carries the provenance of a mapping rather than appearing from
nowhere.

## Crosswalks between communities

Two sets that map the same term give a mapping between those two communities, chained through
the term they share. They are derived rather than authored, and are listed together on the
[Crosswalks](mappings/crosswalks/index.md) page along with the rule that decides which chains
survive.
