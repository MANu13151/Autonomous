"""Tiny JSON state store. Committed back to git by the workflow after each run —
that gives you free persistence AND a git-log audit trail of every change detected."""
import json
from pathlib import Path

STATE_PATH = Path("state.json")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
