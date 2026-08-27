---
hide:
  - toc
---

# Distribution

Where the bytes are, in which format, and which schema they embody.

{{ oold_schema_meta_data("datasets", "Distribution") }}

{{ oold_schema_renderer("datasets", "Distribution") }}

Storage, not content. `conforms_to` points back at the dataset schema the file is an encoding
of, and `table_schema` at the row schema where the serialisation is tabular, so a reader can
materialise rows without guessing. `selector` addresses one part inside a container: a sheet, an
HDF path, a table in a database, a member of an archive.
