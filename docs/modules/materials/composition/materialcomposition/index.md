---
hide:
  - toc
---

# MaterialComposition

The materials a material is made of and how much of each. This is the as-specified claim: a
recipe names ingredients, and an ingredient is a material with a composition of its own.

{{ oold_schema_meta_data("materials", "MaterialComposition") }}

{{ oold_schema_renderer("materials", "MaterialComposition") }}

The constituent is a reference, `@type: "@id"` with `x-oold-range`, not an embedded object: an
ingredient is an entity with its own identity, and embedding a material inside a material would
close a cycle that JSON-LD cannot resolve.

Here the two ontologies swap places. PMDco fits: its proportion is a relational quality of a
portion of matter, and a portion may be of any substance, so `constituent` is
`relational quality of` unchanged. EMMO does not: `hasSpeciesPart` ranges over species, and
while EMMO has `Mixture` and `hasPortionPart`, nothing attaches a fraction to a portion, so
these terms keep their placeholder IRIs in the EMMO reading.
