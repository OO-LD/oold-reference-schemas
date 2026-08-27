---
hide:
  - toc
---

# Composition

What every composition is: a list of components, each a constituent with an amount. Both are
required here, and what a constituent may be is what the two subschemas fix,
[ChemicalComposition](chemicalcomposition/) and [MaterialComposition](materialcomposition/): a
chemical species there, another material here. Both spell the term `constituent`, and each
scopes its own context onto it, so one JSON key carries two predicates without either schema
restating the list.

{{ oold_schema_meta_data("materials", "Composition") }}

{{ oold_schema_renderer("materials", "Composition") }}

The amount references `quantities/MassFraction` at its published IRI. The quantity, not the
unit, decides that a percentage is by mass, so the same `percent` reads as `emmo:WeightPercent`
here and would read as `emmo:VolumePercent` under a volume fraction.

Terms in a schema's own IRI space are placeholders for a vocabulary that is not agreed yet, not
a third ontology. They carry no axioms, they dereference to the schema that defines them, and
each records in `x-oold-context` what it means in EMMO and in PMDco. Every schema declares its
own prefix, named after itself: the contexts are merged flat, so a shared prefix name would
collide and the pointers would land in the wrong file.
