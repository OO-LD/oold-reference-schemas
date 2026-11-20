"""The registry of components: reference schemas kept in other repositories.

`components.toml` lists them. Each entry pins one version of one module by the digest of its
published package, and says in words what it is. The build downloads the package, checks the
digest and the lock inside it, and writes a catalog page: a card per component with links to its
own documentation. The core lists a component, it does not host or review its schemas.

A package is untrusted input. It is read as data only, never executed, and nothing from it is
shown except what is validated here: the lock's identity, version, specification edition and the
modules it cites. Titles and descriptions come from the registry, which maintainers review.

Usage:
  python scripts/components.py           verify every entry and write docs/components/index.md
  python scripts/components.py --check   verify every entry, write nothing
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import lock
import remote
from config import CONFIG, ROOT, ConfigError, Dependency, base_iri, dependencies

FILE = ROOT / "components.toml"
CACHE = ROOT / ".cache" / "packages"
PAGE = ROOT / "docs" / "components" / "index.md"

KEYS = {"title", "description", "repository", "site", "license", "namespace", "module",
        "version", "package", "sha256"}
LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,63}")
LIMITS = {"title": 80, "description": 400}
# What a rendered link may contain: nothing that could end a Markdown link or an HTML attribute.
SAFE_URL = re.compile(r"https://[^\s<>\"'`()\\]+")


class ComponentError(Exception):
    """A registry entry that is malformed or whose package does not hold up."""


@dataclass(frozen=True)
class Component:
    pin: Dependency
    title: str
    description: str
    repository: str
    site: str
    license: str


@dataclass(frozen=True)
class Package:
    """What the verified package says about itself."""

    spec_edition: str
    requires: tuple[str, ...]


def text(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ComponentError(f"{where}: {key} is missing")
    value = value.strip()
    if len(value) > LIMITS.get(key, 200) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ComponentError(f"{where}: {key} must be one short line of text")
    return value


def link(table: dict, key: str, where: str) -> str:
    try:
        value = base_iri(text(table, key, where), f"{where}: {key}")
    except ConfigError as error:
        raise ComponentError(str(error)) from None
    if not SAFE_URL.fullmatch(value):
        raise ComponentError(f"{where}: {key} contains a character a link cannot carry")
    return value


def parse(data: dict) -> tuple[Component, ...]:
    tables = data.get("component", [])
    if not isinstance(tables, list) or set(data) - {"component"}:
        raise ComponentError("components.toml holds only [[component]] tables")
    found: list[Component] = []
    for index, table in enumerate(tables, 1):
        where = f"component {index}"
        if not isinstance(table, dict) or set(table) - KEYS:
            raise ComponentError(f"{where}: unknown or malformed fields")
        try:
            (pin,) = dependencies([table], "components.toml")
        except ConfigError as error:
            raise ComponentError(f"{where}: {error}") from None
        licence = text(table, "license", where)
        if not LICENSE.fullmatch(licence):
            raise ComponentError(f"{where}: license must be an SPDX identifier, got {licence!r}")
        found.append(Component(pin, text(table, "title", where),
                               text(table, "description", where),
                               link(table, "repository", where), link(table, "site", where),
                               licence))
    spaces = [c.pin.namespace for c in found]
    for component in found:
        ns = component.pin.namespace
        if ns == CONFIG.namespace or CONFIG.owns(ns) or CONFIG.namespace.startswith(ns + "/"):
            raise ComponentError(f"{ns} overlaps the namespace of this repository")
        if any(o != ns and (o.startswith(ns + "/") or ns.startswith(o + "/")) for o in spaces):
            raise ComponentError(f"{ns} overlaps the namespace of another component")
    if len(set(spaces)) != len(spaces):
        raise ComponentError("two components share a namespace")
    return tuple(found)


def load(path: Path = FILE) -> tuple[Component, ...]:
    try:
        return parse(tomllib.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ComponentError(f"{path.name} not found") from None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ComponentError(f"{path.name} cannot be read: {error}") from None


def verify(component: Component, data: bytes) -> Package:
    """The package of an entry, if it is what the entry says. Anything else is an error."""
    pin = component.pin
    name = pin.identity
    if hashlib.sha256(data).hexdigest() != pin.sha256:
        raise ComponentError(f"{name}: the package does not match its pinned digest")
    try:
        members = remote.documents(data)
    except remote.RemoteError as error:
        raise ComponentError(f"{name}: {error}") from None
    base = name.removeprefix("https://")
    try:
        found = json.loads(members[f"{base}/{pin.version}/{lock.FILE}"])
    except (KeyError, ValueError):
        raise ComponentError(f"{name}: the package holds no readable {lock.FILE} "
                             f"for {pin.version}") from None
    problems = lock.validate(found)
    if problems or found["lock_version"] != lock.LOCK_VERSION:
        raise ComponentError(f"{name}: the lock is not a valid version {lock.LOCK_VERSION} lock"
                             f" ({'; '.join(problems) or 'old format'})")
    for key, expected in (("namespace", pin.namespace), ("module", pin.module),
                          ("version", pin.version)):
        if found[key] != expected:
            raise ComponentError(f"{name}: the lock says {key} {found[key]!r}, "
                                 f"the entry says {expected!r}")
    requires = found["requires"]
    for identity in requires:
        if not CONFIG.owns(identity + "/"):
            raise ComponentError(f"{name}: it may cite only modules of {CONFIG.namespace}, "
                                 f"got {identity!r}")
    allowed = [f"{base}/", *(f"{i.removeprefix('https://')}/" for i in requires)]
    for member in members:
        if not member.startswith(tuple(allowed)):
            raise ComponentError(f"{name}: {member!r} is not under a module the lock declares")
    cited = tuple(f"{i.removeprefix(CONFIG.namespace + '/')} {r['version']}"
                  for i, r in sorted(requires.items()))
    return Package(found["spec_edition"] or "none", cited)


def md(value: str) -> str:
    """Text that renders as itself: no HTML, no Markdown syntax."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", html.escape(value, quote=False))


def render(entries: list[tuple[Component, Package]]) -> str:
    lines = [
        "# Components",
        "",
        "Reference schemas kept in other repositories. Each builds on modules of this repository"
        " and is maintained by its own authors, with its own documentation. This page lists a"
        " component, it does not host or review its schemas. A component's namespace resolving"
        " is its own work: a listing does not make its identifiers dereference.",
        "",
    ]
    if not entries:
        lines += ["No components are listed yet.", ""]
    for component, package in entries:
        pin = component.pin
        lines += [
            f"## {md(component.title)}", "", md(component.description), "",
            "| | |", "| --- | --- |",
            f"| Module | `{pin.module}` {pin.version} |",
            f"| Namespace | `{pin.namespace}` |",
            f"| Licence | {md(component.license)} |",
            f"| Specification | {package.spec_edition} |",
            f"| Built on | {md(', '.join(package.requires)) or 'nothing'} |",
            f"| Documentation | <{component.site}> |",
            f"| Repository | <{component.repository}> |", "",
        ]
    return "\n".join(lines)


def build(components: tuple[Component, ...],
          get: Callable[[Dependency], bytes] | None = None) -> str:
    def fetch(pin: Dependency) -> bytes:
        try:
            return remote.fetch(pin.package, pin.sha256, CACHE)
        except remote.RemoteError as error:
            raise ComponentError(f"{pin.identity}: {error}") from None

    get = get or fetch
    return render([(c, verify(c, get(c.pin))) for c in components])


def main() -> None:
    try:
        components = load()
        page = build(components)
    except ComponentError as error:
        sys.exit(f"error: {error}")
    if "--check" not in sys.argv[1:]:
        PAGE.parent.mkdir(parents=True, exist_ok=True)
        PAGE.write_text(page, encoding="utf-8")
    print(f"  {len(components)} component(s) verified")


if __name__ == "__main__":
    main()
