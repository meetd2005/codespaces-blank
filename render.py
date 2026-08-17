#!/usr/bin/env python3
"""
Render a report from report.yml into HTML and PDF using the exported
Altered Security SysReptor design, without needing a SysReptor instance.

SysReptor renders a design's Vue template against the report data and prints
the result with WeasyPrint. This script does the same job: it builds the same
document structure the design's template describes, then hands it to WeasyPrint
with the design's own stylesheet. The output is the design as intended, produced
from a plain YAML file.

Usage:
    python3 render.py                    # -> out/report.html and out/report.pdf
    python3 render.py --data report.yml --out out
    python3 render.py --html-only        # skip the PDF (fast preview loop)
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pyyaml.  Run:  pip install -r requirements.txt")

try:
    import markdown as md_lib
except ImportError:
    sys.exit("Missing dependency: markdown.  Run:  pip install -r requirements.txt")


ROOT = Path(__file__).resolve().parent
DESIGN = ROOT / "design"

# Stylesheets, in cascade order. base.css reconstructs the SysReptor global
# stylesheet the design imports, styles.css is the untouched design export,
# renderer.css carries our deliberate deviations.
STYLESHEETS = ["base.css", "styles.css", "renderer.css"]


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "attr_list",
    "def_list",
    "sane_lists",
    "footnotes",
    "md_in_html",
    "pymdownx.tilde",
    "pymdownx.caret",
]

MD_EXTENSION_CONFIGS = {
    "footnotes": {"BACKLINK_TEXT": ""},
}

# SysReptor's markdown dialect supports markdown-it inline footnotes,
# `^[note text]`. Python-Markdown only knows the reference form, so inline
# footnotes are rewritten into `[^fn-N]` definitions before parsing.
INLINE_FOOTNOTE_RE = re.compile(r"\^\[((?:[^\[\]]|\[[^\]]*\])*)\]")

# `{#id .class}` attribute lists: the design template writes `.in-toc.numbered`
# (markdown-it style, no separator) where Python-Markdown wants them separated.
ATTR_LIST_RE = re.compile(r"\{([^{}\n]*)\}\s*$", re.MULTILINE)


def _normalise_attr_lists(text: str) -> str:
    """Turn `{#objective .in-toc.numbered}` into `{#objective .in-toc .numbered}`."""

    def fix(match: re.Match) -> str:
        body = match.group(1)
        # Only touch attribute-list-looking bodies (start with # or .).
        if not body.lstrip().startswith(("#", ".")):
            return match.group(0)
        return "{" + re.sub(r"(?<=[^\s.])\.(?=[A-Za-z_-])", " .", body) + "}"

    return ATTR_LIST_RE.sub(fix, text)


def _extract_inline_footnotes(text: str, counter: list) -> str:
    """Rewrite `^[note]` into a reference plus a definition appended at the end."""
    definitions = []

    def repl(match: re.Match) -> str:
        counter[0] += 1
        name = f"fn-{counter[0]}"
        definitions.append(f"[^{name}]: {match.group(1).strip()}")
        return f"[^{name}]"

    body = INLINE_FOOTNOTE_RE.sub(repl, text)
    if definitions:
        body = body + "\n\n" + "\n\n".join(definitions) + "\n"
    return body


class Renderer:
    def __init__(self, data: dict, base_dir: Path):
        self.data = data
        self.base_dir = base_dir
        self.footnote_counter = [0]
        self.figure_counter = 0
        self.figures: list[tuple[str, str]] = []  # (element id, caption)
        self._md = md_lib.Markdown(
            extensions=MD_EXTENSIONS,
            extension_configs=MD_EXTENSION_CONFIGS,
            output_format="html",
        )

    # -- markdown ----------------------------------------------------------

    def md(self, text) -> str:
        """Render a markdown field to HTML, with SysReptor-flavoured extras."""
        if text is None:
            return ""
        text = str(text)
        if not text.strip():
            return ""

        text = _extract_inline_footnotes(text, self.footnote_counter)
        text = _normalise_attr_lists(text)

        self._md.reset()
        out = self._md.convert(text)

        out = self._rewrite_asset_paths(out)
        out = self._wrap_figures(out)
        return out

    # -- assets ------------------------------------------------------------

    def _rewrite_asset_paths(self, out: str) -> str:
        """Map SysReptor's virtual asset paths onto files in this repository.

        SysReptor serves design assets from `/assets/name/...` and report images
        from `/images/name/...`. Here they live in design/assets/ and images/.
        """

        def fix(match: re.Match) -> str:
            quote, path = match.group(1), match.group(2)
            if path.startswith("/assets/name/"):
                path = "design/assets/" + path[len("/assets/name/"):]
            elif path.startswith("/assets/"):
                path = "design/assets/" + path[len("/assets/"):]
            elif path.startswith("/images/name/"):
                path = "images/" + path[len("/images/name/"):]
            elif path.startswith("/images/"):
                path = "images/" + path[len("/images/"):]
            return f'src={quote}{path}{quote}'

        return re.sub(r'src=(["\'])([^"\']+)\1', fix, out)

    # -- figures -----------------------------------------------------------

    # A paragraph holding nothing but one image becomes a numbered figure,
    # matching how SysReptor promotes standalone images.
    FIGURE_RE = re.compile(
        r"<p>\s*(<img\b[^>]*/?>)\s*</p>", re.IGNORECASE
    )
    ALT_RE = re.compile(r'\balt=(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)
    CLASS_RE = re.compile(r'\bclass=(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)

    def _wrap_figures(self, out: str) -> str:
        def wrap(match: re.Match) -> str:
            img = match.group(1)
            alt_match = self.ALT_RE.search(img)
            caption = (alt_match.group(2).strip() if alt_match else "")

            # An image tagged `{.evidence}` (or any class) passes the class up to
            # the figure, where renderer.css can act on it.
            class_match = self.CLASS_RE.search(img)
            classes = class_match.group(2).strip() if class_match else ""
            figure_class = f' class="{html.escape(classes, quote=True)}"' if classes else ""

            if not caption:
                # Uncaptioned images (the methodology diagram) stay out of the
                # figure numbering and the List of Figures.
                return f"<figure{figure_class}>{img}</figure>"

            self.figure_counter += 1
            fig_id = f"figure-{self.figure_counter}"
            self.figures.append((fig_id, caption))
            return (
                f'<figure id="{fig_id}"{figure_class}>{img}'
                f"<figcaption>{html.escape(caption)}</figcaption></figure>"
            )

        return self.FIGURE_RE.sub(wrap, out)


# ---------------------------------------------------------------------------
# Table of contents
# ---------------------------------------------------------------------------

class TocCollector(HTMLParser):
    """Collect `<h1>`-`<h6>` elements carrying the `in-toc` class, in order."""

    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self._current: dict | None = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if self._current is not None:
            self._depth += 1
            return
        if tag in self.HEADINGS and "in-toc" in (attrs_d.get("class") or "").split():
            self._current = {
                "level": int(tag[1]),
                "id": attrs_d.get("id", ""),
                "parts": [],
            }
            self._depth = 0

    def handle_endtag(self, tag):
        if self._current is None:
            return
        if self._depth > 0:
            self._depth -= 1
            return
        if tag in self.HEADINGS:
            title = re.sub(r"\s+", " ", "".join(self._current["parts"])).strip()
            if self._current["id"]:
                self.items.append(
                    {
                        "level": self._current["level"],
                        "id": self._current["id"],
                        "title": title,
                    }
                )
            self._current = None

    def handle_data(self, data):
        if self._current is not None:
            self._current["parts"].append(data)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or fallback


def format_date(value, style: str = "medium") -> str:
    """Format a date the way the design's `formatDate(..., 'medium')` does."""
    if value in (None, ""):
        return ""
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            value = dt.date.fromisoformat(value.strip())
        except ValueError:
            return value  # pass through whatever the author wrote
    if not isinstance(value, dt.date):
        return str(value)
    return f"{value.strftime('%b')} {value.day}, {value.year}"


ROLE_LABELS = {
    "lead": "Lead Pentester",
    "pentester": "Red Team Operator",
    "reviewer": "Reviewer",
}


def build_document(data: dict, base_dir: Path) -> str:
    report = data.get("report") or {}
    pentesters = data.get("pentesters") or []
    findings = data.get("findings") or []

    r = Renderer(data, base_dir)
    out: list[str] = []
    w = out.append

    # Give every finding a stable anchor id.
    for index, finding in enumerate(findings, start=1):
        if not finding.get("id"):
            finding["id"] = slugify(finding.get("title", ""), f"finding-{index}")

    title = report.get("title", "")
    version = report.get("report_version", "")
    report_date = format_date(report.get("report_date"))

    # ---- running header / footer -----------------------------------------
    w('<div id="header">')
    w('  <div id="header-left">')
    w(f"    <strong>Red Team Assessment Report</strong><br>")
    w(f"    {esc(title)}" + (f" <span>- v{esc(version)}</span>" if version else "") + "<br>")
    if report_date:
        w(f"    <span>{esc(report_date)}</span>")
    w("  </div>")
    w('  <div id="header-right">')
    w('    <img src="design/assets/AlteredSecurity-2048x594--1-.png" alt="Altered Security" />')
    w("  </div>")
    w("</div>")

    w('<div id="footer">')
    w('  <div id="footer-brand">')
    w('    <img src="design/assets/AlteredSecurity-2048x594--1-.png" alt="Altered Security" />'
      '<span class="footer-tagline">OFFENSIVE SECURITY</span>')
    w("  </div>")
    w('  <div id="footer-left"><em>CONFIDENTIAL</em></div>')
    w(f'  <div id="footer-center">{esc(title)}</div>')
    w("</div>")

    if report.get("draft"):
        w('<div id="watermark">DRAFT</div>')

    # ---- cover ------------------------------------------------------------
    w('<section id="page-cover">')
    w('  <div class="cover-photo"><img src="design/assets/thomas-wiese-spartan-fusion.png" alt="" /></div>')
    w('  <svg class="cover-shape" viewBox="0 0 210 297" preserveAspectRatio="none" '
      'xmlns="http://www.w3.org/2000/svg">')
    w('    <polygon points="0,0 210,0 210,122 0,160" fill="#0C0054" fill-opacity="0.97" />')
    w('    <polygon points="0,160 210,122 210,126 0,164" fill="#D2003C" />')
    w("  </svg>")
    w('  <div class="cover-panel">')
    w('    <div class="cover-brand">')
    w('      <img class="cover-logo" src="design/assets/AlteredSecurity-2048x594--1-.png" '
      'alt="Altered Security" /><span class="cover-divider"></span>'
      '<span class="cover-tagline">OFFENSIVE SECURITY</span>')
    w("    </div>")
    w('    <div class="cover-title">')
    w("      <h1>RED TEAM ASSESSMENT REPORT</h1>")
    w(f'      <h2 class="cover-subtitle">{esc(title)}</h2>')
    w("    </div>")
    w('    <div class="cover-meta">')
    w('      <p class="cover-dateline">')
    if report_date:
        w(f"        <span>{esc(report_date)}</span><br>")
    if version:
        w(f"        <span>VERSION {esc(version)}</span>")
    w("      </p>")
    w(f'      <p class="cover-customer"><strong>{esc(report.get("customer_name", ""))}</strong></p>')
    w("    </div>")
    w('    <div class="cover-contact">')
    w('      <p class="cover-contact-label">CONTACT</p>')
    for person in pentesters:
        w('      <p class="cover-contact-person">')
        w(f'        <strong>{esc(person.get("name", ""))}</strong><br>')
        if person.get("mobile"):
            w(f'        <span>{esc(person["mobile"])}<br></span>')
        if person.get("email"):
            w(f'        <span>{esc(person["email"])}</span>')
        w("      </p>")
    w("    </div>")
    w("  </div>")
    w("</section>")
    w("<pagebreak />")

    # The TOC and List of Figures are inserted here once the body is known.
    w("@@TOC@@")
    w("@@LOF@@")

    # ---- document control -------------------------------------------------
    w("<section>")
    w('  <h1 id="document-control" class="in-toc numbered">Document Control</h1>')
    w("  <div>")
    w('    <h2 id="team" class="in-toc numbered">Team</h2>')
    w('    <table class="tbl-plain">')
    w("      <tr><th>Contact</th><th>Details</th><th>Role</th></tr>")
    for person in pentesters:
        details = []
        if person.get("mobile"):
            details.append(f'Mobile: {esc(person["mobile"])}')
        if person.get("email"):
            details.append(f'E-Mail: {esc(person["email"])}')
        roles = ", ".join(
            ROLE_LABELS.get(role, str(role).capitalize()) for role in (person.get("roles") or [])
        )
        w(f'      <tr><td>{esc(person.get("name", ""))}</td>'
          f'<td>{"<br>".join(details)}</td><td>{esc(roles)}</td></tr>')
    w("    </table>")
    w("  </div>")
    w("  <div>")
    w('    <h2 id="list-of-changes" class="in-toc numbered">List of Changes</h2>')
    w('    <table class="tbl-plain">')
    w("      <tr><th>Version</th><th>Description</th><th>Date</th></tr>")
    for change in report.get("list_of_changes") or []:
        w(f'      <tr><td>{esc(change.get("version", ""))}</td>'
          f'<td>{esc(change.get("description", ""))}</td>'
          f'<td>{esc(format_date(change.get("date")))}</td></tr>')
    w("    </table>")
    w("  </div>")
    w("</section>")
    w("<pagebreak />")

    # ---- executive summary -------------------------------------------------
    w("<section>")
    w('  <h1 id="executive-summary" class="in-toc numbered">Executive Summary</h1>')
    w("  <div>")
    w('    <h2 id="executive-summary-overview" class="in-toc numbered">Summary</h2>')
    w(r.md(report.get("executive_summary")))
    w("  </div>")

    w("  <div>")
    w('    <h2 id="finding-summary" class="in-toc numbered">Identified Misconfigurations</h2>')
    w('    <table class="tbl-summary">')
    w("      <thead><tr><th>Name</th><th>Affected Components</th>"
      '<th class="col-page">Page</th></tr></thead>')
    w("      <tbody>")
    for finding in findings:
        fid = finding["id"]
        w(f'        <tr class="table-row-link-recommendation">'
          f'<td><a class="ref" href="#{esc(fid)}">{esc(finding.get("title", ""))}</a></td>'
          f'<td><a class="ref" href="#{esc(fid)}">{esc(finding.get("hostname", ""))}</a></td>'
          f'<td class="col-page"><a class="ref ref-page" href="#{esc(fid)}"></a></td></tr>')
    w("      </tbody>")
    w("    </table>")
    w("  </div>")
    w("</section>")
    w("<pagebreak />")

    # ---- methodology -------------------------------------------------------
    w("<section>")
    w('  <h1 id="methodology" class="in-toc numbered">Methodology</h1>')
    w(r.md(report.get("methodology")))

    objective = report.get("objective")
    if objective:
        w('  <h2 id="objective" class="in-toc numbered">Objective</h2>')
        w(r.md(objective))

    w("  <pagebreak />")
    w("  <div>")
    w('    <h2 id="scope" class="in-toc numbered">Scope</h2>')
    start = format_date(report.get("start_date"))
    if start:
        w(f"    <p>As of <strong>{esc(start)}</strong>, the scope is defined as below:</p>")
    w(r.md(report.get("scope")))
    w("  </div>")

    if report.get("provided_user_machine"):
        w("  <div>")
        w('    <h2 id="provided-users" class="in-toc numbered">'
          "Provided User Account and Machine</h2>")
        w(r.md(report.get("provided_user_machine")))
        w("  </div>")
    w("</section>")
    w("<pagebreak />")

    # ---- compromission path ------------------------------------------------
    w("<section>")
    w('  <h1 id="findings" class="in-toc numbered">Compromission Path</h1>')
    for finding in findings:
        fid = finding["id"]
        w('  <div class="finding">')
        w('    <table class="finding-header">')
        w(f'      <tr><th colspan="2">'
          f'<h2 id="{esc(fid)}" class="in-toc numbered text-center">'
          f'{esc(finding.get("title", ""))}</h2></th></tr>')
        w(f'      <tr><td class="table-key">Hostname</td>'
          f'<td>{esc(finding.get("hostname", ""))}</td></tr>')
        w(f'      <tr><td class="table-key">FQDN</td>'
          f'<td>{esc(finding.get("fqdn", ""))}</td></tr>')
        w(f'      <tr><td class="table-key">OS Details</td>'
          f'<td>{r.md(finding.get("os_details"))}</td></tr>')
        if finding.get("ip_address"):
            w(f'      <tr><td class="table-key">IP Address</td>'
              f'<td>{esc(finding.get("ip_address"))}</td></tr>')
        w("    </table>")

        w("    <h3>Description</h3>")
        w(r.md(finding.get("description")))
        w("    <h3>Compromission Steps</h3>")
        w(r.md(finding.get("compromission_steps")))
        w("    <h3>Recommendations</h3>")
        w(r.md(finding.get("recommendation")))

        w("    <h3>References</h3>")
        w('    <div class="finding-references">')
        references = finding.get("references") or []
        if not references:
            w("      <span>-</span>")
        elif len(references) == 1:
            ref = references[0]
            w(f'      <span><a href="{esc(ref)}" target="_blank">{esc(ref)}</a></span>')
        else:
            w("      <ul>")
            for ref in references:
                w(f'        <li><a href="{esc(ref)}" target="_blank">{esc(ref)}</a></li>')
            w("      </ul>")
        w("    </div>")
        w("    <pagebreak />")
        w("  </div>")
    w("</section>")

    # ---- recommendations (placed near the end) -----------------------------
    w("<section>")
    w('  <h1 id="recommendations" class="in-toc numbered">Recommendations</h1>')
    w('  <table class="tbl-reco">')
    w('    <thead><tr><th style="width: 150px;">Name</th><th>Details</th></tr></thead>')
    w("    <tbody>")
    for finding in findings:
        fid = finding["id"]
        w(f'      <tr class="table-row-link">'
          f'<td><a class="ref" href="#{esc(fid)}">{esc(finding.get("title", ""))}</a></td>'
          f'<td><a class="ref" href="#{esc(fid)}">{r.md(finding.get("recommendation"))}</a></td></tr>')
    w("    </tbody>")
    w("  </table>")
    w("</section>")
    w("<pagebreak />")

    # ---- conclusion (placed near the end) ----------------------------------
    if (report.get("conclusion") or "").strip():
        w("<section>")
        w('  <h1 id="conclusion" class="in-toc numbered">Conclusion</h1>')
        w(r.md(report.get("conclusion")))
        w("</section>")
        w("<pagebreak />")

    # ---- disclaimer --------------------------------------------------------
    if (report.get("disclaimer") or "").strip():
        w('<section class="disclaimer">')
        w('  <h1 id="disclaimer" class="in-toc numbered">Disclaimer</h1>')
        w(r.md(report.get("disclaimer")))
        w("</section>")
        w("<pagebreak />")

    # ---- appendix ----------------------------------------------------------
    appendix_sections = report.get("appendix_sections") or []
    if appendix_sections:
        w('<section class="appendix">')
        w('  <h1 id="appendix" class="in-toc numbered">Appendix</h1>')
        for index, section in enumerate(appendix_sections, start=1):
            section_id = slugify(section.get("title", ""), f"appendix-{index}")
            w(f'  <h2 id="{esc(section_id)}" class="in-toc numbered">'
              f'{esc(section.get("title", ""))}</h2>')
            w(r.md(section.get("content")))
        w("</section>")

    body = "\n".join(out)

    # ---- table of contents / list of figures -------------------------------
    body = body.replace("@@TOC@@", build_toc(body))
    body = body.replace("@@LOF@@", build_lof(r.figures))

    return wrap_html(body, title)


def build_toc(body: str) -> str:
    collector = TocCollector()
    collector.feed(body)

    lines = ['<section id="toc">', "  <h1>Table of Contents</h1>", "  <ol>"]
    for item in collector.items:
        lines.append(
            f'    <li class="toc-level{item["level"]}">'
            f'<a href="#{esc(item["id"])}" class="ref">'
            f'<span>{esc(item["title"])}</span></a></li>'
        )
    lines.append("  </ol>")
    lines.append("</section>")
    lines.append("<pagebreak />")
    return "\n".join(lines)


def build_lof(figures: list[tuple[str, str]]) -> str:
    if not figures:
        return ""
    lines = ['<section id="lof">', "  <h1>List of Figures</h1>", "  <ul>"]
    for fig_id, caption in figures:
        lines.append(
            f'    <li><a href="#{esc(fig_id)}" class="ref ref-figure">'
            f'<span class="ref-title">{esc(caption)}</span></a></li>'
        )
    lines.append("  </ul>")
    lines.append("</section>")
    lines.append("<pagebreak />")
    return "\n".join(lines)


def wrap_html(body: str, title: str) -> str:
    links = "\n".join(
        f'  <link rel="stylesheet" href="design/{name}">' for name in STYLESHEETS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{esc(title)}</title>
{links}
</head>
<body>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--data", default="report.yml", help="report data file")
    parser.add_argument("--out", default="out", help="output directory")
    parser.add_argument("--html-only", action="store_true", help="skip PDF rendering")
    args = parser.parse_args()

    data_path = (ROOT / args.data) if not Path(args.data).is_absolute() else Path(args.data)
    if not data_path.exists():
        sys.exit(f"No such data file: {data_path}")

    with data_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    document = build_document(data, ROOT)

    out_dir = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / "report.html"
    html_path.write_text(document, encoding="utf-8")
    print(f"wrote {html_path.relative_to(ROOT)}")

    if args.html_only:
        return 0

    try:
        from weasyprint import HTML
    except ImportError:
        sys.exit("Missing dependency: weasyprint.  Run:  pip install -r requirements.txt")

    pdf_path = out_dir / "report.pdf"
    # base_url is the repository root so `design/...` and `images/...` resolve.
    HTML(string=document, base_url=str(ROOT) + "/").write_pdf(str(pdf_path))
    print(f"wrote {pdf_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
