---
hide:
  - toc
---

# File

The bytes themselves, named once however many datasets read them. What is true of a file regardless of who reads it lives here; what is true of it as one dataset's representation lives on the Distribution that references it.

{{ oold_schema_meta_data("datasets", "File") }}

{{ oold_schema_renderer("datasets", "File") }}

A file is not a distribution. A distribution is a dataset's representation, so `conforms_to` and
`selector` are true of the pairing rather than of the bytes: the moment one file serves two
datasets, a single node would need two answers. Keeping the bytes separate lets the checksum be
stated once and read by both.

DCAT has no class for the bytes, which is why the distribution keeps its own `download_url`,
`media_type` and `byte_size`. A catalogue reads those and never has to know about this schema;
a crate reads this entity and gets the identity DCAT cannot express.
