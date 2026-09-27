# quantities-qudt

One schema per QUDT quantity kind, each restricting `QuantityValue` to the units of that
kind. 942 schemas, generated rather than written.

- status: generated
- owner: unassigned
- conformance IRI: assigned with the module's first release
- extends: [`quantities`](../quantities/), by published IRI

| file | what it is |
|---|---|
| `module.json` | the module's own metadata, including the version it publishes under |
| `Length.schema.json` | a quantity kind: pins the permitted units, defaults to the SI unit, aliases the unit individuals |
| `Diameter.schema.json` | a kind that narrows another kind and inherits its units |
| `<QuantityKind>.schema.json` | the same pattern, once per QUDT quantity kind |

Every member extends
`https://w3id.org/oo-ld/schemas/quantities/0.2/QuantityValue.schema.json`, directly or
through another kind, so the value, unit and uncertainty terms are the curated module's and
are not restated here.

## Generated, not curated

This module is the first one here that is derived wholesale from an external vocabulary
rather than written. It is 942 schemas against the 15 the rest of the library holds, so it
is worth saying plainly what that changes and what it does not.

It does not change the shape. A member looks like a curated quantity kind, because it is
built to the same template: a class term mapped to its quantity kind, a unit enumeration
whose aliases are mapped to QUDT unit individuals, a default unit, one worked example.

What it changes is density. Nobody will write prose on 942 pages, so most of these pages
are the generated rendering and nothing else. That is the honest state of a generated
module, and it is visible rather than hidden: a reader who opens one sees the schema, its
lineage and its readings, with no commentary claiming more understanding than went into it.

`make generate` takes about two and a half minutes with this module present and
`make check` about twenty, most of it the documentation build. Both pass. If that becomes
the wrong trade later, the cheapest lever is to document a named subset rather than every
member, which needs a filter in `build_docs.py` and `build_pages.py` and no change to the
schemas.

## Where it comes from

The class of each schema is its QUDT quantity kind, and the name follows from it: the schema
for `http://qudt.org/vocab/quantitykind/Length` is `Length.schema.json`. That naming is also
what keeps the module free of collisions. The source labels several distinct kinds the same
way, calling both `Volume` and `CartesianVolume` "Volume", and the quantity kind separates
them where the label does not.

Unit aliases are mapped to QUDT unit IRIs, taken from the OpenSemanticLab unit items where
those record one, and otherwise looked up in the QUDT 3.1.5 unit vocabulary by UCUM code or
through `qudt:scalingOf` and `qudt:prefix`. Nothing is derived by spelling a QUDT IRI that
was not found: a unit that no lookup reaches is reported below rather than guessed at.

## Known gaps

These are properties of the source data. They are recorded here so nobody has to rediscover
them, and two of them are worth an upstream fix rather than a workaround.

### 25 unit entries were dropped, and each one hid a distinct unit

The source gives two different units the same alias inside one enumeration. A JSON-LD term
has to be unique, so only the first can be mapped and the second is not listed.

This is not harmless repetition. All 25 pairs resolve to two different QUDT unit
individuals, so every drop removed a unit the enumeration could otherwise have offered:

- Same unit under two QUDT spellings, where the loss is cosmetic:
  `kelvin_meter_per_watt` covered both `unit:M-K-PER-W` and `unit:K-M-PER-W`,
  `per_meter_squared_per_second` both `unit:PER-M2-SEC` and `unit:PER-SEC-M2`.
- A reduced and an unreduced form of the same unit, where the loss is still cosmetic but the
  source clearly meant both: `per_meter` covered `unit:PER-M` and `unit:M-PER-M2`,
  `newton_per_meter` covered `unit:N-PER-M` and `unit:N-M-PER-M2`.
- Genuinely different units sharing an alias, where the loss is real:
  `Conductance.siemens` and `Admittance.siemens` each covered `unit:S` and `unit:MHO`,
  `PlaneAngle.grade` covered `unit:GON` and `unit:GRAD`, and `Dimensionless.unknown`
  covered `unit:FRACTION` and `unit:SUSCEPTIBILITY_ELEC`, which are not the same quantity at
  all.

The last group is the one to fix upstream. The alias is derived from the dimensional
reduction of the unit, which cannot distinguish a fraction from an electric susceptibility.

### 6 kinds have no QUDT quantity kind

`LengthSpecificLeakRate`, `AreaSpecificLeakRate`,
`GasPressureDependenceOfThermalConductivity`, `GasPressureDependentFlowCoefficient`,
`ThermalConductivitySlope` and `FlowCoefficient` carry no ontology match in the source. They
keep the name it gave them, and their class term is mapped into this module's own IRI space,
the way the `materials` module names terms no agreed vocabulary covers.

### 77 unit aliases have no QUDT unit IRI

They are composed or prefixed units carrying no UCUM code, such as `nano_becquerel` and
`mega_pascal_meter`. They keep their place in the enumeration and their term is mapped into
this module's IRI space, so an instance can still name the unit and a consumer can still see
that it is not a QUDT individual.

## Spelling: `meter` here, `metre` in `quantities`

The curated `quantities` module spells its unit aliases the international way, `metre` and
`kilo_metre`. This module keeps the source's American spelling, `meter` and `kilo_meter`.

Both map to the same QUDT unit IRIs, so nothing differs in RDF and an instance of either
module reads the same once expanded. What differs is the JSON key, which matters to anyone
writing instances against both modules or generating bindings from them. Left as it is
deliberately: changing it would mean editing the generator's source vocabulary, and which
spelling the library should standardise on is a maintainer's decision rather than a
generator's.
