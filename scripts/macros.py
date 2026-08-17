"""Documentation macros, shared with the OO-LD core repository.

A schema page embeds the schema it documents rather than paraphrasing it, so the page cannot
drift from what is published. `inline_file` renders a repository file as tabs (JSON, and the
same content as YAML), which keeps a schema readable for people who find JSON punctuation
noisy. `oold_schema_renderer`, `oold_schema_terms` and `oold_schema_meta_data` render a schema
as a vocabulary, an instance and its RDF readings.

Nothing here is specific to one repository.
"""
import json
import os
import re

# The repository root, one level up: this module lives beside the generators it
# shares its rules with.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Derived artefacts (RDF readings, synthesized instances, ontology labels), mirroring the
# layout of modules/. Kept out of docs/ so everything under docs/ is editable source, and
# committed so a mapping change shows its effect on the graph in review.
GENERATED = os.path.join(ROOT, "generated")

# Render target, set by each renderer ("docs" for zensical, "spec" for the ReSpec
# renderer). `_example_tabs` branches on it.
TARGET = "docs"

# Fence language inferred from the file extension for inline_file(lang="auto").
_LANG_BY_EXT = {
    ".json": "json", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
    ".py": "python", ".mjs": "javascript", ".js": "javascript",
    ".sh": "bash", ".ttl": "turtle", ".html": "html",
}


_ex_counter = [0]  # unique ids for the spec's tab panels within one render


def _json_to_yaml(text):
    """Convert JSON text to block-style YAML (keys kept in source order), or None
    if conversion is unavailable. pyyaml is provided by the spec renderer (uv,
    PEP 723) and the docs build (uvx --with pyyaml); if it is missing, or the
    text is not a full JSON document, callers fall back to a plain JSON block."""
    try:
        import yaml  # noqa: PLC0415 - optional; imported lazily so macros load without it
    except Exception:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
    ).rstrip("\n")


def _fence(lang, text):
    return f"```{lang}\n{text}\n```"


def _docs_tabs(json_text, yaml_text):
    """JSON + 'View as YAML' as pymdownx content tabs (fence + content indented
    under each tab marker)."""
    def blk(lang, text):
        return "\n".join(("    " + ln).rstrip() for ln in [f"```{lang}", *text.split("\n"), "```"])
    return f'=== "JSON"\n\n{blk("json", json_text)}\n\n=== "View as YAML"\n\n{blk("yaml", yaml_text)}'


def _spec_tabs(json_text, yaml_text):
    """JSON + 'View as YAML' as a small HTML tab widget for the ReSpec spec.

    The code stays in Markdown fences (blank-line separated from the container
    tags) so mistune still renders them as <pre><code>, keeping ReSpec syntax
    highlighting and staying out of reach of the RFC 2119 wrapper. The spec
    renderer supplies the CSS and JS that style and toggle these tabs."""
    _ex_counter[0] += 1
    n = _ex_counter[0]

    def panel(pid, lang, text, hidden):
        return f'<div class="ex-panel" id="{pid}" role="tabpanel"{" hidden" if hidden else ""}>\n\n{_fence(lang, text)}\n\n</div>'

    return (
        '<div class="ex-tabs">\n'
        '<div class="ex-tablist" role="tablist">'
        f'<button class="ex-tab" role="tab" aria-selected="true" data-panel="ex{n}j">JSON</button>'
        f'<button class="ex-tab" role="tab" aria-selected="false" data-panel="ex{n}y">View as YAML</button>'
        '</div>\n\n'
        f'{panel(f"ex{n}j", "json", json_text, False)}\n\n'
        f'{panel(f"ex{n}y", "yaml", yaml_text, True)}\n\n'
        '</div>'
    )


def _example_tabs(json_text):
    """Render JSON (main) + 'View as YAML' tabs, or a plain JSON block when YAML
    conversion is unavailable. Target-aware (docs vs spec)."""
    yaml_text = _json_to_yaml(json_text)
    if yaml_text is None:
        return _fence("json", json_text)
    return _spec_tabs(json_text, yaml_text) if TARGET == "spec" else _docs_tabs(json_text, yaml_text)


def inline_file(path, lang="auto"):
    """Inline any repo file. JSON content renders as JSON (main) + 'View as YAML'
    tabs; other languages stay a single fenced block.

    `path` is relative to the repo root (no hardcoded directory prefix). With
    lang="auto" the fence language is inferred from the file extension.
    """
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        content = fh.read().rstrip("\n")
    if lang == "auto":
        lang = _LANG_BY_EXT.get(os.path.splitext(path)[1].lower(), "")
    return _example_tabs(content) if lang == "json" else _fence(lang, content)


def example(name, lang="json"):
    """Inline an example schema (examples/<name>.schema.json) as JSON/YAML tabs."""
    path = f"examples/{name}.schema.json"
    if not os.path.exists(os.path.join(ROOT, path)):
        return f"No example named `{name}`."
    return inline_file(path, lang)


def _keyword_rows(properties, prefix):
    """(keyword, description) rows for properties whose name starts with prefix.

    `prefix` may be a tuple, so dialect entries that keep an external standard's
    name (`@context`, `x-oold-sssom`) are listed alongside the `x-oold-*` ones.
    """
    rows = []
    for name, defn in (properties or {}).items():
        if name.startswith(prefix):
            desc = " ".join((defn.get("description") or "").split()).replace("|", "\\|")
            rows.append((name, desc))
    return rows


def _keyword_table(rows):
    lines = ["| Keyword | Description |", "| --- | --- |"]
    lines += [f"| `{name}` | {desc} |" for name, desc in rows]
    return "\n".join(lines)


def _keyword_properties(schema):
    """Keyword definitions of a schema: top-level `properties` plus any
    `$defs/<name>/properties`. The UI meta-schema keeps its keywords under
    $defs.keywords so the core schema can $ref just them, so a plain top-level
    scan would miss them."""
    props = dict(schema.get("properties") or {})
    for defn in (schema.get("$defs") or {}).values():
        if isinstance(defn, dict):
            props.update(defn.get("properties") or {})
    return props


def render_schema(path, prefix="x-"):
    """Render the extension-keyword table for one schema file (repo-relative).

    Collects keywords from the top-level `properties` and from
    `$defs/*/properties`, keeping those whose name starts with `prefix`
    (default "x-", so x-oold-*, x-oold-ui-*, x-enum-*, ... are all included).
    """
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        schema = json.load(fh)
    return _keyword_table(_keyword_rows(_keyword_properties(schema), prefix))


def vocabulary():
    """Render the core x-oold-* keyword table from every meta/*.json top-level
    `properties` (single source). Dialect keywords kept under $defs (e.g. the UI
    meta-schema's x-oold-ui-*) get their own section via render_schema, so they
    are not duplicated here."""
    meta_dir = os.path.join(ROOT, "meta")
    if not os.path.isdir(meta_dir):
        return "No meta-schemas in this repository."
    rows = []
    for fname in sorted(os.listdir(meta_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(meta_dir, fname), encoding="utf-8") as fh:
            rows += _keyword_rows(json.load(fh).get("properties"),
                                  ("x-oold-", "x-oold-sssom", "@context"))
    return _keyword_table(rows)


# Schema tabs.
# A schema page shows one schema five ways: its terms, the schema as JSON and as YAML,
# an instance of it, and that instance expanded to RDF under each mapping set.
# The RDF fragments are precomputed by scripts/build_docs.py, because expanding
# JSON-LD needs a processor that the documentation build should not carry.

NL = chr(10)


def _tab_group(panels):
    """Material-style tabbed block from [(label, body), ...], body being Markdown."""
    out = []
    for label, body in panels:
        indented = "\n".join(("    " + ln).rstrip() for ln in body.split("\n"))
        out.append(f'=== "{label}"\n\n{indented}')
    return "\n\n".join(out)


def _published_refs(text, module):
    """Rewrite an instance's relative `$schema` and `@context` to the published IRI.

    A committed instance points at the schema beside it, so it validates in a checkout
    without a network. What a reader should copy is the published identifier, so the
    documentation shows that instead of the repository-local path.
    """
    doc = json.loads(text)
    base = f"{IRI_BASE}/{module}/{module_version(module)}/"

    def absolute(value):
        if isinstance(value, str) and value.endswith(".schema.json")                 and not value.startswith(("http://", "https://")):
            return base + value.rsplit("/", 1)[-1]
        if isinstance(value, list):
            return [absolute(item) for item in value]
        return value

    for key in ("$schema", "@context"):
        if key in doc:
            doc[key] = absolute(doc[key])
    return json.dumps(doc, indent=2, ensure_ascii=False)


def oold_schema_renderer(module, name, page=None):
    """Render a schema as terms / JSON / YAML / instance / RDF tabs.

    `module` is the modules/ subdirectory, `name` the schema file stem, e.g.
    schema_tabs("quantities", "QuantityValue"). The term table comes first: it is the
    reading of the schema, where the other tabs are the schema itself and what it produces.

    `page` names the page being rendered, relative to docs/, and is only needed where a
    schema is embedded outside its own page. Links inside the tables are relative,
    so they are computed against that page.
    """
    base = os.path.join(ROOT, "modules", module)
    schema_path = os.path.join(base, f"{name}.schema.json")
    with open(schema_path, encoding="utf-8") as fh:
        schema_text = fh.read().rstrip(NL)

    panels = [("Terms", oold_schema_terms(module, name, page)),
              ("JSON", _fence("json", schema_text))]
    yaml_text = _json_to_yaml(schema_text)
    if yaml_text is not None:
        panels.append(("YAML", _fence("yaml", yaml_text)))

    # a committed instance is authoritative; otherwise the one built from the schema's
    # own examples and defaults by scripts/build_docs.py
    for instance_path, label in (
        (os.path.join(base, f"{name}.instance.json"), "Instance"),
        (os.path.join(GENERATED, module, f"{name}.instance.json"), "Instance"),
    ):
        if os.path.exists(instance_path):
            with open(instance_path, encoding="utf-8") as fh:
                panels.append((label, _fence("json", _published_refs(fh.read(), module))))
            break

    readings = []
    rdf_dir = os.path.join(GENERATED, module)
    if os.path.isdir(rdf_dir):
        for fname in sorted(os.listdir(rdf_dir)):
            if not fname.startswith(f"{name}.") or not fname.endswith(".ttl"):
                continue
            with open(os.path.join(rdf_dir, fname), encoding="utf-8") as fh:
                readings.append((fname[len(name) + 1:-4], fh.read().rstrip(NL)))
    if readings:
        panels.append(("RDF", _rdf_panel(readings)))

    return _tab_group(panels)


def _rdf_panel(readings):
    """The RDF tab: one reading at a time, chosen from a mapping-set dropdown.

    A tab per mapping set would grow with every community that maps the schema, and would
    put the choice of vocabulary on the same footing as the choice of serialization, which
    it is not. Consensus first, since that is what an instance means without a selection.

    The readings are plain code blocks carrying the set they belong to. Without JavaScript
    they stack, each labelled, rather than disappearing.
    """
    _GROUP_ID[0] += 1
    group = f"rdf-{_GROUP_ID[0]}"
    readings = sorted(readings, key=lambda r: r[0] != "consensus")
    options = "".join(f'<option value="{label}">{label}</option>' for label, _ in readings)
    select = (f'<div class="mapping-select"><label for="{group}">Mapping set</label>'
              f'<select id="{group}" data-mapping-select="{group}">{options}</select></div>')
    blocks = [f'```{{.turtle .mapping-set data-group="{group}" data-set="{label}"}}{NL}'
              f'{text}{NL}```' for label, text in readings]
    return select + NL + NL + (NL + NL).join(blocks)


# Mapping sets.
# The sets are derived from the schemas by scripts/build_mappings.py and rendered here, so
# a set page and the term tables cannot disagree: both read the same mappings.


MAPPINGS = os.path.join(GENERATED, "mappings")


def _sssom(name):
    """Rows of a generated SSSOM set, with its commented YAML preamble stripped."""
    path = os.path.join(MAPPINGS, f"{name}.sssom.tsv")
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#")]
    if not lines:
        return [], []
    header = lines[0].split("\t")
    return header, [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln]


def _set_page(name):
    return os.path.join(ROOT, "docs", "mappings", name, "index.md")


def _set_link(name, from_page):
    """Relative link from a page to a mapping set page, or None when there is none."""
    target = _set_page(name)
    if not os.path.exists(target) or not from_page:
        return None
    return os.path.relpath(_url(target), _url(from_page)).replace(os.sep, "/") + "/"


def _all_contexts():
    """Every term definition in the library, for resolving the IRIs a set refers to."""
    ctx = {}
    for module in sorted(os.listdir(os.path.join(ROOT, "modules"))):
        base = os.path.join(ROOT, "modules", module)
        if not os.path.isdir(base):
            continue
        for fname in sorted(os.listdir(base)):
            if fname.endswith(".schema.json"):
                ctx.update(_ctx_of(_read(os.path.join(base, fname))))
    return ctx


def _definition_of(term):
    """The module and schema that declare a term, searched across the library."""
    base = os.path.join(ROOT, "modules")
    for module in sorted(os.listdir(base)):
        if os.path.isdir(os.path.join(base, module)):
            schema = _defining_schema(module, term)
            if schema:
                return module, schema
    return None, None


def _term_link(term, page):
    """A term rendered as a link to the schema that defines it, where one is found."""
    module, schema = _definition_of(term)
    href = _page_link(module, schema, page) if schema else None
    return f'<a href="{href}"><code>{term}</code></a>' if href else f"<code>{term}</code>"


def _defining_schema(module, term):
    """The schema of a module that declares a term, for linking a mapping to its source."""
    base = os.path.join(ROOT, "modules", module)
    if not os.path.isdir(base):
        return None
    for fname in sorted(os.listdir(base)):
        if not fname.endswith(".schema.json"):
            continue
        schema = _read(os.path.join(base, fname))
        if term in _ctx_of(schema) or term in (schema.get("x-oold-context") or {}):
            return fname[: -len(".schema.json")]
    return None


def sssom_table(name):
    """One SSSOM mapping set as a table: what a vocabulary calls each term of the library.

    Reads the generated set by name rather than a path, because the columns rendered here
    are SSSOM slots: subject, predicate, object and the version the object came from.
    """
    header, rows = _sssom(name)
    if not rows:
        return f"No mappings are declared for `{name}`."
    ctx = _all_contexts()

    page = _set_page(name)
    out = ["<table><thead><tr><th>Schema term</th><th>Predicate</th><th>Mapped to</th>"
           "<th>Source version</th></tr></thead><tbody>"]
    for row in rows:
        note = row.get("comment") or ""
        version = row.get("object_source_version") or ""
        term = row["subject_label"]
        out.append(
            "<tr>"
            f"<td>{_term_link(term, page)}</td>"
            f'<td>{row["predicate_id"].split(":")[-1]}</td>'
            f'<td>{_link(row["object_id"], ctx)}'
            + (f"<br><small>{note}</small>" if note else "")
            + "</td>"
            f'<td><small>{version}</small></td>'
            "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


INVERSE = {
    "skos:broadMatch": "skos:narrowMatch",
    "skos:narrowMatch": "skos:broadMatch",
}


def _oriented(name, source):
    """Rows of a crosswalk read from one side.

    A set is stored once per unordered pair, so half the views are the stored direction
    reversed. Reversing swaps broader and narrower and leaves the symmetric predicates
    alone, which is what SSSOM calls a mapping inversion.
    """
    _, rows = _sssom(os.path.join("crosswalks", name))
    if name.split("-", 1)[0] == source:
        return rows
    flipped = []
    for row in rows:
        entry = dict(row)
        entry["subject_id"], entry["object_id"] = row["object_id"], row["subject_id"]
        entry["predicate_id"] = INVERSE.get(row["predicate_id"], row["predicate_id"])
        flipped.append(entry)
    return flipped


def mapping_crosswalk_table(name, source=None, page=None):
    """One derived crosswalk as a table: what two communities call the same thing."""
    rows = _oriented(name, source or name.split("-", 1)[0])
    if not rows:
        return f"Nothing chains between the two sets of `{name}`."
    ctx = _all_contexts()
    out = ["<table><thead><tr><th>Term</th><th>Predicate</th><th>Term</th>"
           "<th>Chained through</th></tr></thead><tbody>"]
    for row in rows:
        via = (row.get("comment") or "").replace("chained through ", "")
        out.append(
            "<tr>"
            f'<td>{_link(row["subject_id"], ctx)}</td>'
            f'<td>{row["predicate_id"].split(":")[-1]}</td>'
            f'<td>{_link(row["object_id"], ctx)}</td>'
            f"<td>{_term_link(via, page) if via else ''}</td>"
            "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def mapping_crosswalks(source=None):
    """Derived crosswalks, grouped by the set they are read from.

    Each pair appears under both of its sets, because the question is asked from one side:
    someone working in EMMO wants everything EMMO relates to, not the half of the pairs
    whose name happens to start with an e. The data is stored once per pair and the other
    direction is rendered by inverting it.
    """
    base = os.path.join(MAPPINGS, "crosswalks")
    if not os.path.isdir(base):
        return "No crosswalks have been derived yet."
    pairs = [f[: -len(".sssom.tsv")] for f in sorted(os.listdir(base))
             if f.endswith(".sssom.tsv")]
    names = sorted({part for pair in pairs for part in pair.split("-", 1)})

    sections = []
    page = _set_page(source) if source else os.path.join(
        ROOT, "docs", "mappings", "crosswalks", "index.md")
    for current in ([source] if source else names):
        blocks = []
        for pair in pairs:
            left, right = pair.split("-", 1)
            if current not in (left, right):
                continue
            other = right if current == left else left
            rows = _oriented(pair, current)
            blocks.append(
                f"<details><summary><strong>{current} to {other}</strong>: "
                f"{len(rows)} mappings</summary>{mapping_crosswalk_table(pair, current, page)}"
                f'<p><a href="/mappings/crosswalks/{pair}.sssom.tsv">Download '
                f"<code>{pair}.sssom.tsv</code></a></p></details>")
        if blocks:
            sections.append("".join(blocks) if source
                            else f"### From {current}" + NL + NL + "".join(blocks))
    if not sections:
        return f"Nothing chains from `{source}` to another set."
    return (NL + NL).join(sections)


def download(path, note=""):
    """Link to a file published at the site root, with its size.

    `path` is the published path, so the link reads the same here and on the site. The
    file is read from the repository to state its size, which is what tells a reader
    whether this is a copy-paste or a download.
    """
    source = os.path.join(ROOT, "docs", path.lstrip("/"))
    if not os.path.exists(source):
        return f"`{path}` is not published."
    size = os.path.getsize(source)
    scale = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} bytes"
    detail = f", {note}" if note else ""
    return f"[Download `{os.path.basename(path)}`]({path}) ({scale}{detail})"


# Schema metadata: version, lineage and published location, rendered from the schemas so a
# page cannot claim a parent the schema does not have.


IRI_BASE = "https://w3id.org/oo-ld/schemas"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def module_version(module, full=False):
    """The version a module publishes under, from its module.json.

    Falls back to the highest x-oold-version among its schemas while a module has no
    module.json, so a module in progress still renders.
    """
    base = os.path.join(ROOT, "modules", module)
    path = os.path.join(base, "module.json")
    if os.path.exists(path):
        version = _read(path).get("version") or "0.1.0"
    else:
        versions = [_read(os.path.join(base, f)).get("x-oold-version") or ""
                    for f in sorted(os.listdir(base)) if f.endswith(".schema.json")]
        version = max([v for v in versions if v] or ["0.1.0"])
    return version if full else ".".join(version.split(".")[:2])


def _parents(module, name):
    schema = _read(os.path.join(ROOT, "modules", module, f"{name}.schema.json"))
    return [ref["$ref"][: -len(".schema.json")]
            for ref in (schema.get("allOf") or [])
            if isinstance(ref, dict) and isinstance(ref.get("$ref"), str)]


def _children(module, name):
    base = os.path.join(ROOT, "modules", module)
    target = f"{name}.schema.json"
    out = []
    for fname in sorted(os.listdir(base)):
        if not fname.endswith(".schema.json") or fname == target:
            continue
        refs = [r.get("$ref") for r in (_read(os.path.join(base, fname)).get("allOf") or [])
                if isinstance(r, dict)]
        if target in refs:
            out.append(fname[: -len(".schema.json")])
    return out


def _channel():
    """Which published tree this build documents: `dev` or a release.

    A documentation snapshot describes the state it was built from, so its links belong to
    that state: the `dev` snapshot documents the tip of main, served at `<module>/dev/`,
    and a snapshot built for a release documents the frozen files at `<module>/<version>/`.
    Deciding it from the release index instead would make the `dev` pages link released
    files as soon as any release exists, while describing unreleased ones.
    """
    return "release" if os.environ.get("OOLD_CHANNEL") == "release" else "dev"


def _earlier(module, version):
    """Module versions released before this one, with the dated docs that described them.

    Read from the release index rather than from the published site, so a page never
    advertises a version nobody can fetch.
    """
    path = os.path.join(GENERATED, "versions.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh).get(module) or []
    short = ".".join(version.split(".")[:2])
    return [e for e in entries if ".".join(e["module"].split(".")[:2]) != short]


def _walkthrough(module, name, from_page):
    """Link into the section of the walkthrough that embeds this schema, if any.

    Found by looking for the macro call rather than by a list kept in step by hand, so a
    schema that leaves the tutorial loses the link on its own.
    """
    source = os.path.join(ROOT, "docs", "how-it-works.md")
    if not os.path.exists(source) or not from_page:
        return None
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    marker = f'schema_tabs("{module}", "{name}")'
    if marker not in text:
        return None
    heading = ""
    for line in text[: text.index(marker)].split("\n"):
        if line.startswith("## "):
            heading = line[3:].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    rel = os.path.relpath(_url(source), _url(from_page)).replace(os.sep, "/")
    return f"{rel}/#{slug}" if slug else f"{rel}/"


def oold_schema_meta_data(module, name):
    """Module, version, lineage and permanent location of a schema, as a bullet list."""
    version = module_version(module)
    _page_link(module, name, None)  # warms the page index
    page = _PAGES.get((module, name))

    def link(other):
        href = _page_link(module, other, page)
        return f"[{other}]({href})" if href else f"`{other}`"

    lines = [f"- module: `{module}` {module_version(module, full=True)}"]
    parents = _parents(module, name)
    if parents:
        lines.append("- extends: " + ", ".join(link(p) for p in parents) + " (`allOf`)")
    children = _children(module, name)
    if children:
        lines.append("- extended by: " + ", ".join(link(c) for c in children))
    walk = _walkthrough(module, name, page)
    if walk:
        lines.append(f"- explained in: [How it works]({walk})")
    # Rooted, not relative: these are published at the site root and must not move when the
    # surrounding documentation is versioned. Which tree they point at follows the build,
    # so a page always links what it describes.
    channel = version if _channel() == "release" else "dev"
    # Conformance is per module: the schemas of a module share one context and are not
    # meaningful apart from it, so the module version is what an instance declares with
    # `dct:conformsTo` and what a consumer pins. The schema itself is named by its file.
    lines.append(f"- conforms to: [`{IRI_BASE}/{module}/{version}`](/{module}/{channel}/), "
                 "the module at this version")
    path = f"/{module}/{channel}/{name}.schema.json"
    note = "" if channel != "dev" else (f" (the tip of main, which this page documents; "
                                        f"a release freezes it at `/{module}/{version}/`)")
    lines.append(f"- schema file: [`{path}`]({path}){note}")
    earlier = _earlier(module, module_version(module, full=True))
    if earlier:
        # the docs for an older module version are the dated site release that shipped it
        lines.append("- earlier versions: " + ", ".join(
            f"[{e['module']}](/{e['docs']}/)" for e in earlier))
    return NL.join(lines)


# Schema term table.
# Rendered from the schema rather than written by hand, so the documentation cannot
# drift from what is published. Existing JSON Schema doc generators cover the
# structural half well but know nothing about @context / x-oold-context, which is the
# half that carries the meaning here, so the traversal is implemented here.


def _labels():
    """Committed label map, so an opaque IRI can be shown by its name (see
    scripts/extract_labels.py). Absent labels simply fall back to the compact IRI."""
    path = os.path.join(GENERATED, "labels.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_LABELS = None


def _ctx_of(schema):
    """The schema's own context object (the inline part of a possibly-list @context)."""
    ctx = schema.get("@context")
    if isinstance(ctx, list):
        merged = {}
        for part in ctx:
            if isinstance(part, dict):
                merged.update(part)
        return merged
    return ctx or {}


def _expand(iri, ctx):
    """Expand a CURIE against the context prefixes; pass full IRIs through."""
    if not isinstance(iri, str) or iri.startswith(("http://", "https://")):
        return iri
    if ":" in iri:
        prefix, _, rest = iri.partition(":")
        base = ctx.get(prefix)
        if isinstance(base, str) and base.startswith(("http://", "https://")):
            return base + rest
    return iri


def _compact(iri, ctx):
    """`prefix:local` for an IRI a context declares a prefix for, else None."""
    best = None
    for prefix, value in ctx.items():
        if (isinstance(value, str) and value.endswith(("#", "/", ":"))
                and iri.startswith(value) and (best is None or len(value) > len(best[1]))):
            best = (prefix, value)
    return f"{best[0]}:{iri[len(best[1]):]}" if best else None


def _link(iri, ctx):
    """Link an ontology term: its label where one is known, its compact form otherwise,
    always pointing at the full IRI."""
    global _LABELS
    if _LABELS is None:
        _LABELS = _labels()
    full = _expand(iri, ctx)
    if not isinstance(full, str):
        return f"<code>{iri}</code>"
    compact = _compact(full, ctx)
    entry = _LABELS.get(full)
    prefix = compact.split(":", 1)[0] if compact else ""
    if entry and prefix:
        text = f"{prefix}:{entry['label']}"
    elif entry:
        text = entry["label"]
    else:
        text = compact or iri
    if full.startswith(("http://", "https://")):
        return f'<a href="{full}">{text}</a>'
    return f"<code>{text}</code>"


def _term_target(defn):
    """The IRI a @context term maps to, whether written compact or expanded."""
    return defn.get("@id") if isinstance(defn, dict) else defn


def _constraints(spec, enum=True):
    """Type and the constraints a reader needs, as one compact cell.

    `enum=False` names the constraint without listing the permitted values, for a property
    whose values are context terms and therefore already listed as alias rows underneath it.
    """
    if not isinstance(spec, dict):
        return ""
    bits = []
    t = spec.get("type")
    if t:
        bits.append(f"<code>{t if isinstance(t, str) else '/'.join(t)}</code>")
    if spec.get("format"):
        bits.append(f"format <code>{spec['format']}</code>")
    if spec.get("enum"):
        bits.append("one of " + ", ".join(f"<code>{e}</code>" for e in spec["enum"])
                    if enum else "enum")
    if "default" in spec:
        bits.append(f"default <code>{json.dumps(spec['default'])}</code>")
    return ", ".join(bits)


_PAGES = None
_CALL = re.compile(r"oold_schema_(?:renderer|terms)\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+)[\"']")


def _pages():
    """Map (module, schema) to the page that documents it.

    Read off the pages themselves rather than assumed from the schema name: the tree nests
    along the inheritance chain, so a page is `<name>.md` or `<dir>/index.md` depending on
    whether the schema has subschemas, and only the tree knows which.
    """
    found = {}
    root = os.path.join(ROOT, "docs", "modules")
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, encoding="utf-8") as fh:
                for module, schema in _CALL.findall(fh.read()):
                    found.setdefault((module, schema), path)
    return found


def _page_link(module, schema, from_page):
    """Relative link to a schema's page, or None when it has no page."""
    global _PAGES
    if _PAGES is None:
        _PAGES = _pages()
    target = _PAGES.get((module, schema))
    if not target or not from_page or target == from_page:
        return None
    # relative to the rendered URL, not to the source file: a leaf page gets its own
    # directory (page.md -> page/), so the two differ by one level
    rel = os.path.relpath(_url(target), _url(from_page)).replace(os.sep, "/")
    return rel + "/"


def _url(path):
    """The directory URL a source page is published at, relative to docs/."""
    rel = os.path.relpath(path, os.path.join(ROOT, "docs")).replace(os.sep, "/")
    rel = rel[: -len(".md")]
    return rel[: -len("/index")] if rel.endswith("/index") else rel


def _set_name(iri):
    """Short name of a mapping set, from its identifier."""
    return iri.rstrip("/").rsplit("/", 1)[-1].removesuffix(".sssom.tsv")


def _alternatives(term, syn, ctx, page=None):
    """Alternative mappings for one term.

    Each entry names its mapping set, links the term, and keeps the SSSOM qualifier and
    comment, which is where the honest caveats live. Shown in full rather than collapsed:
    the mappings are the point of the table, and a reader comparing two communities should
    not have to open every row to do it.
    """
    items = []
    for iri, frag in (syn.get(term) or {}).items():
        if not isinstance(frag, dict):
            continue
        meta = frag.get("x-oold-sssom") or {}
        setid = _set_name(meta.get("mapping_set_id") or "") or "?"
        pred = meta.get("predicate_id", "skos:exactMatch").split(":")[-1]
        note = meta.get("comment", "")
        qualifier = "" if pred == "exactMatch" else f" <em>{pred}</em>"
        detail = f"<br><small>{note}</small>" if note else ""
        href = _set_link(setid, page)
        tag = f'<a href="{href}">{setid}</a>' if href else setid
        items.append(f"<li><strong>{tag}</strong>: {_link(iri, ctx)}{qualifier}{detail}</li>")
    if not items:
        return "-"
    return f'<ul class="mappings">{"".join(items)}</ul>'


INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"

# Above this many permitted values the alias rows are collapsed into one: a unit list can
# run to dozens of entries, which would bury the properties of the schema.
ALIAS_LIMIT = 3

TIPS = {
    "type alias": "A value of the type field that the context expands to a class IRI, "
                  "so an instance names its class with a short token instead of an IRI",
    "value alias": "A permitted value that the context expands to an IRI, because the "
                   "field is coerced with @type: @vocab",
}


def _kind(kind):
    """Label the mechanism a row shows, with its definition on hover."""
    return f'<abbr title="{TIPS[kind]}">{kind}</abbr>'


def _alias(term):
    """An alias row's term, marked as belonging to the property above it."""
    return f'<span class="alias">{term}</span>'


def _rows(schema, ctx, syn, origin, prefix="", seen=None, page=None):
    """Term records, recursing into nested objects and array items.

    A record is {"kind", "group", "cells"}. `kind` tells the renderer what it is looking
    at, so grouping and collapsing are decided once, in one place, instead of every caller
    re-deriving it from the cell text.
    """
    seen = seen if seen is not None else set()
    rows = []
    required = set(schema.get("required") or [])
    for name, spec in (schema.get("properties") or {}).items():
        # `{}` constrains nothing, so it is not an override and has nothing to document
        if not isinstance(spec, dict) or not spec:
            continue
        path = f"{prefix}{name}"
        indent = INDENT * prefix.count(".")
        target = _term_target(ctx.get(name))
        desc = " ".join((spec.get("description") or "").split())
        aliases = [v for v in (spec.get("enum") or []) if isinstance(v, str) and v in ctx]
        rows.append({"kind": "property", "group": path, "cells": (
            f"{indent}<code>{name}</code>" + (" *" if name in required else "")
            + (f"<br><small>{desc}</small>" if desc else ""),
            _constraints(spec, enum=len(aliases) != len(spec.get("enum") or [])) or "-",
            _link(target, ctx) if target else "-",
            _alternatives(name, syn, ctx, page),
        )})
        # Enum values that are themselves context terms: `unit` is coerced with
        # `@type: @vocab`, so "SEC" resolves through the context exactly as a term does.
        # They belong under the property that admits them, for the same reason the class
        # belongs under `type`.
        varnames = spec.get("x-enum-varnames") or []
        labels = {v: (varnames[i] if i < len(varnames) else "")
                  for i, v in enumerate(spec.get("enum") or [])}
        for value in aliases:
            label = labels[value]
            rows.append({"kind": "alias", "group": path, "cells": (
                indent + _alias(f'<code>"{value}"</code>')
                + (f"<br><small>{label}</small>" if label else ""),
                _kind("value alias"),
                _link(_term_target(ctx.get(value)), ctx),
                _alternatives(value, syn, ctx, page),
            )})
        nested = spec if spec.get("properties") else (
            spec.get("items") if isinstance(spec.get("items"), dict) else None)
        if nested and nested.get("properties") and path not in seen:
            seen.add(path)
            rows += _rows(nested, ctx, syn, origin, prefix=f"{path}.", seen=seen,
                          page=page)
    return rows


HEADERS = ("Term", "Constraints", "Consensus mapping", "Alternative mappings")
_GROUP_ID = [0]


def _tr(row, cls=""):
    attr = f' class="{cls.strip()}"' if cls.strip() else ""
    return f"<tr{attr}>" + "".join(f"<td>{c}</td>" for c in row["cells"]) + "</tr>"


def _toggle(label, kind, extra=""):
    """A row that shows or hides the rows of its own kind in this tbody.

    Each level of collapse carries its own class, so a section and a value list can nest:
    `:has()` matches the tbody for whichever toggle it names, and a row hidden by the
    section is hidden whether or not its own list is open.
    """
    _GROUP_ID[0] += 1
    gid = f"rows-{_GROUP_ID[0]}"
    classes = f"toggle {kind}-toggle {extra}".strip()
    return (f'<tr class="{classes}"><td colspan="{len(HEADERS)}">'
            f'<input type="checkbox" id="{gid}">'
            f'<label for="{gid}">{label}</label></td></tr>')


def _section(entry, single):
    """One schema's terms as a tbody.

    An inherited section is collapsed: it is context for the schema being documented, and
    a reader who opens a subschema came for what the subschema adds. Its permitted values
    keep their own collapse inside it.
    """
    inherited = entry["inherited"]
    within = "section-row " if inherited else ""
    body = []

    if inherited:
        link = f'<a href="{entry["href"]}">{entry["title"]}</a>' if entry["href"]             else entry["title"]
        body.append(_toggle(f"all of {link}", "section"))
    elif not single:
        body.append(f'<tr class="section"><td colspan="{len(HEADERS)}">'
                    f'<strong>{entry["title"]}</strong></td></tr>')

    rows, i = entry["rows"], 0
    while i < len(rows):
        row = rows[i]
        if row["kind"] == "alias":
            j = i
            while (j < len(rows) and rows[j]["kind"] == "alias"
                   and rows[j]["group"] == row["group"]):
                j += 1
            group = rows[i:j]
            if len(group) > ALIAS_LIMIT:
                body.append(_toggle(f"{len(group)} permitted values", "values",
                                    extra=within))
                body += [_tr(r, within + "values-row") for r in group]
            else:
                body += [_tr(r, within) for r in group]
            i = j
            continue
        body.append(_tr(row, within))
        i += 1
    return "<tbody>" + "".join(body) + "</tbody>"


def _table(sections):
    head = "<thead><tr>" + "".join(f"<th>{h}</th>" for h in HEADERS) + "</tr></thead>"
    single = len(sections) == 1
    return ("<table>" + head
            + "".join(_section(entry, single) for entry in sections) + "</table>")


def _page_source(page):
    """The source path of the page being rendered, from whatever the caller passed.

    zensical exposes the current page as a Jinja global, so a template can hand it over
    instead of repeating its own filename as a string.
    """
    if page is None:
        return None
    src = getattr(getattr(page, "file", None), "src_path", None) or page
    return os.path.join(ROOT, "docs", str(src).replace("\\", "/"))


def oold_schema_terms(module, name, page=None):
    """Render the terms of a schema and everything it extends, with their RDF readings."""
    base_dir = os.path.join(ROOT, "modules", module)
    chain, seen = [], set()

    def walk(fname):
        path = os.path.join(base_dir, fname)
        if fname in seen or not os.path.exists(path):
            return
        seen.add(fname)
        schema = _read(path)
        for ref in schema.get("allOf") or []:
            if isinstance(ref, dict) and isinstance(ref.get("$ref"), str):
                walk(ref["$ref"])
        chain.append((fname, schema))

    walk(f"{name}.schema.json")
    _page_link(module, name, None)  # warms the page index
    page = _page_source(page) or _PAGES.get((module, name))

    ctx = {}
    for _, schema in chain:
        ctx.update(_ctx_of(schema))

    sections = []
    for fname, schema in chain:
        title = schema.get("title") or fname
        syn = schema.get("x-oold-context") or {}
        own = _rows(schema, ctx, syn, title, page=page)
        if title in ctx:
            # The class is the default value of `type`, mapped by a type alias in the
            # context, so it belongs under that property rather than beside it.
            desc = " ".join((schema.get("description") or "").split())
            klass = {"kind": "alias", "group": "type", "cells": (
                _alias(f'<code>"{title}"</code>')
                + (f"<br><small>{desc}</small>" if desc else ""),
                _kind("type alias"),
                _link(_term_target(ctx.get(title)), ctx),
                _alternatives(title, syn, ctx, page))}
            at = next((i for i, r in enumerate(own) if r["group"] == "type"), len(own) - 1)
            own.insert(at + 1, klass)
        sections.append({
            "title": title,
            "href": _page_link(module, fname[: -len(".schema.json")], page),
            "inherited": fname != f"{name}.schema.json",
            "rows": own,
        })

    return _table(sections) + NL + NL + "`*` marks a required property."


SHARED_MACROS = [download, example, inline_file, mapping_crosswalks,
                 mapping_crosswalk_table, oold_schema_meta_data,
                 oold_schema_renderer, oold_schema_terms, render_schema,
                 sssom_table, vocabulary]


def define_env(env):
    """Entry point for zensical's macros extension."""
    for macro in SHARED_MACROS:
        env.macro(macro)
