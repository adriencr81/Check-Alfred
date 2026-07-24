"""Digest → a self-contained, shareable HTML report (F4, docs/adr/0020).

The third render of a `Digest`, alongside the fixed-format text
(`alfred.report.render`) and Slack Block Kit (`alfred.deliver.slack`). It reuses
this package's `LABELS`, `format_value` and `format_baseline` so labels, values
and baselines stay identical across every sink (the discipline the `render`
docstring calls for).

The output is one autonomous HTML5 file — inline CSS, **zero JavaScript**, no
external resource — so a manager can forward a navigable proof (PLAN.md §13 F4,
"zéro infra"). Each source event ID is an in-page link to an Evidence entry that
carries the same ID, which is what makes "each line clickable to its source
events" literally true within a single file. It is deliberately poorer than the
paid evidence dossier (v0.4): it surfaces the anchoring IDs, not the events —
the baseline's historical `sources` stay in the data, unlinked, exactly as they
are in the stdout and Slack renders.
"""

from __future__ import annotations

from html import escape

from alfred.mandate.model import Deviation
from alfred.report.model import Digest, Line
from alfred.report.render import LABELS, format_baseline, format_value
from alfred.trace.model import EventId

_STYLE = """
:root { color-scheme: light; }
body { font: 15px/1.5 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       color: #1b1f24; background: #f6f8fa; margin: 0; padding: 2rem 1rem; }
main { max-width: 46rem; margin: 0 auto; background: #fff; border: 1px solid #d0d7de;
       border-radius: 10px; padding: 1.5rem 1.75rem; }
h1 { font-size: 1.15rem; margin: 0 0 1.25rem; }
h2 { font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.04em;
     color: #57606a; margin: 1.5rem 0 0.5rem; }
table { width: 100%; border-collapse: collapse; }
th[scope=row] { text-align: left; font-weight: 600; padding: 0.4rem 0; white-space: nowrap; }
td { padding: 0.4rem 0 0.4rem 1rem; vertical-align: baseline; }
td.value { font-variant-numeric: tabular-nums; white-space: nowrap; }
.baseline { color: #57606a; font-size: 0.85em; }
.sources { font-size: 0.85em; }
a.evt { color: #0969da; text-decoration: none; }
a.evt:hover { text-decoration: underline; }
ul.deviations { list-style: none; padding: 0; margin: 0; }
ul.deviations li { padding: 0.35rem 0.6rem; margin: 0.35rem 0; border-left: 3px solid #d1242f;
                   background: #fff8f8; border-radius: 0 4px 4px 0; }
.dev-type { font-weight: 600; color: #d1242f; }
ul.evidence { list-style: none; padding: 0; margin: 0; }
ul.evidence li { padding: 0.25rem 0; border-top: 1px solid #eaeef2; }
ul.evidence li:first-child { border-top: 0; }
ul.evidence code { font-size: 0.85em; word-break: break-all; }
section.narrative { margin: 0 0 1.25rem; }
section.narrative p { margin: 0 0 0.5rem; }
footer { color: #57606a; font-size: 0.8em; margin-top: 1.5rem;
         border-top: 1px solid #eaeef2; padding-top: 0.75rem; }
"""


def _anchor_map(digest: Digest) -> dict[EventId, str]:
    """Assign each distinct source event ID a stable in-page anchor.

    First-appearance order over the lines, then the deviations. An index-based
    anchor (`evt-0`, `evt-1`, …) sidesteps any fragment-escaping or collision
    concern: the link `href` and its Evidence target are built from the same
    map, so every `#evt-n` resolves. The baseline's historical `sources` are
    intentionally excluded — like stdout and Slack, this render surfaces the
    day's own anchors, not the comparison's.
    """
    anchors: dict[EventId, str] = {}
    ordered: list[EventId] = [eid for line in digest.lines for eid in line.sources]
    ordered += [eid for deviation in digest.deviations for eid in deviation.event_ids]
    for event_id in ordered:
        if event_id not in anchors:
            anchors[event_id] = f"evt-{len(anchors)}"
    return anchors


def _source_links(event_ids: tuple[EventId, ...], anchors: dict[EventId, str]) -> str:
    links = [f'<a class="evt" href="#{anchors[eid]}">{escape(eid)}</a>' for eid in event_ids]
    return '<span class="sources">' + ", ".join(links) + "</span>"


def _line_row(line: Line, anchors: dict[EventId, str]) -> str:
    baseline = format_baseline(line)
    baseline_html = (
        f' <span class="baseline">{escape(baseline)}</span>' if baseline is not None else ""
    )
    return (
        f'<tr><th scope="row">{escape(LABELS[line.kind])}</th>'
        f'<td class="value">{escape(format_value(line))}{baseline_html}</td>'
        f"<td>{_source_links(line.sources, anchors)}</td></tr>"
    )


def _deviation_item(deviation: Deviation, anchors: dict[EventId, str]) -> str:
    return (
        f'<li><span class="dev-type">{escape(deviation.type.value)}</span>: '
        f"{escape(deviation.message)} {_source_links(deviation.event_ids, anchors)}</li>"
    )


def render_html(digest: Digest, narrative: tuple[str, ...] = ()) -> str:
    """Render `digest` as one self-contained HTML document (see module docstring).

    When `narrative` is given (the verified prose sentences from
    `alfred.narrate`, plain text each carrying its own `[evt:…]` citation), it
    is rendered as an intro paragraph block above the metric table. Empty (the
    default) keeps the plain computed report — the layer stays decoupled from
    `narrate`, receiving strings, not `Sentence`s.
    """
    anchors = _anchor_map(digest)
    title = f"Alfred · {escape(digest.agent)} · {digest.date.isoformat()}"

    sections: list[str] = [f"<h1>{title}</h1>"]
    if narrative:
        paragraphs = "\n".join(f"<p>{escape(text)}</p>" for text in narrative)
        sections.append(f'<section class="narrative">{paragraphs}</section>')
    if digest.lines:
        rows = "\n".join(_line_row(line, anchors) for line in digest.lines)
        sections.append(f"<table>{rows}</table>")
    if digest.deviations:
        count = len(digest.deviations)
        items = "\n".join(_deviation_item(deviation, anchors) for deviation in digest.deviations)
        sections.append(
            f"<h2>Deviations (mandate) — {count}</h2>"
            f'<ul class="deviations">{items}</ul>'
        )
    if anchors:
        items = "\n".join(
            f'<li id="{anchor}"><code>{escape(event_id)}</code></li>'
            for event_id, anchor in anchors.items()
        )
        sections.append(f'<h2>Evidence</h2><ul class="evidence">{items}</ul>')
    sections.append(
        "<footer>Every line is computed from an identifiable trace event — "
        "no self-reported summaries. Generated by Alfred.</footer>"
    )

    body = "\n".join(sections)
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>"
        f"<style>{_STYLE}</style></head>"
        f"<body><main>{body}</main></body></html>\n"
    )
