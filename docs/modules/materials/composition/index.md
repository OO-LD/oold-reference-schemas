---
hide:
  - toc
---

# Composition

What every composition shares: a list of components, each carrying an amount. What differs is
the constituent, so that is left to the two subschemas,
[ChemicalComposition](chemicalcomposition/) and [MaterialComposition](materialcomposition/).

{{ oold_schema_meta_data("materials", "Composition") }}

{{ oold_schema_renderer("materials", "Composition") }}

The amount mirrors `quantities/MassFraction` rather than referencing it, because a cross-module
`$ref` does not resolve until that module is released. The quantity, not the unit, decides that
a percentage is by mass, so the same `percent` reads as `emmo:WeightPercent` here and would read
as `emmo:VolumePercent` under a volume fraction.

Terms in a schema's own IRI space are placeholders for a vocabulary that is not agreed yet, not
a third ontology. They carry no axioms, they dereference to the schema that defines them, and
each records in `x-oold-context` what it means in EMMO and in PMDco. Every schema declares its
own prefix, named after itself: the contexts are merged flat, so a shared prefix name would
collide and the pointers would land in the wrong file.
