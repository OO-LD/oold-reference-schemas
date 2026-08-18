# OO-LD reference schemas

Modular reference schemas in [OO-LD](https://oo-ld.org/latest/spec/): one document that
is at once a valid JSON Schema and a referenceable JSON-LD context, so structure and semantics
stay in a single artefact that ordinary developer tooling can consume.

Each module is versioned and conformable on its own, so a consumer can adopt `quantities`
without taking on anything domain-specific. The neutral modules (quantities, datasets,
processes, measurement, time) are as relevant to engineering, manufacturing and trade as to
research; domain modules sit on top of them.

> Status: first draft, put up for discussion rather than settled. The module structure below
> is drawn wide enough to give every recurring pattern a home, but which modules exist, what
> belongs in each and how their terms are mapped are all open. Only representative examples are
> filled in, so the approach, the representations and the tooling can be discussed first.

## Modules

| module | scope | status |
|---|---|---|
| [`quantities`](modules/quantities) | QuantityValue, units, uncertainty, value specifications | example |
| [`datasets`](modules/datasets) | Dataset, Distribution, storage modes, tabular data, data services | planned |
| [`processes`](modules/processes) | processes and chains, inputs/outputs, plans, recipes, workflows | planned |
| [`measurement`](modules/measurement) | measurement, assay, calibration, measurement datum | planned |
| [`time`](modules/time) | temporal regions, durations, process start/end, temporalized qualities | planned |
| [`qualities`](modules/qualities) | qualities, dispositions, realizable entities, roles | planned |
| [`materials`](modules/materials) | composition, microstructure, material properties | planned |
| [`devices`](modules/devices) | device specification, settings, identifiers | planned |
| [`simulation`](modules/simulation) | simulated entities, digital counterparts, computation provenance | planned |
| [`foundations`](modules/foundations) | upper-ontology structure and object-property inventories | planned |

## One syntax, tiered semantics

A schema carries one syntactical shape and several RDF readings:

- the default `@context` holds the **consensus** mapping, the reading a module takes as
  agreed: a general vocabulary (QUDT, schema.org, DCAT, PROV, CSVW) in a neutral module, or the
  domain's own ontology in a domain module;
- every further community mapping is a per-term synonym under `x-oold-context`, tagged with an
  SSSOM `mapping_set_id` and the exact ontology version it was validated against;
- selecting a mapping set promotes those synonyms into the context, so the **same instance
  document** exports as EMMO-flavoured or PMDco-flavoured RDF without being rewritten.

See [`modules/quantities`](modules/quantities) for the worked example and
[`modules/quantities/Time.instance.json`](modules/quantities/Time.instance.json) for an instance that round-trips
losslessly under all three readings.

## Layout

```
modules/   the source: one directory per module, instances beside the schemas
examples/  packaging examples (RO-Crate, .eln)
generated/ derived artefacts: RDF readings, ontology labels
docs/      the site: hand-written pages, seeded schema pages, mapping sets
scripts/   generation, versioning and release tooling
```

Published at [schemas.oo-ld.org](https://schemas.oo-ld.org/), where a conformance IRI answers
with the module manifest, listing the version and the schemas it holds, and each schema is
dereferenceable at its own versioned path.

## Validation

Schemas, instances and their RDF round-trip are checked with the upstream OO-LD validator
rather than a copy maintained here (see
[oold-schema#91](https://github.com/OO-LD/oold-schema/issues/91)):

```bash
make validate
make check
```

## Contributing

`modules/` is the source. The documentation pages, the SSSOM mapping sets and the RDF readings
are generated from it, so a schema is edited in one place.

1. Add `modules/<module>/<Name>.schema.json`, and an instance beside it so CI can round-trip it.
2. Run `make generate`. It seeds the schema's documentation page and the navigation entry.
3. Write the prose on that page: what the schema decides, and why a mapping is a close match
   rather than an exact one. A seeded page is never overwritten.
4. Run `make check` and `make validate` before opening a pull request.

Versions are computed rather than typed: `make bump` raises each schema and its module by the
level of what changed since the last release. The full guide is
[schemas.oo-ld.org/contributing](https://schemas.oo-ld.org/contributing/).

## Licence

Schemas and specification text CC-BY-4.0, code MIT. See [LICENSE](LICENSE).

## Funding

These reference schemas are a domain adaptation of OO-LD for science and engineering, funded by
the European Union's Horizon Europe research and innovation programme under grant agreement
No. 101293545, [MaterialsCommons](https://materialscommons.eu/). The generic OO-LD framework is
funded separately; see [OO-LD funding](https://github.com/OO-LD#funding).
