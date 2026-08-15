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
| [`datasets`](schemas/datasets) | Dataset, Distribution, storage modes, tabular data, data services | planned |
| [`processes`](schemas/processes) | processes and chains, inputs/outputs, plans, recipes, workflows | planned |
| [`measurement`](schemas/measurement) | measurement, assay, calibration, measurement datum | planned |
| [`time`](schemas/time) | temporal regions, durations, process start/end, temporalized qualities | planned |
| [`qualities`](schemas/qualities) | qualities, dispositions, realizable entities, roles | planned |
| [`materials`](schemas/materials) | composition, microstructure, material properties | planned |
| [`devices`](schemas/devices) | device specification, settings, identifiers | planned |
| [`simulation`](schemas/simulation) | simulated entities, digital counterparts, computation provenance | planned |
| [`foundations`](schemas/foundations) | upper-ontology structure and object-property inventories | planned |

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
schemas/   reference schemas, one directory per module; instances sit beside them
examples/  packaging examples (RO-Crate, .eln)
docs/      the site: hand-written pages, seeded schema pages, conformance
           IRIs, mapping sets, pinned ontologies
scripts/   generation, versioning and release tooling
```

Published at [schemas.oo-ld.org](https://schemas.oo-ld.org/), where each schema is also
dereferenceable at its versioned path, so a conformance IRI resolves to the schema itself and not
only to a page about it.

## Validation

Schemas, instances and their RDF round-trip are checked with the upstream OO-LD validator
rather than a copy maintained here (see
[oold-schema#91](https://github.com/OO-LD/oold-schema/issues/91)):

```bash
make validate
make check
```

## Licence

Schemas and specification text CC-BY-4.0, code MIT. See [LICENSE](LICENSE).
