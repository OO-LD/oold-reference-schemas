# Contributing

## One source, everything else derived

`modules/` is the source of truth. Every other artefact in the repository is produced from
it, and the build fails if a committed artefact disagrees with what the schemas say.

| what | where | who writes it |
|---|---|---|
| schemas, module metadata | `modules/<module>/` | you |
| prose about a schema | `docs/modules/<module>/.../index.md` | you, in a seeded page |
| site pages and assets | `docs/*.md`, `docs/stylesheets`, `docs/javascripts` | you |
| RDF readings, instances, labels | `generated/` | `make generate` |
| SSSOM mapping sets | `generated/mappings/` | `make generate`, not committed |
| schema page tree and nav | `docs/modules/`, `zensical.toml` nav region | `make generate` |
| schemas at their published paths | `docs/<module>/<version>/` | `make generate`, not committed |
| mapping sets at their published paths | `docs/mappings/**.sssom.tsv` | `make generate`, not committed |

Run `make generate` after touching a schema, and `make check` before opening a pull
request. `make check` is what CI runs.

## Adding a schema

1. Write `modules/<module>/<Name>.schema.json`. To extend an existing schema, reference it
   from `allOf`; the first `$ref` decides where the schema sits in the documentation tree.
2. Run `make generate`. This seeds `docs/modules/<module>/.../<name>/index.md`, adds it to
   the navigation, regenerates the RDF readings and rebuilds the mapping sets.
3. Write the prose. The seeded page carries only what is derivable, rendered by macros.
   Put explanation under a `## How it works` heading: what the schema decides, what it
   deliberately leaves out, and why a mapping is a close match rather than an exact one.
4. Run `make validate`. A schema that does not round-trip through RDF is not finished.

An instance file starts with `$schema`. Editors read it to offer validation while the file is
being edited, and some stop looking after the first key, so the order is not cosmetic.
`make check` enforces it.

Pages are seeded once and never overwritten. If a page stops documenting the schema its
location claims, or documents a schema that no longer exists, `make check` says so rather
than silently rewriting your prose. A page that has to move because its schema gained a
parent is moved with its content intact.

## Mappings

A mapping is authored next to the term it maps, never in a separate file:

- the consensus reading of a term goes in `@context`;
- every community alternative goes in `x-oold-context`, tagged with its
  `mapping_set_id` and the exact ontology version it was checked against.

A value alias is a term whose values are vocabulary entries rather than free text, coerced
with `@vocab`: `unit` is one, and `SEC` or `PERCENT` are its members. List them as an `enum`
of the vocabulary's own local names, and give each one a name in `x-enum-varnames`, in the
same order:

```json
"unit": {
  "enum": ["SEC", "MilliSEC", "HR"],
  "x-enum-varnames": ["second", "milli_second", "hour"]
}
```

The names are what a generated binding uses, so they must be lower case ASCII identifiers
and unique within the enum. Where the value is already such a name (`second`, `milli_metre`),
it is the name and `x-enum-varnames` is not needed. `make check` enforces that. Write the
names out rather than deriving them: no standardised representation for arbitrary units is both canonical and ASCII. UCUM
is ASCII but not canonical, since `L/(m2.s)` and `L.m-2.s-1` are the same unit; SI symbols
are canonical but not ASCII. For a composed unit, normalise the
[siunitx](https://ctan.org/pkg/siunitx) spelling, so `\liter\per\meter\squared\per\second`
becomes `liter_per_meter_squared_per_second`.

The SSSOM sets in `generated/mappings/` are built from those declarations. Do not edit
them; edit the schema and regenerate. Each set is published as SSSOM TSV at the identifier
its `mapping_set_id` names, so `https://w3id.org/oo-ld/schemas/mappings/emmo.sssom.tsv`
resolves to the set itself, and the version of the set is stamped inside the file rather
than in the identifier, so a release does not have to touch every schema.

Pin the ontology, not the promise of one: `object_source_version` may name a commit or a
snapshot where a published version IRI is stale. The files are not carried here; they are
pinned by hash in `ontologies.lock.json`. `make ontologies` fetches and verifies them, and
`make labels` rereads the human-readable labels for the terms the schemas map. A hash
mismatch means upstream moved under the pin, so the mappings that target it need re-checking
before the lock is updated; `python scripts/fetch_ontologies.py --update` refetches and
rewrites the hashes once you have decided the mappings still hold. See
[Pinned ontologies](ontologies.md) for how a pin is added or moved.

## Versions

Three number lines, each with a different job:

- **Schemas** carry `x-oold-version`, their own semver.
- **Modules** carry the version in `modules/<module>/module.json`. A module is the unit
  that is published and conformed to, so its bump level is the highest level found among
  its schemas: a removed property or a changed consensus mapping is major, an added
  optional property or a new synonym is minor, a description is a patch. A removed schema
  is major, an added one minor.
- **The repository** is released by date, because it aggregates modules that version
  independently and no single semver level could describe eleven of them at once.

`make bump` computes the versions rather than incrementing them: it reads the last release,
raises each schema by the level of what changed since, and raises the module by the highest
level among its schemas. Running it twice therefore lands on the same number, which is what
makes it safe in a pre-commit hook. `make check` verifies the same floors, so a bump that is
too small fails review rather than shipping.

`make release` stamps the dated release, records which module version it documents in
`generated/versions.json`, and regenerates. The schema pages read that index back, which is
how a reader finds the documentation for a module version that is no longer current.

Publishing checks both promises before it writes: `scripts/check_publish.py` refuses to
rewrite an exact release and refuses to move a compatibility line with anything above a patch,
so a forgotten bump fails the deploy rather than changing what someone already fetched.

Between releases, schemas may run ahead of their module. That state is published at
`<module>/dev/`, which is explicitly not a conformance target. A released version is
written once at `<module>/<major.minor>/` and is never rewritten by anything above a patch,
because a conformance IRI that changes meaning is worse than no IRI at all.

## Style

- No em dashes, no decorative comments, no emoji.
- Comments explain why, not what. If a workaround exists, name what it works around.
- Prose is honest about limits: a mapping that is only a close match says so, and says why.
