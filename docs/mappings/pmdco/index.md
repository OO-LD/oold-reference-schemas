# PMDco mappings

How the terms of this library are named in PMDco.

Generated from the mappings declared in the schemas, so this page and the schemas cannot
disagree.

## Stated mappings

Each row maps a term of this library, defined by the schema it links to, onto its
counterpart in PMDco, with the ontology version the mapping was checked against.

{{ download("/mappings/pmdco.sssom.tsv", "SSSOM TSV") }}

{{ sssom_table("pmdco") }}

## Derived crosswalks

What PMDco and another vocabulary call the same thing, chained through the terms both map
here. Derived rather than stated: every row carries the `semapv:MappingChaining`
justification and names the term the chain went through. The rule and the full set are on
the [Crosswalks](../crosswalks/) page.

{{ mapping_crosswalks("pmdco") }}
