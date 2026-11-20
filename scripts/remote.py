"""Fetch a package of another repository, safely.

The pinned sha256 is what makes the artifact trustworthy: it is checked before anything reads
the bytes, and a cache hit is checked again. The download itself is bounded and may only reach
public https addresses, redirects included. A name can still change its answer between the
address check and the connection, which is why the digest, not the address, is the guarantee.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import socket
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

MAX_BYTES = 50_000_000
MAX_MEMBERS = 2000
MAX_UNPACKED = 200_000_000
TIMEOUT = 30


class RemoteError(Exception):
    """A package that cannot be fetched or does not match its pin."""


def check_url(url: str, resolve=socket.getaddrinfo) -> None:
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        raise RemoteError(f"not a valid URL: {url!r}") from None
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or port not in (None, 443)):
        raise RemoteError(f"only plain https URLs on the default port are fetched: {url!r}")
    for info in resolve(parts.hostname, 443):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise RemoteError(f"{parts.hostname} resolves to a non public address")


def redirects(resolve=socket.getaddrinfo) -> urllib.request.HTTPRedirectHandler:
    class Handler(urllib.request.HTTPRedirectHandler):
        max_redirections = 3

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            check_url(newurl, resolve)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return Handler()


def fetch(url: str, sha256: str, cache: Path, opener=None, resolve=socket.getaddrinfo) -> bytes:
    """The package at `url` if it has the pinned digest, from the cache when it is there."""
    path = cache / f"{sha256}.zip"
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
        return path.read_bytes()
    check_url(url, resolve)
    opener = opener or urllib.request.build_opener(redirects(resolve))
    try:
        with opener.open(url, timeout=TIMEOUT) as response:
            data = response.read(MAX_BYTES + 1)
    except OSError as error:  # URLError and HTTPError are OSErrors
        raise RemoteError(f"{url} could not be fetched: {error}") from None
    if len(data) > MAX_BYTES:
        raise RemoteError(f"{url} is larger than {MAX_BYTES} bytes")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise RemoteError(f"{url} does not match its pinned digest")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def documents(data: bytes) -> dict[str, bytes]:
    """The members of a package by name, refusing an archive that is too large."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = [i for i in archive.infolist() if not i.is_dir()]
            if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNPACKED:
                raise RemoteError("the package holds more than is allowed")
            return {i.filename: archive.read(i) for i in infos}
    except zipfile.BadZipFile:
        raise RemoteError("the package is not a zip archive") from None
