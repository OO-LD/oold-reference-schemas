# Pinned ontologies

The ontology versions each mapping was validated against, so a mapping can be re-checked and
drift detected when an upstream release lands. Every synonym additionally records its own
`object_source_version`, so the pin travels with the mapping rather than only with this page.

{{ oold_pinned_ontologies() }}

An ontology is pinned once a mapping targets it, rather than mirrored wholesale. OBO
terms come from their versioned release artefacts, so the pin is a release rather than
whatever `latest` resolves to today.

## How the pin is enforced

The files themselves are not carried here. They belong to other projects, and nothing in the
documentation build reads them: the labels they supply are committed, so the site builds
offline. What is carried is `ontologies.lock.json`, naming for each ontology its version,
repository, ref and a SHA-256 per file.

```
make ontologies    fetch the pinned files into .ontologies/ and verify every hash
make labels        refresh the committed labels from them
```

## Maintaining the lock

Pin a versioned artefact, never a `latest` URL. A moving target makes every upstream release
look like tampering, and a check that cries wolf is a check nobody reads.

To add an ontology, write its entry in `ontologies.lock.json` with the version, repository,
ref, base URL, licence and the files a mapping needs, then fill in the hashes:

```
python scripts/fetch_ontologies.py --update
```

Changing a pin is the same act with one step more: edit the ref, run `--update`, and before
committing the new hashes, re-check the mappings that target the ontology and record the new
`object_source_version` on each synonym. `--update` reports what moved and changes nothing
else, so the decision stays with a person.

A hash mismatch is the point of the exercise. A tag that moves, a file edited in place or a
published build that lags its own branch each fail loudly here, rather than leaving a mapping
that quietly means something else. Updating a pin is therefore a deliberate act: change the ref
in the lock, fetch, re-check the mappings that target it, and record the new
`object_source_version` on each synonym.

Terms from vocabularies that are not pinned, `schema.org` among them, are resolved once from
OLS where it carries them and shown by their compact IRI otherwise.
