"""Monitoring agent graph.

Design choices baked in on purpose:
- fetch_node never raises on a single target failure — one broken selector
  shouldn't kill the whole run. Failures are tracked per-target instead.
- The LLM is only ever called when something actually changed (route_after_fetch),
  and ALL changes for a run are summarized in a single call — not one per target.
  That's what keeps LangSmith trace volume and Groq usage near-zero on quiet runs.
- A source that's failed 3+ runs in a row gets folded into the alert once, so a
  dead selector surfaces to you instead of silently going stale forever.
"""
import os
from typing import Any, Dict, List, TypedDict

from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from alerts import send_alert
from fetchers import extract_items, fetch_page, hash_value
from guardrails import RunGuardrails
from state_store import save_state

guardrails = RunGuardrails()


class MonitorState(TypedDict):
    targets: List[Dict[str, Any]]
    stored_state: Dict[str, Any]
    changes: List[Dict[str, Any]]
    fetch_errors: List[Dict[str, Any]]
    digest: str


def _clean_num(s: Any) -> str:
    return "".join(c for c in str(s) if c.isdigit() or c == ".")


def _is_decrease(current: Any, previous: Any) -> bool:
    try:
        return float(_clean_num(current)) < float(_clean_num(previous))
    except (TypeError, ValueError):
        return True  # can't compare numerically — surface it, let a human judge


def fetch_node(state: MonitorState) -> MonitorState:
    stored = state["stored_state"]
    changes: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for target in state["targets"]:
        tid = target["id"]
        try:
            html = fetch_page(target["url"])
            items = extract_items(html, target["selector"])

            if target["alert_on"] == "new_items":
                prev_items = set(stored.get(tid, {}).get("items", []))
                new_items = [i for i in items if i not in prev_items]
                if new_items:
                    changes.append({"id": tid, "type": "new_items", "items": new_items[:10]})
                stored[tid] = {
                    "items": items[-target.get("max_items_tracked", 50):],
                    "consecutive_failures": 0,
                }

            elif target["alert_on"] == "value_change":
                current = items[0] if items else None
                previous = stored.get(tid, {}).get("value")
                if previous is not None and current != previous:
                    direction = target.get("direction")
                    if direction != "decrease" or _is_decrease(current, previous):
                        changes.append({"id": tid, "type": "value_change", "old": previous, "new": current})
                stored[tid] = {"value": current, "consecutive_failures": 0}

        except Exception as e:  # noqa: BLE001 — deliberately broad: one bad target must not kill the run
            failures = stored.get(tid, {}).get("consecutive_failures", 0) + 1
            stored.setdefault(tid, {})["consecutive_failures"] = failures
            errors.append({"id": tid, "error": str(e), "consecutive_failures": failures})

    return {**state, "stored_state": stored, "changes": changes, "fetch_errors": errors}


def route_after_fetch(state: MonitorState) -> str:
    broken = [e for e in state["fetch_errors"] if e["consecutive_failures"] >= 3]
    if state["changes"] or broken:
        return "summarize"
    return "persist"


def summarize_node(state: MonitorState) -> MonitorState:
    guardrails.register_llm_call()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    llm = ChatGroq(model=model, temperature=0)

    broken = [e for e in state["fetch_errors"] if e["consecutive_failures"] >= 3]
    prompt = (
        "Write a short alert digest (max 150 words, plain text, no markdown headers) "
        "for a personal monitoring bot.\n\n"
        f"Changes detected:\n{state['changes']}\n\n"
        f"Sources that have failed 3+ runs in a row (likely a broken selector or site change):\n{broken}\n\n"
        "Be concise and specific — name the items/prices, don't use generic phrasing."
    )
    result = llm.invoke(prompt)
    return {**state, "digest": result.content}


def alert_node(state: MonitorState) -> MonitorState:
    send_alert(os.environ["DISCORD_WEBHOOK_URL"], state["digest"])
    return state


def persist_node(state: MonitorState) -> MonitorState:
    save_state(state["stored_state"])
    return state


def build_graph():
    graph = StateGraph(MonitorState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("alert", alert_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("fetch")
    graph.add_conditional_edges("fetch", route_after_fetch, {"summarize": "summarize", "persist": "persist"})
    graph.add_edge("summarize", "alert")
    graph.add_edge("alert", "persist")
    graph.add_edge("persist", END)

    return graph.compile()
