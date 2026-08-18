# OO-LD Reference Schemas

Structure travels well. A CSV, a JSON file or a Parquet table opens anywhere, and two labs can
exchange files all day without either of them learning anything about the other's data.

Meaning does not travel. The same quantity, process or dataset is modelled differently by every
ontology, every schema language and every information system, and the differences are rarely
disagreements about the science. They are disagreements about representation: whether a value
and its unit sit on one node or two, whether a duration is a quantity or a temporal region,
whether a unit is a class or an individual.

The usual response is to pick an ontology. That works inside one project and fails at its
boundary, because picking one excludes everyone aligned with another. The boundary is often a
domain boundary: a measured quantity crosses from a laboratory to an engineering calculation to
a product declaration, and each side has its own vocabulary for the same number. Ontology
alignment is supposed to fix that afterwards, but alignment between whole ontologies is a
research problem, while the practical need is much smaller: make *this* schema readable by
*those* communities.

## One document, two standards

An [OO-LD](https://oo-ld.org/latest/spec/) document is at once a valid JSON Schema and a
referenceable JSON-LD context. Nothing new is invented; two existing standards are put in one
file.

That single move has an outsized effect. The same artefact validates an instance, generates
typed code and a form, and expands that instance to RDF. There is no separate context to keep in
sync, no generated copy that drifts, and no build step between the developer's view and the
semantic view. A developer who never says the word "ontology" still produces linked data.

## One syntax, several readings

Where communities genuinely differ, a schema here does not pick a winner. The default context
carries the reading its module takes as agreed, every further community mapping rides along as a
per-term synonym, and selecting a mapping set promotes those synonyms so the *same instance
document* exports as EMMO-flavoured or PMDco-flavoured RDF. Nothing about the instance changes,
only its RDF reading. Terms a community has no term for keep the consensus reading rather than
failing, so a partial alignment stays usable.

Because the synonyms carry SSSOM metadata, the mappings round-trip to a standard mapping set:
they can be reviewed, cited and reused by people who never open a JSON Schema.

[Walk through a worked example](how-it-works.md){ .md-button .md-button--primary }
[How the mapping works](mapping-sets.md){ .md-button }

## What is here

Schemas are grouped into modules, each versioned and conformable on its own, so a consumer in
civil engineering, manufacturing or trade can adopt `quantities` without taking on anything
domain-specific. Domain modules sit on top of neutral ones rather than replacing them. See
[Modules](modules/) for the full set and their status.

Modules and schemas are published at versioned, dereferenceable paths, so an identifier
answers with the artefact rather than with a page about it:

```
https://w3id.org/oo-ld/schemas/quantities/0.1
  -> the module manifest: title, version and the schemas it holds

https://w3id.org/oo-ld/schemas/quantities/0.1/QuantityValue.schema.json
  -> the schema itself
```

Because structure and semantics sit in one document, the schemas are also the source for
generated assets: typed code bindings, schema-driven user interfaces, API descriptions, and the
SSSOM mapping sets themselves.

## What this is not

It is not an ontology, and it does not compete with one. Ontologies define what things are, with
far more expressivity than a schema can carry. These schemas describe how data is shaped and
which ontology terms that shape corresponds to, in the subset that survives a round-trip through
ordinary tooling. Where an ontology's structure cannot be reached by term mapping, that is stated
plainly rather than papered over.

## Status

First draft, put up for discussion rather than settled. The module structure is drawn wide
enough to give every recurring pattern a home, but which modules exist, what belongs in each
and how their terms are mapped are all open. `quantities` is the worked example; the other
modules carry a scope note and are open for contribution, in any domain that shares the
pattern.

Everything published here is checked in CI: schemas against the OO-LD meta-schema, instances
against their schemas, and every mapping-set reading for a lossless round-trip through RDF.

## Funding

These reference schemas are a domain adaptation of OO-LD for science and engineering, funded by
the European Union's Horizon Europe research and innovation programme under grant agreement
No. 101293545, [MaterialsCommons](https://materialscommons.eu/). The generic OO-LD framework is
funded separately; see [OO-LD funding](https://github.com/OO-LD#funding).
