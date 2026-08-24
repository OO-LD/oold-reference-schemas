---
hide:
  - toc
---

# TabularDataset

A dataset whose payload is a list of rows, each row a typed object.

{{ oold_schema_meta_data("datasets", "TabularDataset") }}

{{ oold_schema_renderer("datasets", "TabularDataset") }}

The row type is what makes this a schema rather than a description of one, so this class leaves
`items` open and a subschema fixes it. A wide table with a `Time`-typed column is already a time
series; no separate class is needed for that.
