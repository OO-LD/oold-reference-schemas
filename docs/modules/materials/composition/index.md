---
hide:
  - toc
---

# Composition

Chemical composition of a substance.

{{ oold_schema_meta_data("materials", "Composition") }}

{{ oold_schema_renderer("materials", "Composition") }}


The example below shows how the chemical composition can be specified for a substance instance:

```json
{
  "$schema": "Composition.schema.json",
  "@context": "Composition.schema.json",
  "@id": "https://example.org/material/no27_14",
  "type": ["Substance"],
  "composition": {
    "type": ["ChemicalComposition"],
    "components": [
      {"type": ["Component"], "constituent": "Fe", "amount": {"type": ["MassFraction"], "value": 96.7, "unit": "PERCENT"}},
      {"type": ["Component"], "constituent": "Si", "amount": {"type": ["MassFraction"], "value": 3.3, "unit": "PERCENT", "standard_uncertainty": 0.1}},
      {"type": ["Component"], "constituent": "C", "amount": {"type": ["MassFraction"], "value": 120, "unit": "PPM"}}
    ]
  }
}
```

It should result generic RDF representation:

{% raw %}
```mermaid
flowchart LR
    a{{substance1}}--> |a| A([Substance])
    b{{composition1}}--> |a| B([ChemicalComposition])
    c1{{comp_Fe}} & c2{{comp_Si}} & c3{{comp_C}}--> |a| C([Component])
    d1{{Fe}} & d2{{Si}} & d3{{C}}--> |a| D([ChemicalSpecies])
    e1{{wt_Fe}} & e2{{wt_Si}} & e3{{wt_C}}--> |a| E1([MassFraction])-->|subClassOf| E2([ChemicalCompositionQuantity])
    g1{{%}} & g2{{ppm}}--> |a| G([MassFractionUnit])

    a -->|composition| b
    b -->|components| c1 & c2 & c3
    c1 -->|constituent| d1
    c2 -->|constituent| d2
    c3 -->|constituent| d3
    c1 -->|amount| e1
    c2 -->|amount| e2
    c3 -->|amount| e3
    e1 -->|value| f1[96.7]
    e2 -->|value| f2[3.3]
    e3 -->|value| f3[120]
    e2 -->|standard_uncertainty| f4[0.1]
    e1 -->|unit| g1
    e2 -->|unit| g1
    e3 -->|unit| g2

    classDef cls fill:#ffc,stroke:#f8f200,color:#000
    classDef indv fill:#cfc,stroke:#96daa1,color:#000
    classDef literal fill:none,stroke:#800,color:#000

    class A,B,C,D,E1,E2,G cls
    class a,b,c1,c2,c3,d1,d2,d3,e1,e2,e3,g1,g2 indv
    class f1,f2,f3,f4 literal
```
{% endraw %}
