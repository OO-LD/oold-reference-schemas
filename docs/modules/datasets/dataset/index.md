---
hide:
  - toc
---

# Dataset

Data published as one thing. The metadata lives in the fields; `data` is the interpreted
payload, and **the type of `data` is the schema**, so there is no separate schema object to keep
in sync.

{{ oold_schema_meta_data("datasets", "Dataset") }}

{{ oold_schema_renderer("datasets", "Dataset") }}

Three ways to hold the payload, and the schema is the same for all three: inline in `data`,
behind a JSON-LD `@id` that a loader dereferences, or in a file described by a
[Distribution](../distribution/). A distribution is a serialisation of this dataset, not a
different thing, which is what `conforms_to` records.
