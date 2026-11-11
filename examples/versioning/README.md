# Versioning example

The smallest working picture of the versioning scheme: validate an instance with
no network, using only the offline package of a released module.

## Run it

```bash
make generate
uv run examples/versioning/validate_offline.py \
  docs/packages/materials-0.2.0.zip modules/materials/Material.instance.json
```

`make generate` builds `docs/packages/<module>-<version>.zip`. The command then
prints `valid`. The instance cites its schema by a bare file name, which the
script reads from the module the zip is named after.

## What it shows

- The zip holds `materials` and the `quantities` version its lock pins, as
  unmodified documents at the paths the host serves.
- The instance can also cite an identity IRI, by line or by exact version, and
  the same zip validates both:

  ```text
  https://w3id.org/oo-ld/schemas/materials/0.2/Material.schema.json
  https://w3id.org/oo-ld/schemas/materials/0.2.0/Material.schema.json
  ```

- A document the zip lacks is reported as `not in the package`, never fetched.

## Where it is used

`make validate` runs this same script over every module instance, so the recipe
in the guide is the one CI checks.

The guide is at [docs/versioning-guide.md](../../docs/versioning-guide.md). A
contributor template will grow out of this directory.
