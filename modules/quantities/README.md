# quantities

QuantityValue, units, uncertainty, value specifications (scalar, fraction, categorical), ratios.

- status: worked example
- owner: unassigned
- conformance IRI: `https://w3id.org/oo-ld/schemas/quantities/0.3`

| file | what it is |
|---|---|
| `module.json` | the module's own metadata, including the version it publishes under |
| `QuantityValue.schema.json` | a numeric value with a unit and optional standard uncertainty |
| `Time.schema.json` | a quantity kind: pins the permitted units, defaults to the SI unit, aliases the unit individuals |
| `Length.schema.json` | a quantity kind, the same pattern for length |
| `Diameter.schema.json` | a subschema of `Length`, narrowing the class term |
| `MassFraction.schema.json` | a ratio: the quantity, not the unit, says the fraction is by mass |
| `Voltage.schema.json` | a quantity kind for electric potential difference |
| `ElectricCurrent.schema.json` | a quantity kind for electric current |
| `<Name>.instance.json` | an instance per quantity kind, validated and round-tripped by CI |

Walkthrough of how these are built and mapped:
[schemas.oo-ld.org/how-it-works](https://schemas.oo-ld.org/how-it-works/).
