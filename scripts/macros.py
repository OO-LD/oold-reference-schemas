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
from pathlib import Path

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
    documentation shows that instead of the repository-local path, for the same tree the
    rest of the page links: `dev` while reading the development snapshot, the frozen
    version while reading a release.
    """
    doc = json.loads(text)
    channel = module_version(module) if _channel() == "release" else "dev"
    base = f"{IRI_BASE}/{module}/{channel}/"

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
    diagrams = []
    if os.path.isdir(rdf_dir):
        for fname in sorted(os.listdir(rdf_dir)):
            if not fname.startswith(f"{name}.") or not fname.endswith(".mmd"):
                continue
            with open(os.path.join(rdf_dir, fname), encoding="utf-8") as fh:
                diagrams.append((fname[len(name) + 1:-4], fh.read().rstrip(NL)))
    # the triples first, the picture of them second
    if readings:
        panels.append(("RDF", _rdf_panel(readings)))
    if diagrams:
        panels.append(("Graph", _graph_panel(diagrams)))

    return _tab_group(panels)


def _graph_panel(diagrams):
    """The Graph tab: the same reading as a diagram, one mapping set at a time.

    Turtle answers which triples there are, and a diagram answers what shape they make,
    which is the question a reader has when comparing two communities. Same dropdown as the
    RDF tab, so the two tabs stay in step.
    """
    _GROUP_ID[0] += 1
    group = f"graph-{_GROUP_ID[0]}"
    diagrams = sorted(diagrams, key=lambda d: d[0] != "consensus")
    options = "".join(f'<option value="{label}">{label}</option>' for label, _ in diagrams)
    select = (f'<div class="mapping-select"><label for="{group}">Mapping set</label>'
              f'<select id="{group}" data-mapping-select="{group}">{options}</select></div>')
    blocks = [f'<div class="mapping-set" data-group="{group}" data-set="{label}" markdown>'
              f'{NL}{NL}```mermaid{NL}{text}{NL}```{NL}{NL}</div>'
              for label, text in diagrams]
    return select + NL + NL + (NL + NL).join(blocks)


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


def _module_versions(module, page):
    """Where else this page exists, one entry per version of its module.

    A documentation snapshot documents one state of a module, so switching module version
    means switching snapshot: `dev` for the tip of main, and the dated release that
    documented each published version. The release index holds that mapping.
    """
    if not page:
        return []
    url = _url(page)
    entries = []
    path = os.path.join(GENERATED, "versions.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for entry in json.load(fh).get(module) or []:
                short = ".".join(entry["module"].split(".")[:2])
                entries.append((short, f"/{entry['docs']}/{url}/"))
    entries.append(("dev", f"/dev/{url}/"))
    current = "dev" if _channel() == "dev" else module_version(module)
    return [(label, href, label == current) for label, href in entries]


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

    channel = version if _channel() == "release" else "dev"
    lines = [f"- module: [`{module}`](/{module}/{channel}/) "
             f"{module_version(module, full=True)}"]
    versions = _module_versions(module, page)
    if len(versions) > 1:
        lines.append("- module version: " + " &middot; ".join(
            f"**{label}**" if current else f"[{label}]({href})"
            for label, href, current in versions))
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
    path = f"/{module}/{channel}/{name}.schema.json"
    lines.append(f"- schema file: [`{path}`]({path})")
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


def _refs(spec):
    """Every schema a subschema references, its own first, then the ones it composes."""
    if not isinstance(spec, dict):
        return []
    targets = [spec.get("$ref")] + [m.get("$ref") for m in (spec.get("allOf") or [])
                                    if isinstance(m, dict)]
    return [t for t in targets if isinstance(t, str)]


def _schema_file(document, origin):
    """The file a reference names: a sibling, or a module of this repository."""
    if document.startswith("https://w3id.org/oo-ld/schemas/"):
        parts = document[len("https://w3id.org/oo-ld/schemas/"):].split("/")
        if len(parts) == 3:
            candidate = Path(ROOT) / "modules" / parts[0] / parts[2]
            return candidate if candidate.is_file() else None
        return None
    candidate = Path(origin).parent / document
    return candidate if candidate.is_file() else None


def _rows(schema, ctx, syn, origin, prefix="", page=None):
    """Term records for one schema, and the embedded objects reached from it.

    Returns (rows, embeds). An embedded object is not flattened into this table: it is a
    schema in its own right, so it becomes its own section, the way an inherited schema
    does. A record is {"kind", "group", "cells"}: `kind` tells the renderer what it is
    looking at, so grouping and collapsing are decided in one place.
    """
    rows, embeds = [], []
    required = set(schema.get("required") or [])
    for name, spec in (schema.get("properties") or {}).items():
        # `{}` constrains nothing, so it is not an override and has nothing to document
        if not isinstance(spec, dict) or not spec:
            continue
        path = f"{prefix}{name}"
        target = _term_target(ctx.get(name))
        desc = " ".join((spec.get("description") or "").split())
        aliases = [v for v in (spec.get("enum") or []) if isinstance(v, str) and v in ctx]
        rows.append({"kind": "property", "group": path, "required": name in required,
                     "cells": (
            f"<code>{name}</code>" + (" *" if name in required else "")
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
                _alias(f'<code>"{value}"</code>')
                + (f"<br><small>{label}</small>" if label else ""),
                _kind("value alias"),
                _link(_term_target(ctx.get(value)), ctx),
                _alternatives(value, syn, ctx, page),
            )})
        inner, via = spec, "$ref"
        layers = _layers(spec, origin, name)
        if not layers:
            items = spec.get("items") if isinstance(spec.get("items"), dict) else None
            inner, via = (items, "items") if items else (spec, "$ref")
            layers = _layers(inner, origin, name) if items else []
        if layers:
            embeds.append({"path": path, "layers": layers, "via": via,
                           "title": layers[-1]["title"]})
    return rows, embeds


def _layers(spec, origin, name):
    """What an embedded object is made of, base first, the object's own part last.

    A composed schema is not one flat object: `allOf` states which schema it builds on, and
    that is exactly what a reader needs when the same base carries several compositions. The
    layers are kept apart here so the table can show them the way a schema page does.
    """
    if not isinstance(spec, dict):
        return []
    layers = []
    for target in _refs(spec):
        document, _, pointer = target.partition("#")
        root = _schema_file(document, origin) if document else origin
        if root is None:
            continue
        data = _read(root)
        for step in [s for s in pointer.split("/") if s]:
            data = (data or {}).get(step.replace("~1", "/").replace("~0", "~"))
            if data is None:
                break
        if isinstance(data, dict):
            # the referenced document contributes its own layer through the recursion, so
            # appending it here as well would state it twice
            layers += _layers(data, root, pointer.rsplit("/", 1)[-1] or name)
    own = {k: v for k, v in spec.items() if k not in ("$ref", "allOf")}
    if own.get("properties"):
        layers.append({"schema": own, "source": origin,
                       "title": spec.get("title") or (layers[-1]["title"] if layers
                                                      else name)})
    return layers


HEADERS = ("Term", "Constraints", "Consensus mapping", "Alternative mappings")
MAX_LEVEL = 6
_GROUP_ID = [0]


def _gid() -> str:
    _GROUP_ID[0] += 1
    return f"rows-{_GROUP_ID[0]}"


def _level(level: int) -> str:
    """How deep a row sits, capped where further indent would cost more than it says."""
    return f"level-{min(level, MAX_LEVEL)}"


def _tr(row, classes=()):
    cls = " ".join(c for c in classes if c)
    attr = f' class="{cls}"' if cls else ""
    return f"<tr{attr}>" + "".join(f"<td>{c}</td>" for c in row["cells"]) + "</tr>"


def _toggle(label, kind, gid, classes=()):
    """A row that shows or hides every row naming its group.

    Membership is carried by the rows, not by their position, so a section that contains
    another section hides it too: a nested toggle names its own group and every group it
    sits inside, and closing any of them takes it away.
    """
    cls = " ".join(("toggle", f"{kind}-toggle", *[c for c in classes if c]))
    return (f'<tr class="{cls}"><td colspan="{len(HEADERS)}">'
            f'<input type="checkbox" id="{gid}">'
            f'<label for="{gid}">{label}</label></td></tr>')


def _collapse_style(gids):
    """The rule per collapsible group, since a class alone cannot name its checkbox.

    `:has()` looks up from the table, so the rule works wherever the checkbox sits, which
    a sibling combinator cannot do across rows.
    """
    rules = "".join(f".md-typeset:has(#{gid}:not(:checked)) .by-{gid}{{display:none}}"
                    for gid in gids)
    return f"<style>{rules}</style>" if rules else ""


def _runs(rows):
    """The rows grouped by the term they belong to, so a run can be handled as one."""
    out, i = [], 0
    while i < len(rows):
        j = i + 1
        while (j < len(rows) and rows[j]["kind"] == "alias"
               and rows[j]["group"] == rows[i]["group"]):
            j += 1
        out.append(rows[i:j])
        i = j
    return out


def _link_to(entry):
    return (f'<a href="{entry["href"]}">{entry["title"]}</a>' if entry["href"]
            else entry["title"])


def _opening_row(row, gid, child, classes):
    """The term row itself opens the object it reaches.

    A term that refers to a schema is not a term plus a heading: it is one thing, and the
    reference is a constraint on it, so the row states which schema and opens it in place.
    """
    cells = list(row["cells"])
    cells[0] = (f'<input type="checkbox" id="{gid}">'
                f'<label for="{gid}">{cells[0]}</label>')
    reference = f'<code>{child["via"]}</code> {_link_to(child)}'
    cells[1] = reference if cells[1] in ("", "-") else f'{cells[1]}, {reference}'
    return _tr({**row, "cells": tuple(cells)}, ["toggle", "term-toggle", *classes])


def _section(entry, level, hidden, state, single=False, opened=False):
    """One schema's terms, and under each term the object it reaches.

    An embedded object is a schema of its own, so its terms are not flattened into this
    table, but they belong where the term that reaches them stands: a reader following
    `amount` finds what an amount is at that point, not at the end of the table.
    """
    gids, done, by_path, owners = state
    body = []

    if opened:
        # the term row above already carries the toggle, so the section starts at its rows
        level += 1
    elif entry["inherited"] and not entry["rows"]:
        # every term of this layer is refined further out, so there is nothing to open: the
        # lineage is still worth stating, as a line rather than as an empty section
        return (f'<tr class="section-note {_level(level)} {" ".join(hidden)}">'
                f'<td colspan="{len(HEADERS)}">all of {_link_to(entry)}</td></tr>')
    elif entry["inherited"]:
        gid = _gid()
        gids.append(gid)
        embedded = entry.get("embedded")
        # a layer an object builds on reads as what it is, `all of`, and only an object no
        # term opened has to name the term it belongs to
        label = (f'<code>{embedded}</code> is {_link_to(entry)}'
                 if embedded and entry.get("own") else f"all of {_link_to(entry)}")
        kind = ["embedded"] if embedded else []
        body.append(_toggle(label, "section", gid, [*kind, _level(level), *hidden]))
        hidden = [*hidden, f"by-{gid}"]
        level += 1
    elif not single:
        body.append(f'<tr class="section"><td colspan="{len(HEADERS)}">'
                    f'<strong>{entry["title"]}</strong></td></tr>')

    within = [_level(level), *hidden]
    for run in _runs(entry["rows"]):
        group = by_path.get(run[0]["group"])
        if (group and run[0]["kind"] == "property" and id(group[0]) not in done
                and owners.get(run[0]["group"]) is entry):
            done.update(id(s) for s in group)
            gid = _gid()
            gids.append(gid)
            body.append(_opening_row(run[0], gid, group[-1], within))
            body += [_tr(r, within) for r in run[1:]]
            inside = [*hidden, f"by-{gid}"]
            # what the object builds on first, the way a schema page reads, then its own
            for base in group[:-1]:
                body.append(_section(base, level + 1, inside, state))
            body.append(_section(group[-1], level, inside, state, opened=True))
            continue
        if run[0]["kind"] == "alias" and len(run) > ALIAS_LIMIT:
            values = _gid()
            gids.append(values)
            body.append(_toggle(f"{len(run)} permitted values", "values", values, within))
            body += [_tr(r, [_level(level + 1), *hidden, f"by-{values}"]) for r in run]
        else:
            body += [_tr(r, within) for r in run]
    return "".join(body)


def _table(sections):
    by_path = {}
    for entry in sections:
        if entry.get("embedded"):
            by_path.setdefault(entry["embedded"], []).append(entry)
    # the term row that opens an object is the last one to state it: a schema that narrows
    # an inherited term is where the reader looks for what it now holds
    owners = {}
    for entry in sections:
        for row in entry["rows"]:
            if row["kind"] == "property" and row["group"] in by_path:
                owners[row["group"]] = entry
    state = ([], set(), by_path, owners)
    chain = [e for e in sections if not e.get("embedded")]
    body = "".join(_section(e, 0, [], state, single=len(chain) == 1) for e in chain)
    # an object no term reached keeps a section of its own rather than disappearing
    body += "".join(_section(e, 0, [], state) for e in sections
                    if e.get("embedded") and id(e) not in state[1])
    head = "<thead><tr>" + "".join(f"<th>{h}</th>" for h in HEADERS) + "</tr></thead>"
    return (_collapse_style(state[0]) + "<table>" + head
            + "<tbody>" + body + "</tbody></table>")


def _page_source(page):
    """The source path of the page being rendered, from whatever the caller passed.

    zensical exposes the current page as a Jinja global, so a template can hand it over
    instead of repeating its own filename as a string.
    """
    if page is None:
        return None
    src = getattr(getattr(page, "file", None), "src_path", None) or page
    return os.path.join(ROOT, "docs", str(src).replace("\\", "/"))


def _chain_of(path):
    """A schema and everything it extends, the schema itself last.

    Following `allOf` through the file that declares it, so a schema in another module is
    reached the same way as one next door: what a term means is decided by the document it
    comes from, not by the page it is shown on.
    """
    chain, seen = [], set()

    def walk(schema_path):
        schema_path = os.path.normpath(schema_path)
        if schema_path in seen or not os.path.exists(schema_path):
            return
        seen.add(schema_path)
        schema = _read(schema_path)
        for ref in schema.get("allOf") or []:
            if isinstance(ref, dict) and isinstance(ref.get("$ref"), str):
                target = _schema_file(ref["$ref"].partition("#")[0], schema_path)
                if target:
                    walk(target)
        chain.append((schema_path, schema))

    walk(path)
    return chain


def _readings(chain, base_ctx=None, base_syn=None):
    """The context and the synonyms a chain of schemas puts together."""
    ctx = dict(base_ctx or {})
    syn = dict(base_syn or {})
    for _, schema in chain:
        ctx.update(_ctx_of(schema))
        syn.update(schema.get("x-oold-context") or {})
    return ctx, syn


def oold_module_page(module, page=None):
    """A module's whole page: what it is, where it is published, and what it holds.

    A module has nothing to say that its own files do not already state, so the page is
    generated in full and a seeded one carries only this call. Prose written underneath it
    survives, which is where a module explains a decision rather than a fact.
    """
    base_dir = Path(ROOT) / "modules" / module
    if not base_dir.is_dir():
        return ""
    meta = _read(base_dir / "module.json") if (base_dir / "module.json").is_file() else {}
    parts = [f'# {meta.get("title", module)}']
    if meta.get("scope"):
        parts.append(" ".join(str(meta["scope"]).split()))
    parts.append(oold_module_meta_data(module, page))
    schemas = oold_module_schemas(module, page)
    if schemas:
        parts += ["## Schemas", schemas]
    return (NL + NL).join(parts)


def oold_module_meta_data(module, page=None):
    """What a module is and where it is published, as a bullet list.

    Read from module.json and the schemas themselves rather than repeated in prose, so a
    module page cannot claim a version, a status or a schema count the module does not have.
    """
    base_dir = Path(ROOT) / "modules" / module
    if not base_dir.is_dir():
        return ""
    meta = _read(base_dir / "module.json") if (base_dir / "module.json").is_file() else {}
    schemas = sorted(base_dir.glob("*.schema.json"))
    instances = sorted(base_dir.glob("*.instance.json"))
    channel = module_version(module) if _channel() == "release" else "dev"

    lines = [f"- version: `{module_version(module, full=True)}`, "
             f"published at [`/{module}/{channel}/`](/{module}/{channel}/)"]
    if meta.get("status"):
        lines.append(f'- status: {meta["status"]}')
    lines.append(f"- schemas: {len(schemas)}, with {len(instances)} committed "
                 f"instance{'' if len(instances) == 1 else 's'}")
    versions = _module_versions(module, _page_source(page))
    if len(versions) > 1:
        lines.append("- module version: " + " &middot; ".join(
            f"**{label}**" if current else f"[{label}]({href})"
            for label, href, current in versions))
    # the readings the module actually publishes, which is more than it declares: a schema
    # that embeds another inherits that one's mappings too
    sets = sorted({f.name.split(".")[-2] for f in Path(GENERATED, module).glob("*.ttl")}
                  - {"consensus"}) if Path(GENERATED, module).is_dir() else []
    if sets:
        lines.append("- mapping sets: " + ", ".join(
            f"[{name}]({_set_link(name, _page_source(page))})" for name in sets))
    return NL.join(lines)


def oold_module_schemas(module, page=None):
    """The schemas of a module, nested by what each one extends.

    Generated rather than written, because a module page that lists its schemas by hand goes
    stale the moment one is added, and the inheritance is the order a reader needs: a
    subschema inherits the terms and the mappings of the schema above it.
    """
    base_dir = os.path.join(ROOT, "modules", module)
    if not os.path.isdir(base_dir):
        return ""
    page = _page_source(page)
    parents, titles, leads = {}, {}, {}
    for path in sorted(Path(base_dir).glob("*.schema.json")):
        name = path.name[: -len(".schema.json")]
        schema = _read(path)
        titles[name] = schema.get("title") or name
        leads[name] = " ".join((schema.get("description") or "").split()).split(". ")[0]
        parents[name] = _parents(module, name)

    def branch(name, depth):
        indent = "    " * depth
        href = _page_link(module, name, page)
        lead = f", {leads[name]}" if leads[name] else ""
        lines = [f'{indent}- [{titles[name]}]({href}){lead.rstrip(".")}']
        for child in sorted(n for n, ps in parents.items() if ps and ps[-1] == name):
            lines += branch(child, depth + 1)
        return lines

    roots = sorted(n for n, ps in parents.items() if not ps)
    return NL.join(line for root in roots for line in branch(root, 0))


def oold_schema_terms(module, name, page=None):
    """Render the terms of a schema and everything it extends, with their RDF readings."""
    base_dir = os.path.join(ROOT, "modules", module)
    chain = _chain_of(os.path.join(base_dir, f"{name}.schema.json"))

    _page_link(module, name, None)  # warms the page index
    page = _page_source(page) or _PAGES.get((module, name))

    ctx, _ = _readings(chain)

    sections, embedded = [], {}
    for path, schema in chain:
        fname = os.path.basename(path)
        title = schema.get("title") or fname
        syn = schema.get("x-oold-context") or {}
        own, embeds = _rows(schema, ctx, syn, path, page=page)
        # a schema that narrows an inherited object states the same term again, and its
        # version is the one to expand: it carries the base as a layer of its own
        for embed in embeds:
            embedded[embed["path"]] = dict(embed, ctx=ctx, syn=syn)
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

    # An embedded object is a schema of its own, so it gets its own section rather than
    # more indentation: collapsed like an inherited one, titled by the property that
    # reaches it, and linked to its page where it has one.
    # depth first, so a nested object follows the object that reaches it instead of the
    # next object at its own level
    done, queue = set(), list(embedded.values())
    while queue:
        entry = queue.pop(0)
        if entry["path"] in done:
            continue
        done.add(entry["path"])
        # What a term means is stated by the document it comes from, so each layer adds its
        # own context on top of the section that reaches it: an object assembled from a
        # shared base plus properties of its own is only fully described by both.
        child_ctx, child_syn = entry["ctx"], entry["syn"]
        for index, layer in enumerate(entry["layers"]):
            source = layer["source"]
            child_ctx, child_syn = _readings([(source, _read(source))],
                                             child_ctx, child_syn)
            rows, deeper = _rows(layer["schema"], child_ctx, child_syn, source,
                                 prefix=f'{entry["path"]}.', page=page)
            queue[:0] = [dict(e, ctx=child_ctx, syn=child_syn) for e in deeper]
            sections.append({
                "title": layer["title"],
                "href": _embedded_href(source, module, page),
                "inherited": True,
                "embedded": entry["path"],
                "via": entry["via"],
                "own": index == len(entry["layers"]) - 1,
                "rows": rows,
            })

    return _table(sections) + NL + NL + "`*` marks a required property."


def _embedded_href(source, module, page):
    """The page of the schema an embedded object comes from, when it has one.

    An object defined inline has no page of its own, and one reached across modules has
    its page in that module, so the link is computed from where the schema actually is
    rather than from where the reference was written.
    """
    path = Path(source)
    if not path.name.endswith(".schema.json"):
        return ""
    return _page_link(path.parent.name, path.name[: -len(".schema.json")], page)


SHARED_MACROS = [download, example, inline_file, mapping_crosswalks,
                 oold_module_meta_data, oold_module_page,
                 oold_module_schemas,
                 mapping_crosswalk_table, oold_schema_meta_data,
                 oold_schema_renderer, oold_schema_terms, render_schema,
                 sssom_table, vocabulary]


def define_env(env):
    """Entry point for zensical's macros extension."""
    for macro in SHARED_MACROS:
        env.macro(macro)
