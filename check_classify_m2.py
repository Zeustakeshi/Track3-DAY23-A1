"""Ad-hoc script: check classify_node accuracy against all scenarios.

Run: uv run python check_classify_m2.py
"""

from langgraph_agent_lab.nodes_classify import classify_node
from langgraph_agent_lab.scenarios import load_scenarios

scenarios = load_scenarios("data/sample/scenarios.jsonl")
correct = 0
for s in scenarios:
    r = classify_node({"query": s.query})
    ok = r["route"] == s.expected_route
    correct += int(ok)
    status = "OK" if ok else "SAI"
    print(f"{s.id:20s} expected={s.expected_route:15s} actual={r['route']:15s} {status}")

print(f"accuracy: {correct}/{len(scenarios)}")
