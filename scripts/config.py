"""The identity of a collection of reference schemas, read from reference-schemas.toml.

The engine is shared between repositories, so nothing in it may name one of them. The
namespace is what schemas cite, the host is where their files are served, and everything
else a script needs to say about itself comes from here.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "reference-schemas.toml"


class ConfigError(Exception):
    """A missing or malformed reference-schemas.toml."""


@dataclass(frozen=True)
class Config:
    title: str
    repository: str
    namespace: str
    host: str

    @property
    def genid(self) -> str:
        """Base of the IRIs that stand in for blank nodes in a reading."""
        return f"{self.host}/.well-known/genid/"

    def iri(self, *parts: str) -> str:
        return "/".join((self.namespace, *parts))

    def owns(self, iri: str) -> bool:
        return iri.startswith(self.namespace + "/")

    def local(self, iri: str) -> list[str] | None:
        """The path segments of an IRI below the namespace, or None if it is not ours."""
        return iri[len(self.namespace) + 1:].split("/") if self.owns(iri) else None


def load(path: Path = FILE) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path.name} not found: create it at the repository root "
                          "with [project] and [namespace] tables") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path.name} is not valid TOML: {error}") from None

    def value(table: str, key: str) -> str:
        found = (data.get(table) or {}).get(key)
        if not isinstance(found, str) or not found:
            raise ConfigError(f"{path.name} lacks {table}.{key}")
        return found

    def https(table: str, key: str) -> str:
        found = value(table, key).rstrip("/")
        if not found.startswith("https://"):
            raise ConfigError(f"{table}.{key} must be an https IRI, got {found!r}")
        return found

    return Config(
        title=value("project", "title"),
        repository=https("project", "repository"),
        namespace=https("namespace", "iri"),
        host=https("namespace", "host"),
    )


CONFIG = load()
