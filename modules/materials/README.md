# materials

Chemical composition, structure and microstructure, material properties, object-vs-material duality.

- status: in-progress
- owner: @jesper-friis, @simontaurus, @BerndBaylerlein, @joergwa
- conformance IRI: assigned with the module's first release

> Not to be confused with MaterialsDCAT-AP, which is an application profile
> at the catalog layer and gets its own module when it starts.

Where no vocabulary is agreed yet, a schema names its terms in its own IRI space: the schema
IRI is the class, and a JSON Pointer into the schema is the property, so
`.../Composition.schema.json` is Material and `.../Composition.schema.json#/properties/composition`
is the edge to its composition. These are placeholders, not a third ontology. They carry no
axioms, they dereference to the schema that defines them, and each one records in
`x-oold-context` what it means in EMMO and in PMDco, so a consumer can map away from them.

Modules are listed even while empty, so that every recurring pattern has a home and
contributors know where to add. Adding a schema: derive it from a community pattern (a SHACL
shape plus example A-Box where one exists), map it as described in the contributor guide, and
add an instance beside it so CI validates it.
