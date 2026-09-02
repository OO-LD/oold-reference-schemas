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

Where a fragment syntax exists, the part belongs in the URL and no property is needed. Two
datasets over one CSV are then two distributions with two fragment URLs and one file.

Where none exists, `selector` names the part the way the Web Annotation model does: an expression,
a class saying which language it is in, and `conforms_to` naming the specification or convention
where the class does not fix it. An opaque string would be a private convention that no consumer
can parse.

| the part | how to name it |
|---|---|
| rows or columns of a CSV | `download_url` with an RFC 7111 fragment, `run.csv#col=1,3` |
| a region or an interval of an image, audio or video | `download_url` with a Media Fragments fragment, `scan.mp4#t=10,20` |
| a group or dataset in HDF5 | `FragmentSelector`, value `/cell42/cycling`, `conforms_to` the HDF5 path documentation |
| a sheet in a spreadsheet | `FragmentSelector`, value `Sheet1`, `conforms_to` the convention the reader applies |
| a table or a query in a database | `FragmentSelector`, value `SELECT * FROM cycling WHERE cell = 42`, `conforms_to` the SQL dialect |
| an element in XML | `XPathSelector`, value `//measurement[@cell='42']`, class fixes the language |
| an element in HTML | `CssSelector`, value `#results table.cycling` |
| a passage in text | `TextQuoteSelector` or `DataPositionSelector` |

The expression is carried by `rdf:value` in every case, which is what the Web Annotation model
does, so a consumer reads the class to know how to interpret it. The JSON calls it `value`, scoped
to the selector, so it does not collide with the `value` of a quantity in the same document.
