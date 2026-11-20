"""Modules of other repositories, read from the packages they are pinned to.

A pin in reference-schemas.toml names one version of one module and the digest of the package
that holds it. Nothing is discovered: a module that is not pinned is an error, and a pinned
package is only downloaded when a document of it is needed, then checked against its digest.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

import remote
from _shared import LockError
from config import CONFIG, ROOT, Dependency

CACHE = ROOT / ".cache" / "packages"


class Pinned:
    """A catalog of the pinned modules, with the same interface as the repository's own."""

    def __init__(self, dependencies: Iterable[Dependency],
                 get: Callable[[Dependency], bytes] | None = None) -> None:
        self.deps = {d.identity: d for d in dependencies}
        self.get = get or (lambda d: remote.fetch(d.package, d.sha256, CACHE))
        self.loaded: dict[str, dict[str, bytes]] = {}

    def pin(self, identity: str) -> Dependency:
        if identity not in self.deps:
            raise LockError(f"{identity} is not pinned in reference-schemas.toml")
        return self.deps[identity]

    def versions(self, identity: str) -> list[str]:
        return [self.pin(identity).version]

    def digest(self, identity: str) -> str:
        return self.pin(identity).sha256

    def members(self, identity: str) -> dict[str, bytes]:
        if identity not in self.loaded:
            try:
                self.loaded[identity] = remote.documents(self.get(self.pin(identity)))
            except remote.RemoteError as error:
                raise LockError(f"{identity}: {error}") from None
        return self.loaded[identity]

    def prefix(self, identity: str, version: str) -> str:
        return f"{identity.removeprefix('https://')}/{version}/"

    def files(self, identity: str, version: str) -> dict[str, bytes]:
        pinned = self.pin(identity).version
        if version != pinned:
            raise LockError(f"{identity} is pinned at {pinned}, not {version}")
        prefix = self.prefix(identity, version)
        return {m[len(prefix):]: d for m, d in self.members(identity).items()
                if m.startswith(prefix) and m.endswith(".schema.json")}

    def schemas(self, identity: str, version: str) -> dict[str, dict]:
        return {n: json.loads(d) for n, d in self.files(identity, version).items()}

    def requires_of(self, identity: str) -> dict:
        """What the package of a pinned module says it was locked against."""
        name = self.prefix(identity, self.pin(identity).version) + "oold.lock.json"
        if name not in self.members(identity):
            raise LockError(f"the package of {identity} carries no lock")
        data = json.loads(self.members(identity)[name])
        if data.get("lock_version") != 2:
            raise LockError(f"the lock in the package of {identity} is not a v2 lock")
        return data["requires"]


class Combined:
    """The repository's own modules and the pinned ones, told apart by namespace."""

    def __init__(self, own, pinned: Pinned) -> None:
        self.own, self.pinned = own, pinned

    @property
    def namespaces(self) -> list[str]:
        others = {d.namespace for d in self.pinned.deps.values()} - {CONFIG.namespace}
        return [CONFIG.namespace, *sorted(others)]

    def side(self, identity: str):
        return self.own if identity.rpartition("/")[0] == CONFIG.namespace else self.pinned

    def versions(self, identity: str) -> list[str]:
        return self.side(identity).versions(identity)

    def schemas(self, identity: str, version: str) -> dict[str, dict]:
        return self.side(identity).schemas(identity, version)

    def files(self, identity: str, version: str) -> dict[str, bytes]:
        return self.side(identity).files(identity, version)

    def digest(self, identity: str) -> str | None:
        return None if self.side(identity) is self.own else self.pinned.digest(identity)

    def requires_of(self, identity: str) -> dict:
        return {} if self.side(identity) is self.own else self.pinned.requires_of(identity)
