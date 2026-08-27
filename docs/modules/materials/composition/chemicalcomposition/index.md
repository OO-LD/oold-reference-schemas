---
hide:
  - toc
---

# ChemicalComposition

The species a substance is made of and how much of each. This is the as-analysed claim: an
elemental analysis names species, not ingredients.

{{ oold_schema_meta_data("materials", "ChemicalComposition") }}

{{ oold_schema_renderer("materials", "ChemicalComposition") }}

EMMO fits this case exactly. A composition there is a language construct, and
`SingleComponentComposition` is the smallest sub-expression that still says something: one
species, one fraction. `components` is EMMO's `hasSpatialTile`, `constituent` its `hasSpeciesPart`,
whose range `ChemicalSpecies` is `ChemicalElement or ChemicalNomenclature or ChemicalFormula`,
so `Fe` and `SiC` both fit.

PMDco reads the same document through its own pattern, where the component is a mass ratio and
the amount the fraction value specification it is specified by.

{% raw %}
```mermaid
flowchart LR
    a{{substance1}}--> |a| A([Substance])
    b{{composition1}}--> |a| B([ChemicalComposition])
    c1{{comp_Fe}} & c2{{comp_Si}} & c3{{comp_C}}--> |a| C([ChemicalComponent])
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
