"""Standalone evidence script for the SQLite checkpointer — OWNER: M5.

Independent of graph.py (still under construction by M1): builds a tiny
throwaway StateGraph using the real AgentState schema + a couple of nodes
that loop a few times, so it exercises the exact same checkpointer code
path (`persistence.build_checkpointer("sqlite", ...)`) without depending
on any other member's file.

What it proves:
  1. `build_checkpointer("sqlite", ...)` returns a working SqliteSaver
     (WAL mode, no `from_conn_string()`).
  2. State is durably checkpointed across steps for a given thread_id.
  3. `graph.get_state_history(config)` returns > 1 checkpoint (persistence
     + time-travel evidence for Gate 3 / rubric "Persistence and recovery").
  4. A **second process** re-opening the same DB file can resume /
     inspect the history of a thread created by the first process
     (crash-resume evidence) — simulated here via two separate
     `build_checkpointer` + `build_graph` calls against the same file.

Usage:
    python scripts/test_persistence_resume.py

Writes a human-readable log to reports/persistence_resume_evidence.log
"""

from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langgraph_agent_lab.persistence import build_checkpointer  # noqa: E402
from langgraph_agent_lab.state import AgentState  # noqa: E402

DB_PATH = "outputs/persistence_demo.db"
LOG_PATH = "reports/persistence_resume_evidence.log"
THREAD_ID = "resume-demo-thread"


def _build_demo_graph(checkpointer):
    """A tiny 3-node looping graph sharing AgentState, independent of graph.py."""
    from langgraph.graph import END, START, StateGraph

    def step_node(state: AgentState) -> dict:
        attempt = state.get("attempt", 0) + 1
        return {
            "attempt": attempt,
            "events": [{"node": "step", "event_type": "completed", "message": f"attempt {attempt}"}],
        }

    def route_step(state: AgentState) -> str:
        return "step" if state.get("attempt", 0) < 3 else END

    builder = StateGraph(AgentState)
    builder.add_node("step", step_node)
    builder.add_edge(START, "step")
    builder.add_conditional_edges("step", route_step, {"step": "step", END: END})
    return builder.compile(checkpointer=checkpointer)


def main() -> None:
    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        lines.append(msg)

    log(f"=== SQLite checkpointer resume evidence — {datetime.datetime.now().isoformat()} ===")

    os.makedirs("outputs", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # --- Process 1: run the graph, produce several checkpoints ---
    checkpointer_1 = build_checkpointer("sqlite", DB_PATH)
    log(f"build_checkpointer('sqlite', {DB_PATH!r}) -> {checkpointer_1!r}")
    graph_1 = _build_demo_graph(checkpointer_1)
    config = {"configurable": {"thread_id": THREAD_ID}}

    result = graph_1.invoke({"attempt": 0, "events": []}, config=config)
    log(f"invoke() final state: attempt={result['attempt']}, events={len(result['events'])}")

    history_1 = list(graph_1.get_state_history(config))
    log(f"[process 1] len(list(graph.get_state_history(config))) = {len(history_1)}")
    assert len(history_1) > 1, "expected multiple checkpoints from the looped run"

    # --- Process 2: fresh checkpointer + fresh graph object over the SAME db file ---
    # Simulates a crash/restart: no in-memory state is reused, only the sqlite file.
    checkpointer_2 = build_checkpointer("sqlite", DB_PATH)
    graph_2 = _build_demo_graph(checkpointer_2)

    resumed_state = graph_2.get_state(config)
    log(f"[process 2] resumed state.values = {resumed_state.values}")
    assert resumed_state.values["attempt"] == result["attempt"], "resumed state must match last checkpoint"

    history_2 = list(graph_2.get_state_history(config))
    log(f"[process 2] len(list(graph.get_state_history(config))) = {len(history_2)}")
    assert len(history_2) == len(history_1), "history must survive process restart (same db file)"

    log("PASS: sqlite checkpoint survives a fresh process re-opening the same db file.")

    os.makedirs("reports", exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nLog written to {LOG_PATH}")


if __name__ == "__main__":
    main()
