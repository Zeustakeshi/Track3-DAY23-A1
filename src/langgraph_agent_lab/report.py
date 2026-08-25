"""Report generation helper.

Renders a markdown report from a MetricsReport: a summary table, a
per-scenario table, and four narrative sections (architecture, reducers,
failure analysis, improvement plan).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .metrics import MetricsReport, ScenarioMetric


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _summary_table(metrics: MetricsReport) -> str:
    rows = [
        ("total_scenarios", str(metrics.total_scenarios)),
        ("success_rate", _fmt_pct(metrics.success_rate)),
        ("avg_nodes_visited", f"{metrics.avg_nodes_visited:.2f}"),
        ("total_retries", str(metrics.total_retries)),
        ("total_interrupts", str(metrics.total_interrupts)),
        ("resume_success", str(metrics.resume_success)),
    ]
    lines = ["| Metric | Value |", "| --- | ---: |"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    return "\n".join(lines)


def _scenario_row(item: ScenarioMetric) -> str:
    status = "✅" if item.success else "❌"
    errors = "yes" if item.errors else "no"
    return (
        f"| {item.scenario_id} | {item.expected_route} | {item.actual_route or '—'} "
        f"| {status} | {item.nodes_visited} | {item.retry_count} | {item.interrupt_count} "
        f"| {item.approval_required} | {item.approval_observed} | {item.latency_ms} | {errors} |"
    )


def _scenario_table(metrics: MetricsReport) -> str:
    header = (
        "| Scenario | Expected route | Actual route | Success | Nodes visited "
        "| Retries | Interrupts | Approval required | Approval observed | Latency (ms) | Errors |"
    )
    sep = "| --- | --- | --- | :---: | ---: | ---: | ---: | :---: | :---: | ---: | :---: |"
    rows = [_scenario_row(item) for item in metrics.scenario_metrics]
    return "\n".join([header, sep, *rows])


def _failed_scenarios(metrics: MetricsReport) -> list[ScenarioMetric]:
    return [item for item in metrics.scenario_metrics if not item.success]


def _architecture_section() -> str:
    return (
        "The graph has 11 nodes wired as a fixed intake/classify entry, five conditional "
        "branches out of `classify` (simple, tool, missing_info, risky, error), a bounded "
        "`tool -> evaluate -> retry` loop, and a `risky_action -> approval` human-in-the-loop "
        "gate. Every branch converges on `finalize -> END`, so no scenario can terminate "
        "without an audit event being recorded. State is a single `AgentState` TypedDict "
        "shared across nodes and persisted per `thread_id` via the configured checkpointer."
    )


def _reducer_section() -> str:
    return (
        "`messages`, `tool_results`, `errors`, and `events` use the `add` reducer because "
        "they are append-only audit trails — every node that touches them must return a "
        "single new item, never the whole accumulated list, or entries get duplicated. "
        "`route`, `evaluation_result`, `pending_question`, `proposed_action`, and `approval` "
        "have no reducer (last-write-wins) because only the newest value is meaningful for "
        "routing; only `classify_node` is allowed to write `route`."
    )


def _failure_analysis_section(metrics: MetricsReport) -> str:
    failed = _failed_scenarios(metrics)
    if not failed:
        return (
            "All scenarios met their expected route and output requirements in this run. "
            "See the failure modes documented in `reports/lab_report.md` for the two classes "
            "of failure the graph is designed to survive (bounded retry exhaustion, and route "
            "misclassification under LLM error)."
        )
    lines = ["The following scenarios did not meet expectations in this run:"]
    for item in failed:
        reason = (
            f"expected `{item.expected_route}`, got `{item.actual_route}`"
            if item.actual_route != item.expected_route
            else "route matched but output/approval requirements were not met"
        )
        lines.append(f"- `{item.scenario_id}`: {reason} ({len(item.errors)} error(s) logged)")
    return "\n".join(lines)


def _improvement_plan_section(metrics: MetricsReport) -> str:
    items = []
    if metrics.success_rate < 1.0:
        items.append(
            "Investigate and fix the failing scenarios listed above before the next Gate 2 run."
        )
    if metrics.total_retries == 0:
        items.append(
            "No retries were observed — re-run S05/S07 specifically to confirm the retry loop "
            "and dead-letter path are exercised."
        )
    if metrics.total_interrupts < 2:
        items.append(
            "Fewer than 2 approval events were recorded — confirm S04/S06 reach `approval_node`."
        )
    if not metrics.resume_success:
        items.append(
            "Add a crash-resume/state-history demonstration and set `resume_success=True`."
        )
    if not items:
        items.append("Harden LLM error handling and add a Postgres checkpointer as a stretch goal.")
    return "\n".join(f"- {line}" for line in items)


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    Includes: a metrics summary table, a per-scenario results table, and four
    narrative sections (architecture, reducers, failure analysis, improvement
    plan) derived from the metrics. Return: formatted markdown string.
    """
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""# LangGraph Agent Lab — Generated Report

_Generated: {generated_at}_

## Summary metrics

{_summary_table(metrics)}

## Scenario results

{_scenario_table(metrics)}

## Architecture

{_architecture_section()}

## State reducers

{_reducer_section()}

## Failure analysis

{_failure_analysis_section(metrics)}

## Improvement plan

{_improvement_plan_section(metrics)}
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
