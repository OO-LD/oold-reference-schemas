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

## Three properties that look alike

`dcat:mediaType` is the format of the bytes, an IANA media type IRI, which is what DCAT-AP
harvests. `dcterms:conformsTo` is the schema those bytes embody, which is what makes the file
readable as typed data. `dcterms:format` is neither: the Dataspace Protocol claims it for the
transfer channel, with values such as `HttpData-PULL`, so a file format written there means a
wire protocol to a connector and a file type to a catalogue. This module therefore never maps a
format onto `dcterms:format`, and the term is reserved.

`byte_size` stays an uncoerced term although DCAT-AP types it `xsd:nonNegativeInteger`: a pinned
datatype does not survive the round trip, because `fromRDF` with native types drops it and the
term no longer matches on the way back. The value is an integer either way.

## Naming a part of a container

Where a fragment syntax exists, the part belongs in the URL and no property is needed: RFC 7111
addresses rows and columns of a CSV, Media Fragments addresses time and regions of media. Two
datasets over one CSV are then two distributions with two fragment URLs and one file.

Where none exists, an HDF5 group, a sheet, a table in a database, `selector` names the part the
way the Web Annotation model does: an expression plus the specification it follows. An opaque
string would be a private convention that no consumer can parse, and `conforms_to` on the
selector is what says whose convention it is.
