---
hide:
  - toc
---

# CyclingTable

What the columns of a battery cycling file mean, and which cell and protocol produced it.

{{ oold_schema_meta_data("datasets", "CyclingTable") }}

{{ oold_schema_renderer("datasets", "CyclingTable") }}

The rows stay in the file. A cycling run is millions of rows, so what belongs in the schema is
what a reader needs to interpret a column: its name in the header, the quantity it measures and
the unit it is recorded in. `time`, `voltage` and `current` are the three a tester always
writes; capacity and cycle index follow once the quantities module has them.

The quantity and unit aliases are mirrored from `quantities` rather than referenced, the same
workaround the materials module uses, and for the same reason: a cross-module `$ref` does not
resolve until that module is released.
