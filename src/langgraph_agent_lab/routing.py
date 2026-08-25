"""Routing functions for conditional edges.

Each function takes AgentState and returns a string -- the name of the next node.
These strings MUST match node names registered in graph.py.
"""

from __future__ import annotations

from .state import AgentState

_AFTER_CLASSIFY: dict[str, str] = {
    "simple": "answer",
    "tool": "tool",
    "missing_info": "clarify",
    "risky": "risky_action",
    "error": "retry",
}


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.

    Mapping:
    - "simple"       -> "answer"
    - "tool"         -> "tool"
    - "missing_info" -> "clarify"
    - "risky"        -> "risky_action"
    - "error"        -> "retry"
    - unknown/default -> "answer"
    """
    route = state.get("route", "")
    return _AFTER_CLASSIFY.get(route, "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Decide if tool result is satisfactory or needs retry.

    This is the 'done?' check that creates the retry loop --
    a key LangGraph advantage over linear LCEL chains.

    - If evaluation_result == "needs_retry" -> "retry"
    - Otherwise -> "answer"
    """
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry the tool or give up.

    MUST be bounded -- unbounded retry loops will fail grading.

    - If attempt < max_attempts -> "tool" (try again)
    - If attempt >= max_attempts -> "dead_letter" (give up, escalate)

    Reads both values from state (never hard-code the limit) -- retry_or_fallback_node
    increments "attempt" BEFORE this function is called, per CONTRACT.md section 4.
    """
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    if attempt < max_attempts:
        return "tool"
    return "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Route based on human approval decision.

    - If approved -> "tool" (proceed with risky action)
    - If rejected -> "clarify" (ask user for alternative)

    CONTRACT.md rule 2: "approval" is a plain dict, e.g.
    {"approved": bool, "reviewer": str, "comment": str} -- never a Pydantic object.
    """
    approval = state.get("approval") or {}
    if approval.get("approved") is True:
        return "tool"
    return "clarify"
