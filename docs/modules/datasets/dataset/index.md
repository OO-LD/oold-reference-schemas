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

## Policies and data spaces

`has_policy` carries the ODRL Offers that govern use. It sits on the dataset because
`odrl:hasPolicy` has domain `odrl:Asset`: the dataset is the asset, so a policy never attaches to
a distribution or to the bytes. Two datasets over one file are two assets with two offers, which
is what keeps the file free of statements that are only true of one reading of it. The rules
themselves are not modelled here; a policy language is a module of its own.

The Dataspace Protocol requires a catalogue dataset to carry at least one distribution, and its
distribution is a transfer channel, not a byte location: its `dcterms:format` names a protocol
and its identity is anonymous. A connector generates those from the destinations it can serve, so
a dataset whose `data` is inline or behind a reference is a complete DCAT-AP dataset here and
becomes a complete Dataspace Protocol dataset once a connector publishes it. That is why
`distributions` carries no minimum.

Two things to know when such a document is handed to a connector. Our `@context` must come first
if the protocol context is added, because that one declares its terms `@protected` and the
protocol redefines `Dataset`, `Distribution` and `DataService`; the reverse order aborts with a
protected term redefinition. And the protocol's own JSON Schemas require the literal keys `@id`
and `@type`, so the `id` and `type` aliases have to be written out for that payload, which is a
serialisation step rather than a schema change.
