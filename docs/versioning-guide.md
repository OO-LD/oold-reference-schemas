# Versioning guide

The short version, for people who cite schemas and people who change them. The
full rules are in [Versions and identifiers](versioning.md).

Every path below is under `https://w3id.org/oo-ld/schemas/`.

## Citing a schema

| I want | I cite | for example |
| --- | --- | --- |
| patches to flow in | the line | `materials/0.2/` |
| the same bytes forever | the exact version | `materials/0.2.0/` |
| to work offline | a package | `packages/materials-0.2.0.zip` |

Rule of thumb: working data cites the line, and an archived or published
dataset cites the exact version.

Below 1.0 the line is `0.2`. From 1.0 it is just `1`.

## Working offline

A released version has a zip that holds the module and everything it pins.

1. Download `https://schemas.oo-ld.org/packages/materials-0.2.0.zip`.
2. Take [validate_offline.py][recipe], a short standalone script.
3. Run it:

```bash
uv run validate_offline.py materials-0.2.0.zip my-material.json
```

It reads every schema from the zip and has no other way to fetch one, so
nothing leaves your machine. To use another validator, map an IRI to the zip
member by removing the prefix above.

[recipe]: https://github.com/OO-LD/oold-reference-schemas/blob/main/examples/versioning/validate_offline.py

## Changing a schema in five steps

1. **Edit** the schema in `modules/<module>/`. Cite other modules by line.
2. **Bump** with `make bump`. It works out the level from what changed.
3. **Read** the level it chose, using the table below.
4. **Check** with `make generate`, `make check` and `make validate`.
5. **Release**, which is a maintainer step: `make release`, then tag.

What you changed, and what the people citing you see:

| you changed | level | below 1.0 | from 1.0 |
| --- | --- | --- | --- |
| a description | patch | same line | same line |
| added an optional property | minor | new line | same line |
| new spec edition | minor | new line | same line |
| removed or required a property | major | new line | new line |
| changed a consensus mapping | major | new line | new line |

A new line never touches the old one. `0.2/` keeps serving what it served.

## Example: a fix in a dependency

`materials` cites `quantities/0.2/`, and `materials 0.2.0` is released.

1. `quantities` publishes a description fix as `0.2.1`.
2. The line `quantities/0.2/` now serves `0.2.1`. Everyone on the line gets it.
3. The lock of `materials 0.2.0` still says `quantities 0.2.0`, because it
   records what was true when `materials` was released.
4. `materials` picks the fix up in its next release, and the new lock says
   `0.2.1`.

## Where to look

- [Versions and identifiers](versioning.md): what every path means.
- [Contributing](contributing.md): the working routine in full.
- `examples/versioning/` in the repository: the offline recipe.
