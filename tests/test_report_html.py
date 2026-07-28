"""Digest → self-contained shareable HTML report (F4, docs/adr/0020)."""

from __future__ import annotations

import re
from datetime import date

from alfred.mandate.model import Deviation, DeviationType
from alfred.report.html import render_html
from alfred.report.model import Baseline, Digest, Line, LineKind
from alfred.trace.model import EventId


def _digest() -> Digest:
    return Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(
            Line(LineKind.TASKS_COMPLETED, 47.0, (EventId("a1c"), EventId("a1d"))),
            Line(
                LineKind.COST_EUR,
                3.42,
                (EventId("c0f"),),
                baseline=Baseline(
                    mean=1.20, window_days=7, sample_days=5, sources=(EventId("h1"),)
                ),
            ),
        ),
        deviations=(
            Deviation(
                DeviationType.TOOL_NOT_ALLOWED,
                (EventId("d0a"),),
                "tool 'read_pii' is not in allowed_tools",
            ),
        ),
    )


def test_render_html_includes_narrative_when_given() -> None:
    html = render_html(_digest(), narrative=("Completed 47 tasks today. [evt:a1c, a1d]",))
    assert 'class="narrative"' in html
    assert "Completed 47 tasks today. [evt:a1c, a1d]" in html


def test_render_html_has_no_narrative_section_by_default() -> None:
    assert 'class="narrative"' not in render_html(_digest())


def test_render_html_is_a_self_contained_document() -> None:
    html = render_html(_digest())
    assert "<!doctype html>" in html.lower()
    assert "<style>" in html  # CSS inline, not linked
    # Fully self-contained, zero JS, no external resource (zero infra).
    for external in ("http://", "https://", "src=", "<script"):
        assert external not in html


def test_render_html_shows_labels_values_and_baseline() -> None:
    html = render_html(_digest())
    assert "Tasks completed" in html
    assert "Cost (tokens → €)" in html
    assert "47" in html
    assert "3.42 €" in html
    assert "+185% vs 7-day avg" in html  # reuses render.format_baseline
    assert "⚠️" in html


def test_render_html_header_carries_agent_and_date() -> None:
    html = render_html(_digest())
    assert "refund-bot-v3" in html
    assert "2026-08-30" in html


def test_every_source_link_resolves_to_an_evidence_anchor() -> None:
    html = render_html(_digest())
    hrefs = set(re.findall(r'href="#(evt-\d+)"', html))
    ids = set(re.findall(r'id="(evt-\d+)"', html))
    assert hrefs  # the report has clickable sources
    # Each line / deviation is clickable *to its source events* — every link
    # target exists in the evidence section (F4's defining behaviour).
    assert hrefs <= ids


def test_render_html_anchors_the_deviation() -> None:
    html = render_html(_digest())
    assert "tool_not_allowed" in html
    assert "read_pii" in html
    assert 'href="#evt-' in html  # the deviation's source is a link too


def test_render_html_escapes_untrusted_text() -> None:
    digest = Digest(
        agent="a<script>x</script>&",
        date=date(2026, 8, 30),
        lines=(Line(LineKind.TASKS_COMPLETED, 1.0, (EventId("e1"),)),),
        deviations=(
            Deviation(DeviationType.FORBIDDEN_ACTION, (EventId("e2"),), "drop <table> & run"),
        ),
    )
    html = render_html(digest)
    assert "<script>x</script>" not in html  # never emitted raw
    assert "&lt;script&gt;" in html
    assert "drop &lt;table&gt; &amp; run" in html


def test_render_html_shows_full_event_ids_in_evidence() -> None:
    long_id = "784800533a465770e69a993566e99bd0"
    digest = Digest(
        agent="bot",
        date=date(2026, 8, 30),
        lines=(Line(LineKind.TASKS_COMPLETED, 1.0, (EventId(long_id),)),),
    )
    html = render_html(digest)
    # HTML has room for the full ID — unlike the width-bound text render.
    assert long_id in html


def test_render_html_omits_deviations_section_when_clean() -> None:
    digest = Digest(
        agent="bot",
        date=date(2026, 8, 30),
        lines=(Line(LineKind.TASKS_COMPLETED, 1.0, (EventId("e1"),)),),
    )
    html = render_html(digest)
    assert "Deviations" not in html
    assert 'id="evt-0"' in html  # the line's source is still in evidence
