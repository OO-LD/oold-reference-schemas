---
hide:
  - toc
---

# Dataset

Data published as one thing: what it is, who may use it, and where the files are.

{{ oold_schema_meta_data("datasets", "Dataset") }}

{{ oold_schema_renderer("datasets", "Dataset") }}

DCAT for the publication layer, CSVW for what is inside a file, QUDT for what a column
measures. Nothing here is invented: the schema only fixes which of those terms to use and in
which shape, so a cycling run reads as a dataset to a catalogue and as a table to a parser.

The instance shows the three layers at once: a dataset, its one distribution, and the table
schema of that distribution.
