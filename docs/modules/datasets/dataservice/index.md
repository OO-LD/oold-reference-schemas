---
hide:
  - toc
---

# DataService

A service through which datasets are reached. In a data space the connector publishes the instance, since the endpoint depends on who is asking and over which protocol; this schema states what such an entry looks like.

{{ oold_schema_meta_data("datasets", "DataService") }}

{{ oold_schema_renderer("datasets", "DataService") }}

A data space connector publishes the instance, not this repository. The endpoint depends on the
requesting participant's credentials and on the protocol version the catalogue was served
through, so it is decided at request time; what belongs here is the shape of the entry and the
mapping of `endpoint_url` onto `dcat:endpointURL`.
