# Conformance IRIs

Conformance to the notation itself is defined by the
[OO-LD specification](https://oo-ld.org/latest/spec/); this page is about conforming to a module
published here.

!!! note "The `w3id.org` redirect is pending"
    A conformance IRI is written `https://w3id.org/oo-ld/schemas/<module>/<version>`, which is
    the identifier to cite and to declare, because it is independent of where the files are
    hosted. The redirect that makes it dereference is filed as
    [perma-id/w3id.org#6556](https://github.com/perma-id/w3id.org/pull/6556) and not yet merged,
    so until it is, fetch through `https://schemas.oo-ld.org/<module>/<version>/` directly. No
    version has been released while this is open, so no published identifier is affected.

Each module is conformable on its own; bundles aggregate modules at pinned versions so a domain
consumer can claim one thing rather than several. Instances declare conformance with
`dct:conformsTo` (or the RFC 6906 media-type `profile` parameter).

| IRI | what it covers |
|---|---|
| `https://w3id.org/oo-ld/modules/<module>/<version>` | a single module |
| `https://w3id.org/oo-ld/schemas/bundle/science/<version>` | quantities + datasets + processes + measurement + time |
| `https://w3id.org/oo-ld/schemas/bundle/mse/<version>` | the science bundle + materials + devices |

IRIs are module-scoped and project-independent on purpose: a module can later move to its own
repository as a redirect rather than a breaking change. The `w3id.org/oo-ld/` namespace
redirects to `oo-ld.org`, see https://github.com/perma-id/w3id.org/pull/6556.
