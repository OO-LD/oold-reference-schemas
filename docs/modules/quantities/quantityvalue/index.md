---
hide:
  - toc
---

# QuantityValue

A number with a unit, optionally with its standard uncertainty. It is the base schema every
other quantity in this module extends.

{{ oold_schema_meta_data("quantities", "QuantityValue") }}

{{ oold_schema_renderer("quantities", "QuantityValue") }}

## Decisions

**Uncertainty is flat, and deliberately incomplete.** Only two forms are here:
`standard_uncertainty`, in the unit of the value following the GUM convention, and
`relative_standard_uncertainty`, a dimensionless ratio and not a percentage. These are the only
two that released vocabularies actually map. Expanded uncertainty, coverage factor and coverage
intervals have no flat target in QUDT, EMMO, PMDco or schema.org, so inventing terms for them
here would create mappings that mean nothing to anyone else. They belong in a separate,
node-shaped uncertainty record once there is something to map them to.

**Numbers are not datatype-coerced.** JSON numbers project to `xsd:double`, which is the only
fractional datatype that survives the round-trip back into a native JSON number. Coercing to
`xsd:decimal` looks tidier and quietly breaks re-validation, because the value returns from RDF
as a string. QUDT constrains these properties to `xsd:decimal` on `qudt:Quantifiable`, but our
nodes are not typed as `Quantifiable`, so no constraint is violated; a QUDT-strict consumer can
canonicalize on ingest.

**The unit is an IRI, and `unit` is coerced with `@type: @vocab`.** Modelling the unit as a
reference to a unit individual keeps the class-versus-individual question out of the data
entirely. The `@vocab` coercion is what lets a subclass declare its unit individuals as terms
and give each one community aliases, which is the next step.

**Class alternatives sit on the inline `type` term** rather than in `x-oold-instance-rdf-type`,
because that keyword materializes *all* declared types on every export. That is right for
consensus co-typing and wrong for either/or community alignments, where the point is to pick
one.

**EMMO has no synonym for `value`.** EMMO models a quantity value as a node with a nested
numerical part, and this schema's `value` is a literal, so no term definition on *this* schema
can produce it: the EMMO reading falls back to `qudt:value`. The correspondence is not lost,
it belongs to the other side. A schema whose `value` is an object can declare, in its mapping
set for QUDT, that `qudt:value` nests under it, and then reads this schema's data as its own
nested shape. See [Shapes, not only names](../../../mapping-sets.md#shapes-not-only-names) and
[emmo-repo/EMMO#376](https://github.com/emmo-repo/EMMO/issues/376).

## Where the mappings come from

Each synonym records the ontology and the exact version it was checked against. The EMMO
mappings target the 1.0.4 development branch rather than the 1.0.3 release, because that is
where units became individuals and the VIM4 data properties appeared. The published build at
`w3id.org/emmo/1.0.4` lags its own branch, so the pin names the commit rather than the version
IRI.

## References

- [emmo-repo/EMMO#376](https://github.com/emmo-repo/EMMO/issues/376), preferred representation of quantities
- [emmo-repo/EMMO#377](https://github.com/emmo-repo/EMMO/issues/377), relating quantity individuals to units
- [OO-LD/oold-schema#107](https://github.com/OO-LD/oold-schema/issues/107), this schema upstream
- [OO-LD/oold-schema#108](https://github.com/OO-LD/oold-schema/issues/108), the mapping-selection requirements
