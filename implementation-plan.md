# Autonomous Agent System — Implementation Plan

## Goal
One supervised system, three agents, running unattended (including overnight),
observable through LangSmith, staying at or near $0/month:

1. **Monitoring & alerts** — jobs, prices, etc.
2. **Research & report generation**
3. **Coding / repo issue fixing**

Built and shipped in that order, not all at once — each phase should be stable
before the next one starts.

## Guiding principles

- **Autonomy without idle cost.** Nothing runs (and nothing bills) between
  triggers. Use scheduled/event-triggered CI jobs, not a standing server.
- **Memory instead of re-instruction.** State (backlog, checkpoints, last-seen
  values) persists between runs so you configure something once, not every time.
- **Guardrails over trust.** Step caps, LLM-call caps, and timeouts on every
  run, because nobody's watching in real time when it fails.
- **Risk-tiered autonomy.** Read-only actions (alerts, reports) run fully
  autonomously. Anything irreversible or external (merging code, spending
  money) stops for your approval.

## Shared stack

| Layer | Choice | Free-tier reality (verified against current docs) |
|---|---|---|
| Orchestration | LangGraph | open source, no cost |
| LLM | Groq | 30 req/min, 6,000 tokens/min, 14,400 req/day, no card required, all models |
| Search (research agent) | Tavily | 1,000 credits/month, no card required |
| Observability | LangSmith | 5,000 traces/month, 14-day retention, 1 seat (free Developer tier) |
| Trigger/host | GitHub Actions | unlimited free on public repos w/ standard runners; 2,000 min/month free on private repos |
| Alerts | Discord webhook | free, no bot/OAuth needed |
| State | committed JSON/SQLite in-repo | free, and gives a git-log audit trail for free |

**Repo visibility:** public, for this system — unlocks unlimited Actions
minutes. Keep anything genuinely sensitive (real employer names, financial
thresholds) out of committed state/config, since it becomes public history.
The code agent (Phase 3) may warrant its own repo/visibility decision later
if it touches real work.

**LangSmith projects:** one per agent (`monitoring-agent`, `research-agent`,
`code-agent`) so trace/cost usage is visible per domain instead of blended.

**Discord channels:** one per agent (`#alerts`, `#research`, `#code-review`)
off the same server, so notifications are triaged at a glance.

**Shared code:** a `common/` module for `alerts.py` and `guardrails.py`,
imported by all three agents rather than duplicated.

---

## Phase 1 — Monitoring & Alerts ✅ sketched

**Status:** scaffold built (`monitoring-agent.zip`), not yet deployed.

**What it does:** polls a configurable list of targets (`targets.yaml`),
diffs against last-seen state, and only spends an LLM call when something
actually changed — batched into one summarization call per run, not one
per target.

**Trigger:** cron, every 30 min (`workflow_dispatch` also enabled for
manual runs).

**Files:** `targets.yaml`, `fetchers.py`, `state_store.py`, `guardrails.py`,
`alerts.py`, `graph.py`, `main.py`, `.github/workflows/monitor.yml`

**Before going live:**
- [ ] Push scaffold to a new public repo
- [ ] Add repo secrets: `GROQ_API_KEY`, `LANGCHAIN_API_KEY`, `DISCORD_WEBHOOK_URL`
- [ ] Create Discord server/channel + webhook (see chat for step-by-step)
- [ ] Replace example entries in `targets.yaml` with real URLs/selectors
- [ ] Trigger one manual run via `workflow_dispatch`, confirm the alert lands
- [ ] Let it run unattended for 3–5 days before trusting it fully

**Watch for:** selectors breaking when a site changes layout (the
3-failures-in-a-row alert should catch this); LangSmith trace count staying
low on quiet runs (confirms the "only call the LLM on change" design is
working as intended).

---

## Phase 2 — Research & Report Generation (next)

**What it does:** takes a topic (from a backlog you add to, or a fixed
daily list), searches the web via Tavily, synthesizes a short report via
Groq, and delivers it (repo markdown file, or emailed/posted digest).

**Trigger:** cron for recurring topics (e.g. a daily digest), or
backlog-driven if you want to drop in one-off topics.

**Key design decisions to make when building this:**
- Backlog format: a simple table/file (`topics.yaml` or a small SQLite
  table) so you add a topic once instead of prompting fresh each time
- Report length/depth vs. Tavily credit budget (1,000 credits/month —
  a "deep" research call can cost far more credits than a basic search,
  so cap search depth per topic)
- Output destination: committed markdown in-repo is simplest and free;
  email/Notion are options if you want it somewhere else

**Guardrails specific to this agent:**
- Cap Tavily calls per topic (avoid one topic burning the monthly credit budget)
- Same LLM-call-cap pattern as monitoring, sized for a longer research chain

**Risk tier:** low — fully autonomous is fine. Worst case is a mediocre
report, not a broken system.

---

## Phase 3 — Coding / Repo Issue Fixing (last)

**What it does:** picks up a flagged issue (e.g. labeled `agent-fix`),
reproduces it, writes a fix, runs the test suite, and opens a **draft PR**.

**Trigger:** GitHub webhook (`issues: opened` or a label event) — not cron.
It should only run when there's an actual issue, which also means near-zero
cost when idle.

**Hard rule: it never merges.** This is the one domain where the approval
gate is not optional. Autonomous merge is a fundamentally different risk
than a bad monitoring alert or a mediocre report.

**Key design decisions to make when building this:**
- Sandbox/test execution: run inside the same Actions container (free
  compute already available)
- Repo visibility/scope: decide separately from Phases 1–2, especially if
  it touches real/work repos rather than personal projects
- What "done" looks like: draft PR + test results + a summary comment,
  waiting in `#code-review` for your review — never auto-merged

**Risk tier:** high — build this only once Phases 1 and 2 have run
unattended without surprises.

---

## Open decisions to revisit

- [ ] Confirm cron cadence for Phase 1 once real targets are in (30 min may
      be finer-grained than actually needed)
- [ ] Decide Phase 2's output destination (repo file vs. email vs. elsewhere)
- [ ] Decide Phase 3's repo/visibility before building it
- [ ] Periodically check LangSmith trace usage and Groq/Tavily usage against
      free-tier caps as all three agents come online together
