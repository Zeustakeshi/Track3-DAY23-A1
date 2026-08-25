# LangGraph Agent Lab — Generated Report

_Generated: 2026-08-25T11:05:38+00:00_

## Summary metrics

| Metric | Value |
| --- | ---: |
| total_scenarios | 12 |
| success_rate | 100.0% |
| avg_nodes_visited | 6.42 |
| total_retries | 5 |
| total_interrupts | 3 |
| resume_success | False |

## Scenario results

| Scenario | Expected route | Actual route | Success | Nodes visited | Retries | Interrupts | Approval required | Approval observed | Latency (ms) | Errors |
| --- | --- | --- | :---: | ---: | ---: | ---: | :---: | :---: | ---: | :---: |
| S01_simple | simple | simple | ✅ | 4 | 0 | 0 | False | False | 0 | no |
| S02_tool | tool | tool | ✅ | 6 | 0 | 0 | False | False | 0 | no |
| S03_missing | missing_info | missing_info | ✅ | 4 | 0 | 0 | False | False | 0 | no |
| S04_risky | risky | risky | ✅ | 8 | 0 | 1 | True | True | 0 | no |
| S05_error | error | error | ✅ | 10 | 2 | 0 | False | False | 0 | yes |
| S06_delete | risky | risky | ✅ | 8 | 0 | 1 | True | True | 0 | no |
| S07_dead_letter | error | error | ✅ | 5 | 1 | 0 | False | False | 0 | yes |
| S08_cancel | risky | risky | ✅ | 8 | 0 | 1 | True | True | 0 | no |
| S09_track | tool | tool | ✅ | 6 | 0 | 0 | False | False | 0 | no |
| S10_broken | missing_info | missing_info | ✅ | 4 | 0 | 0 | False | False | 0 | no |
| S11_unavailable | error | error | ✅ | 10 | 2 | 0 | False | False | 0 | yes |
| S12_policy | simple | simple | ✅ | 4 | 0 | 0 | False | False | 0 | no |

## Architecture

The graph has 11 nodes wired as a fixed intake/classify entry, five conditional branches out of `classify` (simple, tool, missing_info, risky, error), a bounded `tool -> evaluate -> retry` loop, and a `risky_action -> approval` human-in-the-loop gate. Every branch converges on `finalize -> END`, so no scenario can terminate without an audit event being recorded. State is a single `AgentState` TypedDict shared across nodes and persisted per `thread_id` via the configured checkpointer.

## State reducers

`messages`, `tool_results`, `errors`, and `events` use the `add` reducer because they are append-only audit trails — every node that touches them must return a single new item, never the whole accumulated list, or entries get duplicated. `route`, `evaluation_result`, `pending_question`, `proposed_action`, and `approval` have no reducer (last-write-wins) because only the newest value is meaningful for routing; only `classify_node` is allowed to write `route`.

## Failure analysis

All scenarios met their expected route and output requirements in this run. See the failure modes documented in `reports/lab_report.md` for the two classes of failure the graph is designed to survive (bounded retry exhaustion, and route misclassification under LLM error).

## Improvement plan

- Add a crash-resume/state-history demonstration and set `resume_success=True`.
