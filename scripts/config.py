"""The identity of a collection of reference schemas, read from reference-schemas.toml.

The engine is shared between repositories, so nothing in it may name one of them. The
namespace is what schemas cite, the host is where their files are served, and everything
else a script needs to say about itself comes from here.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # noqa: UP036 - the message is the point
    raise SystemExit("error: the engine needs Python 3.11 or newer (it reads TOML with tomllib)")

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

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


def base_iri(value: str, where: str) -> str:
    """An https base IRI without trailing slash. Appending a path to it must stay valid."""
    if value[:8].lower() != "https://":
        raise ConfigError(f"{where} must be an https IRI, got {value!r}")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ConfigError(f"{where} must not contain whitespace or control characters")
    if "?" in value or "#" in value:
        raise ConfigError(f"{where} must not contain a query or a fragment, got {value!r}")
    try:
        parts = urlsplit(value)
        host, _ = parts.hostname, parts.port
    except ValueError as error:
        raise ConfigError(f"{where} is not a valid IRI ({error}), got {value!r}") from None
    if not host or parts.username is not None or parts.password is not None:
        raise ConfigError(f"{where} needs a host and no credentials, got {value!r}")
    return "https://" + value[8:].rstrip("/")


def load(path: Path = FILE) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path.name} not found: create it at the repository root "
                          "with [project] and [namespace] tables") from None
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path.name} cannot be read: {error}") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path.name} is not valid TOML: {error}") from None

    def value(table: str, key: str) -> str:
        section = data.get(table)
        if not isinstance(section, dict):
            raise ConfigError(f"{path.name} lacks the [{table}] table")
        found = section.get(key)
        if not isinstance(found, str) or not found.strip():
            raise ConfigError(f"{path.name} lacks {table}.{key}")
        return found.strip()

    return Config(
        title=value("project", "title"),
        repository=base_iri(value("project", "repository"), "project.repository"),
        namespace=base_iri(value("namespace", "iri"), "namespace.iri"),
        host=base_iri(value("namespace", "host"), "namespace.host"),
    )


def _default() -> Config:
    try:
        return load()
    except ConfigError as error:
        raise SystemExit(f"error: {error}") from None


CONFIG = _default()
