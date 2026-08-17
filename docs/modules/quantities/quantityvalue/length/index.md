---
hide:
  - toc
---

# Length

`QuantityValue` restricted to length units. It adds no properties: it pins the permitted
units, defaults to the SI unit, and names the quantity kind in each community's vocabulary.

{{ oold_schema_meta_data("quantities", "Length") }}

{{ oold_schema_renderer("quantities", "Length") }}

## Why PATO is only a close match

EMMO `Length` is an exact match: it is the ISQ quantity, the same thing QUDT names. PATO
`length` is deliberately not. PATO models length as a *quality inhering in a bearer*, not as a
value with a unit. Declaring that exact would assert that a number-with-unit is the same entity
as a property of an object, which is the category error the mapping is meant to expose rather
than hide.

This is why the mapping sets carry SSSOM predicates rather than a flat list of equivalents, and
why the derived [crosswalks](../../../../mappings/crosswalks/) refuse to chain two close matches into a third.
