# Versions and identifiers

What each identifier names, and what a version change means for documents already written.
The rules for setting versions are in [Contributing](contributing.md).

## What an identifier names

```text
https://w3id.org/oo-ld/schemas/quantities/0.1
  resolves to
https://schemas.oo-ld.org/quantities/0.1/QuantityValue.schema.json
```

A conformance identifier names a **module at a version**, not a single schema. That is the unit to
validate against, cite and pin, because the schemas in a module share a context and are
meaningless apart from it.

Four things are published, and they move at different speeds:

| identifier | what it is | stability |
| --- | --- | --- |
| `<module>/<major.minor.patch>/` | one exact release | written once, never rewritten |
| `<module>/<line>/` | the newest patch of that line | moves only within a compatibility line |
| `<module>/dev/` | the current state of the main branch | changes without notice |
| `/mappings/<set>.sssom.tsv` | a mapping set as SSSOM | replaced on release, version inside the file |

The **line** is the part of a version that a break changes:

| version | line | why |
| --- | --- | --- |
| `0.2.3` | `0.2` | below 1.0 a break raises the minor |
| `1.4.2` | `1` | from 1.0 a break raises the major |

A reference to `quantities/0.2/` therefore never meets a break, and the
same holds for `quantities/1/` once the module reaches 1.0. From 1.0 on only
`<module>/<major>/` and the exact path are published, so a module has one
moving alias at any time. The rule is one function, `line` in
`scripts/_shared.py`, which every script and the site read.

Released versions are the pin target. `dev` shows what is coming before it is frozen and is
explicitly not a conformance target. A module that has never been released has only a `dev`
path: merging work does not mint a version, cutting a release does.

## What a version change means

Modules use semantic versioning, and the level is the strongest change any schema in the
module underwent:

- **Major.** Something that was valid is not any more, or means something else. A removed
  property, a newly required one, a narrowed type, a removed permitted value. Also a
  changed consensus mapping: the structure survives, but instances now say something
  different in RDF, which is a break even though no validator would notice.
- **Minor.** Something was added. An optional property, a permitted value, a new community
  mapping, a new schema in the module. Documents valid against the old version stay valid.
- **Patch.** Descriptions, comments, examples. Nothing an instance can observe.

Below 1.0 nothing is promised yet, so a major change raises the minor and a
minor change raises it too. A `0.x` line therefore receives patches only,
and anything else moves a dependent to a new line on purpose.

A patch release keeps the same path, so `quantities/0.1` can gain a clearer description
without moving. Anything above patch gets its own path, and the old one keeps serving the
bytes it always served.

## Documentation for an older version

The site is released by date rather than by semantic version, because it covers modules
that version independently and one number cannot describe all of them at once. Every module
version that ever existed was current in some dated release, so the prose for it is still
online: each schema page names the module version it documents and links the releases
where earlier versions were current.

## Mapping sets

A set is identified by the file it is published as, and carries its version inside as
`mapping_set_version`. A schema therefore needs no edit when the sets are
released, and a downloaded set states which release it came from.

Derived crosswalks between two communities live under `/mappings/crosswalks/` and are
regenerated with every release. They are chained, not curated, which their
`mapping_justification` records.
