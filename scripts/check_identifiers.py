"""Check that the identifiers the schemas hand out actually dereference.

A conformance IRI is a promise that something answers at that address. The promise is kept
by a redirect this repository does not own, so it can be true today and false tomorrow, and
nothing else in the build would notice: the schemas are published to their own host, and
every internal link points there.

Reports by default. `--require` is the pre-release gate and asks the only question that can
be answered before a release exists: does the redirect itself work. A version path cannot
resolve until the release publishes it, so requiring that beforehand would make the first
release impossible. `--verify` is the mirror, run after publishing, and requires every
version path to resolve.

Usage:
  python scripts/check_identifiers.py           report
  python scripts/check_identifiers.py --require the redirect resolves (before a release)
  python scripts/check_identifiers.py --verify  every version path resolves (after one)
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

from _shared import MODULES, module_version

IRI_BASE = "https://w3id.org/oo-ld/schemas"
TIMEOUT = 30


def resolves(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return 200 <= response.status < 300, f"{response.status} {response.url}"
    except urllib.error.HTTPError as error:
        return False, f"{error.code}"
    except Exception as error:  # noqa: BLE001 - a name that does not resolve is a result
        return False, str(error)


def redirect_works() -> bool:
    """Whether the w3id redirect resolves at all, tested on a path that always exists.

    A released version and the redirect fail the same way, with a 404, and the fix for
    each is different: one waits for a release, the other for a namespace change.
    """
    for module_dir in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        schemas = sorted(module_dir.glob("*.schema.json"))
        if schemas:
            # a file rather than a directory: a directory without its trailing slash is a
            # 404 on the hosting side, which would look like a broken redirect
            ok, _ = resolves(f"{IRI_BASE}/{module_dir.name}/dev/{schemas[0].name}")
            return ok
    return False


def main() -> None:
    require = "--require" in sys.argv
    verify = "--verify" in sys.argv
    redirect = redirect_works()
    failures = 0
    for module_dir in sorted(d for d in MODULES.iterdir() if d.is_dir()):
        module = module_dir.name
        schemas = sorted(module_dir.glob("*.schema.json"))
        if not schemas:
            continue
        version = module_version(module)
        targets = [f"{IRI_BASE}/{module}/{version}",
                   f"{IRI_BASE}/{module}/{version}/{schemas[0].stem}.json"]
        for url in targets:
            ok, detail = resolves(url)
            print(f"  {'ok  ' if ok else 'fail'} {url} -> {detail}")
            failures += not ok

    if failures and redirect:
        print(f"{failures} identifier(s) do not resolve, though the w3id redirect itself does: "
              "these versions have not been released yet, so only <module>/dev/ is published.")
    elif failures:
        print(f"{failures} identifier(s) do not resolve, and neither does the redirect itself. "
              "Check the oo-ld namespace at https://github.com/perma-id/w3id.org.")
    if require and not redirect:
        print("the w3id redirect does not resolve, so a release would mint identifiers that "
              "answer nothing. Check the oo-ld namespace at "
              "https://github.com/perma-id/w3id.org.")
        sys.exit(1)
    if verify and failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
