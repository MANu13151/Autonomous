"""Hard caps so a bug (e.g. every target flapping at once) can't runaway the LLM bill.
Note the design in graph.py already batches all changes into ONE summarize call per run —
this counter is the defensive backstop, not the primary control."""

MAX_LLM_CALLS_PER_RUN = 3


class LLMBudgetExceeded(Exception):
    pass


class RunGuardrails:
    def __init__(self, max_llm_calls: int = MAX_LLM_CALLS_PER_RUN):
        self.max_llm_calls = max_llm_calls
        self.llm_calls = 0

    def register_llm_call(self) -> None:
        self.llm_calls += 1
        if self.llm_calls > self.max_llm_calls:
            raise LLMBudgetExceeded(
                f"Run exceeded {self.max_llm_calls} LLM calls — halting to protect budget."
            )
