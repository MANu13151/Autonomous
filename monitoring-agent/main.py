import os

import yaml

from graph import build_graph
from state_store import load_state


def main() -> None:
    # Load local .env if present (for local runs)
    if os.path.exists(".env"):
        with open(".env") as ef:
            for line in ef:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # 3 lines and every node call shows up in LangSmith automatically.
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "monitoring-agent")

    with open("targets.yaml") as f:
        targets = yaml.safe_load(f)["targets"]

    graph = build_graph()
    initial_state = {
        "targets": targets,
        "stored_state": load_state(),
        "changes": [],
        "fetch_errors": [],
        "digest": "",
    }

    graph.invoke(initial_state)


if __name__ == "__main__":
    main()
