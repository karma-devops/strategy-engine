# DECISIONS (ADRs)

Architecture Decision Records. Each entry: date, decision, context, consequences.

---

## ADR-001 — Server-rendered Jinja2, no SPA
**Date:** 2026-07-13
**Decision:** UI is server-rendered Jinja2 templates with data injected in Python;
charts via LightweightCharts v5. No SPA, no Node build step.
**Context:** Zero-column backtest bug risk from client-rendered tables; operator
wanted premium polish without a JS framework.
**Consequences:** Simpler deploy (single uvicorn process). No client bundle.
Dashboard HTML is the working UI; `/shell` + `app-shell.html` is an unfinished
redesign (see BACKLOG #42/#43 — decision pending).

## ADR-002 — 3-way strict separation (Live / Paper / Backtest)
**Date:** 2026-07-18
**Decision:** LIVE uses `dry_run=False` only; PAPER is a top-level menu with
`dry_run=True`; BACKTEST uses an isolated `data/backtest.db` with zero live/paper
data access.
**Context:** Theoretical tools (backtest) must never bleed into live dashboard or
engine stats.
**Consequences:** Paper + Backtesting are top-level nav siblings; "Testing"
collapsible removed.

## ADR-003 — MASTER.md is palette authority
**Date:** 2026-07-18
**Decision:** `design-system/MASTER.md` wins over `CONTEXT.md §6` and `tokens.css`.
Downstream files reconcile to it.
**Context:** 3-way palette drift (#34D399 / #FB7185 / #15100B vs #10b981 / #ef4444).
**Consequences:** HL position-card pattern (left-edge spine, long=teal, short=red)
adopted for dashboard cards.

## ADR-004 — Worker stays standalone
**Date:** 2026-07-18
**Decision:** `scripts/worker.py` (port 9999) remains a standalone MVP tester,
NOT merged into the main app.
**Context:** Operator directive — keep testing wrapper isolated.
**Consequences:** Main app (port 8792) and worker (9999) are independent processes.

## ADR-005 — CONTEXT.md / NOTES.md at repo root
**Date:** 2026-07-18
**Decision:** `CONTEXT.md` and `NOTES.md` stay at repo root (not in `docs/`) so the
operator can navigate them directly. `TASK-LIST.md` lives in `docs/`.
**Context:** Operator working-style override of the contract's `/docs/` layout.
**Consequences:** `docs/README.md` points to root CONTEXT/NOTES.

## ADR-006 — Seed engine-1 only on fresh accounts
**Date:** 2026-07-18
**Decision:** No default fleet. Seed `engine-1` only. UI copy "6-Engine Default
Fleet" is inaccurate and will be corrected (BACKLOG #32).
**Context:** Operator: "we do not need any engines default on new account, just
seed for us engine 1."
**Consequences:** `DEFAULT_FLEET` docstring + UI labels to be fixed.

## ADR-007 — ADIX backup-before-write
**Date:** 2026-07-18
**Decision:** Every doc/code edit is preceded by an ADIX STABLE tar.gz backup
(excludes venv/pyc/db/.env). One file per turn; verify after every write.
**Context:** Karpathy + backup-versioning discipline; operator "careful execution."
**Consequences:** 100+ versioned backups in `backups/`. `cookies.txt`, `.env`,
`*.db` gitignored.
