---
hide:
  - toc
---

# Material

A material and what it is made of.

{{ oold_schema_meta_data("materials", "Material") }}

{{ oold_schema_renderer("materials", "Material") }}

The two compositions are separate claims, not two encodings of one. An elemental analysis and a
recipe can coexist, and they can disagree: 20% A, 80% B and a measured 100 ppm water are not
fractions of the same partition, since the water arrived with A or B. Keeping them in two lists
makes that impossible to write by accident, and a material may carry either, both, or several
of each, once provenance is added.

Reading a material composition back to element level, by following each ingredient to its own
chemical composition and summing, is a derivation over dereferenced documents. It is sound only
where every ingredient has a chemical composition on the same basis, which is exactly what the
mixed case breaks, so the schema never asserts it.
