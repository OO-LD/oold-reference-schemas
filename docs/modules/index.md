# Modules

Schemas are grouped into modules. Each is versioned and conformable on its own, so a consumer
can adopt one without taking on the others, and a module can later move to its own repository as
a redirect rather than a breaking change.

Modules are listed even while empty: the structure is meant to give every recurring pattern a
home, so contributors know where a new schema belongs rather than inventing a place for it. The
cut below is a first draft. Which modules exist and where a boundary falls are open questions,
and moving a schema between modules is cheaper now than after the inventory is filled in.

| module | scope | status |
|---|---|---|
| [`quantities`](quantities/quantityvalue/) | QuantityValue, units, uncertainty, value specifications (scalar, fraction, categorical), ratios | worked example |
| `datasets` | Dataset, Distribution, storage modes, tabular data, data services | planned |
| `processes` | processes and chains, inputs and outputs, plans, recipes, participants, workflows | planned |
| `measurement` | measurement, assay, calibration, measurement datum | planned |
| `time` | temporal regions, durations, process start and end, temporalized qualities | planned |
| `qualities` | qualities, dispositions, realizable entities, roles | planned |
| `materials` | chemical composition, structure and microstructure, material properties | planned |
| `devices` | device specification, settings and setpoints, identifiers | planned |
| `simulation` | simulated entities, digital counterparts, computation provenance | planned |
| `foundations` | upper-ontology structure, module overviews, object-property inventories | planned |

`time` is about process time: temporal regions, durations, temporalized qualities. It is not the
`Time` quantity kind, which lives in `quantities`. The two are different things that share a
word, and they must not be mapped onto each other.

Conformance IRIs follow `https://w3id.org/oo-ld/modules/<module>/<version>`; see
[Conformance](../conformance.md).

## Reading a module's pages

Each module holds one page per schema: what it is for, the schema itself, how each of its
terms reads in RDF, and the decisions behind it. The schema files are embedded from the
repository, so a page shows what is published rather than a description of it.

Schemas are listed by inheritance: a subschema appears under the schema it extends, because
that is how its terms and mappings are inherited too.

- **`quantities`**
    - [QuantityValue](quantities/quantityvalue/), a number with a unit and optional uncertainty
        - [Time](quantities/quantityvalue/time/), restricted to time units, with its unit individuals aliased
        - [Length](quantities/quantityvalue/length/), restricted to length units
            - [Diameter](quantities/quantityvalue/length/diameter/), `Length` across a round object

Published files for a module are listed at its versioned path, for example
[`quantities/0.1/`](/quantities/0.1/).
