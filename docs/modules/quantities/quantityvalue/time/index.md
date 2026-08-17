---
hide:
  - toc
---

# Time

`QuantityValue` restricted to time units, that is a duration. It shows the per-quantity subclass
pattern: constrain the units, default to the SI one, and give each unit individual its community
aliases.

!!! note "Not the same as the `time` module"
    This is the *quantity kind* Time: a duration with a unit. The `time` module is about
    process time, that is temporal regions, process start and end, and temporalized qualities.
    Upstream ontologies use the same word for both, so mapping one onto the other is a mistake
    that is easy to make and hard to notice.

{{ oold_schema_meta_data("quantities", "Time") }}

{{ oold_schema_renderer("quantities", "Time") }}

## Where the unit aliases come from

The EMMO 1.0.4 branch publishes around 1600 unit individuals, each carrying a `qudtReference`
annotation. The alias table is therefore generated rather than hand-typed, and the same source
gives the UCUM and UN/CEFACT codes when they are needed.
