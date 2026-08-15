# How it works

Four schemas, each building on the one before, are enough to show every mechanism in this
library. The notation itself is specified in the
[OO-LD specification](https://oo-ld.org/latest/spec/); this page is about what the schemas
here do with it. Read them in order and you will have seen how one document carries structure and
meaning at once, how a second community reading is added without touching the data, and what
a subschema costs.

The widgets below are the same ones the [modules](modules/index.md) pages use, rendered from
the schemas themselves. Nothing here is retyped, so nothing here can go stale.

## QuantityValue

`QuantityValue` is a number, a unit, and optionally the uncertainty of the number. Everything
else in the library reuses it, so it is worth reading closely: if this one is awkward, the
awkwardness spreads everywhere.

{{ oold_schema_renderer("quantities", "QuantityValue", page) }}

Five tabs, one source. **Terms** is the schema read as a vocabulary: every term, what
constrains it, what it means in the consensus reading, and what each community calls it
instead. **JSON** and **YAML** are the schema itself. **Instance** is a document that
validates against it. **RDF** is that same document expanded to triples, with a selector for
the mapping set, which is the whole point of the exercise: one file, several readings.

Look at the `unit` row in the Terms tab. The property maps to `qudt:hasUnit`, and underneath
it sit the permitted values, each mapping to a unit individual of its own. That two-level
structure is what lets a community rename both the property and the units it points at.

## Time: constraining the units

`Time` restricts `QuantityValue` to time units. It is the pattern every quantity kind
follows.

!!! note "Not the same as the `time` module"
    This is the *quantity kind* Time: a duration with a unit. The `time` module is about
    process time, that is temporal regions, process start and end, and temporalized qualities.
    Upstream ontologies use the same word for both, so mapping one onto the other is a mistake
    that is easy to make and hard to notice.

{{ oold_schema_renderer("quantities", "Time", page) }}

The subclass adds four things and inherits everything else:

1. **A more specific class term.** `Time` maps to the QUDT quantity kind `qkind:Time`, with
   EMMO's ISQ `Time` class as a synonym. QUDT models quantity kinds as individuals, so typing an
   instance with one is punning, the same question EMMO faces for units. It is harmless for data
   exchange and left to the ontologies to settle.
2. **Unit individuals as context terms.** `SEC`, `MilliSEC` and `HR` are declared in the
   `@context`, which is what makes them aliasable at all.
3. **An enum and a default.** The enum pins the valid units, which also guards the `@vocab`
   coercion inherited from `QuantityValue`: without it, a typo would be silently minted into an
   IRI under the vocabulary base. The default is the SI unit.
4. **Value-level aliases.** Each unit term carries its EMMO and UO counterparts, so a
   community reading resolves the *unit itself*, not just the property pointing at it.

In the Terms tab this is visible as two sections: everything inherited from `QuantityValue`,
then what `Time` overrides. The class row sits under `type`, because that is what it is, the
default value of `type` resolved through a type alias, not a field of its own.

### Reading the three graphs

Switch the mapping set in the RDF tab. Those are three readings of one unchanged instance file.

The consensus reading types the node with the QUDT quantity kind and uses `qudt:value` and
`qudt:hasUnit`. The `emmo` reading swaps in EMMO's ISQ `Time` class, `hasReferencePart`, the
EMMO `standardUncertainty` data property, and, at value level, `emmo:Second` for the unit
itself. The `pmdco` reading uses `obo:OBI_0001937` for the value and `obo:IAO_0000039` with the
UO second.

The fallbacks are the honest part. EMMO has no term that a flat `value` can map to, so that
triple stays `qudt:value`; PMDco has no quantity-kind class for the type and no uncertainty
property, so those stay on the consensus mapping. A partial alignment remains usable, and it is
visible exactly where a community has nothing to offer.

CI checks every reading for a lossless round-trip, so a mapping that drops or mangles a
term fails the build rather than shipping quietly.

## Length: the same pattern again

`Length` repeats the pattern for another quantity kind, which is the point: the second one
costs nothing new to design.

{{ oold_schema_renderer("quantities", "Length", page) }}

It adds a class term mapping to `qkind:Length`, a unit enum that pins the valid length units
and guards the inherited `@vocab` coercion, the SI unit as default so an instance may omit
`unit` entirely, and a value term per unit so each one is aliasable per community. With four
permitted units the Terms tab collapses them behind a toggle rather than pushing the properties
out of view.

## Diameter: three levels deep

{{ oold_schema_renderer("quantities", "Diameter", page) }}

Note how little it declares. The units, their aliases, the value and uncertainty terms and every
mapping on them come from `Length` and `QuantityValue`; `Diameter` only narrows the class term
and the example. That is the point of the chain: a new quantity costs a handful of lines, and it
inherits a validated mapping set rather than restating one.

## Where to go next

- [Modules](modules/index.md) lists every schema with the same five tabs.
- [Mapping sets](mapping-sets.md) covers the tiering mechanism in general.
- [Mapping sets](mapping-sets.md) has the SSSOM exports and the derived crosswalks.
- [Versions and identifiers](versioning.md) says what you can pin and what a bump means.
- [Contributing](contributing.md) is the other side: where to edit and how versions are set.

## References

- [emmo-repo/EMMO#376](https://github.com/emmo-repo/EMMO/issues/376), preferred representation of quantities
- [emmo-repo/EMMO#377](https://github.com/emmo-repo/EMMO/issues/377), relating quantity individuals to units
- [OO-LD/oold-schema#107](https://github.com/OO-LD/oold-schema/issues/107), the QuantityValue schema upstream
- [OO-LD/oold-schema#108](https://github.com/OO-LD/oold-schema/issues/108), the mapping-selection requirements
