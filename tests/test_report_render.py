"""Digest → fixed-format text rendering (PLAN.md §5 Brique 3 example format)."""

from __future__ import annotations

from datetime import date

from alfred.mandate.model import Deviation, DeviationType
from alfred.report.model import Baseline, Digest, Line, LineKind
from alfred.report.render import format_baseline, format_sources, render
from alfred.trace.model import EventId


def _cost_line(value: float, mean: float) -> Line:
    return Line(
        LineKind.COST_EUR,
        value,
        (EventId("c0f"),),
        baseline=Baseline(mean=mean, window_days=7, sample_days=5, sources=(EventId("h1"),)),
    )


def _digest_with_one_deviation() -> Digest:
    return Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(
            Line(
                LineKind.TASKS_COMPLETED,
                47.0,
                (EventId("a1c"), EventId("a1d"), EventId("a1e")),
            ),
            Line(LineKind.COST_EUR, 3.42, (EventId("c0f"),)),
            Line(LineKind.ESCALATIONS, 3.0, (EventId("e01"), EventId("e02"), EventId("e03"))),
        ),
        deviations=(
            Deviation(
                type=DeviationType.TOOL_NOT_ALLOWED,
                event_ids=(EventId("d0a"),),
                message="tool 'read_pii' is not in allowed_tools",
            ),
        ),
    )


def test_render_matches_fixed_format_single_deviation() -> None:
    lines = render(_digest_with_one_deviation()).splitlines()
    assert lines[0] == "Alfred · refund-bot-v3 · 2026-08-30"
    assert lines[1] == ""
    assert lines[2].startswith("Tasks completed:")
    assert "47" in lines[2]
    assert "[evt:a1c, a1d, a1e]" in lines[2]
    assert lines[3].startswith("Cost (tokens → €):")
    assert "3.42 €" in lines[3]
    assert "[evt:c0f]" in lines[3]
    assert lines[4].startswith("Escalations:")
    assert "3" in lines[4]
    assert "[evt:e01, e02, e03]" in lines[4]
    assert lines[5].startswith("Deviations (mandate):")
    assert "[evt:d0a]" in lines[5]
    assert "tool_not_allowed" in lines[5]
    assert "read_pii" in lines[5]
    assert len(lines) == 6


def test_render_omits_deviations_section_when_none() -> None:
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(Line(LineKind.TASKS_COMPLETED, 1.0, (EventId("e1"),)),),
    )
    output = render(digest)
    assert "Deviations" not in output


def test_format_sources_truncates_long_ids_to_prefix() -> None:
    assert format_sources((EventId("e69a993566e99bd0"),)) == "[evt:e69a9935…]"


def test_format_sources_keeps_short_ids_intact() -> None:
    assert format_sources((EventId("d0a"), EventId("demo-1-task"))) == "[evt:d0a, demo-1-task]"


def test_format_sources_samples_at_most_three_ids() -> None:
    ids = tuple(EventId(f"f0dd0fd8f111ebc{i}") for i in range(6))
    assert format_sources(ids) == "[evt:f0dd0fd8…, f0dd0fd8…, f0dd0fd8… +3]"


def test_format_sources_omits_sample_suffix_at_three_ids() -> None:
    assert format_sources((EventId("a1"), EventId("a2"), EventId("a3"))) == "[evt:a1, a2, a3]"


def test_render_never_shows_a_full_long_event_id() -> None:
    long_id = "784800533a465770"
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(Line(LineKind.TASKS_COMPLETED, 1.0, (EventId(long_id),)),),
    )
    output = render(digest)
    assert long_id not in output
    assert "evt:78480053…" in output


def test_format_baseline_none_without_baseline() -> None:
    assert format_baseline(Line(LineKind.COST_EUR, 3.42, (EventId("c0f"),))) is None


def test_format_baseline_flags_a_doubling_with_warning() -> None:
    # 3.42 vs mean 1.20 → +185% → over the ±100% threshold.
    text = format_baseline(_cost_line(3.42, 1.20))
    assert text is not None
    assert "+185% vs 7-day avg" in text
    assert "⚠️" in text


def test_format_baseline_no_warning_below_threshold() -> None:
    text = format_baseline(_cost_line(1.10, 1.00))  # +10%
    assert text == "+10% vs 7-day avg"
    assert "⚠️" not in text


def test_format_baseline_warns_symmetrically_on_a_collapse() -> None:
    text = format_baseline(_cost_line(0.40, 1.00))  # -60% → not warned
    assert text == "-60% vs 7-day avg"
    warned = format_baseline(_cost_line(0.20, 1.00))  # -80%... still below 100%
    assert warned == "-80% vs 7-day avg"
    halved = format_baseline(_cost_line(0.00, 1.00))  # -100% → warned
    assert halved is not None and "⚠️" in halved


def test_render_appends_baseline_on_the_same_line() -> None:
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(_cost_line(3.42, 1.20),),
    )
    rows = render(digest).splitlines()
    cost_row = next(row for row in rows if row.startswith("Cost (tokens → €):"))
    assert "[evt:c0f]" in cost_row
    assert "(+185% vs 7-day avg ⚠️)" in cost_row


def test_render_lists_each_deviation_when_multiple() -> None:
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(),
        deviations=(
            Deviation(DeviationType.TOOL_NOT_ALLOWED, (EventId("d1"),), "msg one"),
            Deviation(DeviationType.BUDGET_EXCEEDED, (EventId("d2"),), "msg two"),
        ),
    )
    lines = render(digest).splitlines()
    header = next(line for line in lines if line.startswith("Deviations (mandate):"))
    assert "2" in header
    assert any("tool_not_allowed" in line and "msg one" in line for line in lines)
    assert any("budget_exceeded" in line and "msg two" in line for line in lines)
