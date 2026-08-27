---
hide:
  - toc
---

# ElectrochemicalCyclingDataset

A battery cycling run: time since the test started, cell voltage and cell current, row by row.

{{ oold_schema_meta_data("datasets", "ElectrochemicalCyclingDataset") }}

{{ oold_schema_renderer("datasets", "ElectrochemicalCyclingDataset") }}

The row carries quantities, so a value states its unit instead of leaving it to a header, and
the three fields map to BattINFO through the electrochemistry domain ontology: `TestTime`,
`CellVoltage`, `CellCurrent`.

The committed instance holds three samples inline, which is the readable case. A real run is
millions of rows and lives in a file: the same dataset then carries a
[Distribution](../../../distribution/) whose `conforms_to` names this schema, and a reader
materialises the rows from it. Nothing about the schema changes between the two.
