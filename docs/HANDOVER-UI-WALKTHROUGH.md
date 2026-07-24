# HANDOVER — UI Browser Walkthrough Session

**Prepared:** 2026-07-19 (Asia/Makassar)
**Project:** strategy-engine (PULS-R multi-engine crypto trading system)
**Repo:** `/workspace/projects/strategy-engine/main` (git root is `main/`, NOT the parent `strategy-engine/`)
**Goal of this session:** Click through EVERY UI page in a real browser, screenshot, and report what actually renders vs. what's broken. No code fixes unless a bug is trivial and obvious — primary deliverable is a FINDINGS REPORT.

---

## 1. Server State (read-first)

| Item | Value |
|------|-------|
| Server PID | 29567 (alive) |
| Port | 8792 |
| Launch cwd | `/workspace/projects/strategy-engine/main` |
| Launch cmd | `/workspace/projects/strategy-engine/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8792` |
| UI login | user `operator` / pass `operator` (from `.env`) |
| DB | `main/data/dev_test.db` (engine-1 seeded, stopped, no open position) |
| Git branch | `main` (tracks `origin/main`); `master` = identical backup; tag `archive/pre-restructure` = old history |
| Last commit | `e7709b1` |

**If server is down:** restart from `main/` dir:
```bash
cd /workspace/projects/strategy-engine/main
/workspace/projects/strategy-engine/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8792
```
Verify: `curl -s -m 5 -u operator:operator -o /dev/null -w "%{http_code}" http://127.0.0.1:8792/app/dashboard` → expect `200`.

---

## 2. How to browse

Use the `browser_*` tools (browser_navigate → browser_snapshot → browser_vision for screenshots).
- Base URL: `http://127.0.0.1:8792`
- Login: navigate to `/` or `/app/dashboard`, Basic Auth prompt → `operator` / `operator`.
- For API-driven pages, the page calls `window.API_KEY` (set by `withdrawals.html`). Other pages use Basic Auth only.

---

## 3. Pages to walk (every one — do not skip)

### Primary flows
1. **`/`** — landing page. Does it render? Login flow? (BUG #59: auth broken reported)
2. **`/app/dashboard`** — main dashboard. Position cards, PulseGraph, engine list.
3. **`/app/live`** — LIVE view (alias of dashboard? check)
4. **`/app/paper`** — Paper Trading page (top-level menu, dry_run=True)
5. **`/app/engines`** — engine list
6. **`/app/engines/engine-1`** — engine detail (mode tag LIVE/PAPER, strategy params, position card)
7. **`/app/trades`** — trades table
8. **`/app/strategies`** — strategy list
9. **`/app/strategies/studio`** — strategy studio
10. **`/app/testing/paper`** — paper testing runner
11. **`/app/testing/historical`** — backtest form (submit a backtest, confirm results render) (BUG #62/#63: sw.js)
12. **`/app/withdrawals`** — withdrawals page (API works w/ key; does UI render tables?)
13. **`/app/settings`** — settings
14. **`/app/account`**, **`/app/account/secrets`**, **`/app/account/settings`**
15. **`/app/assistant`** — chat widget (needs AI_API_KEY or shows disabled)
16. **`/app/alerts`** — alerts page
17. **`/instances/new`** — instance creation form (BUG #64: missing engine_v6_1; #65: presets unwired)
18. **`/logs`** — log stream (auth required, verified 401/200)
19. **`/kill/status`** — kill-switch status page

### PWA / shell
20. **`/shell`** — the alternate dashboard (BUG #42/#43: competes with dashboard.html — is it broken? unfinished? decide later)
21. Check `sw.js` registration — does it reference `/static/pages.js` that doesn't exist? (BUG #62) Does it cache-first `/`? (BUG #63)

---

## 4. What to CHECK on each page

For every page, record:
- **HTTP status** (200? 404? 500? redirect loop?)
- **Renders correctly?** (layout, no broken CSS, no raw `{{ }}` Jinja leftovers)
- **JS errors** — use `browser_console` to capture console errors / uncaught exceptions
- **Data populates?** (does the table/card show real data or empty/loading-forever?)
- **Auth** — does it require login? does it incorrectly show login when already authed? (BUG #59)
- **Mobile** — narrow viewport, does layout break? (UX backlog)
- **Screenshot** — `browser_vision` with a specific question per page

---

## 5. Known bugs to verify (from BACKLOG.md)

| # | Reported | What to look for |
|---|----------|------------------|
| 41 | No kill-switch UI button | Is there a STOP ALL in the topbar? (Probably not — confirm) |
| 42/43 | Two dashboards (/shell vs dashboard.html) | Which is real? Is /shell broken? |
| 44 | /dashboard 404 after login | Does `/dashboard` (no /app/) 404? (route may be `/app/dashboard`) |
| 59 | landing.html auth broken | Does `/` redirect correctly or loop? |
| 60 | sessionStorage dead code | Minor — note if seen in console |
| 61 | fake wallet-connect CTAs | Are there fake "Connect Wallet" buttons with no function? |
| 62 | sw.js dead /static/pages.js | Open DevTools → Network/Console; does sw.js 404 on pages.js? |
| 63 | sw.js cache-first on / | After deploy, does old shell show? (hard to test live; note config) |
| 64 | instance_form missing engine_v6_1 | On /instances/new, is engine_v6_1 in the strategy dropdown? |
| 65 | instance_form.js presets unwired | Are the preset buttons dead? |
| 66 | spec.html dead weight | Is /spec or spec.html linked anywhere? (move out if not) |

---

## 6. Discipline (operator-mandated)

- **Pulse first** every turn (`self-pulse.sh`).
- **One page at a time.** Screenshot, console-check, note findings, move to next.
- **Do NOT fix code** unless operator explicitly says "fix it" — this session is RECON (reconnaissance).
- **Backup before any edit** if you do fix (ADIX tar.gz).
- **Report findings** as a structured list: page → status → issue → screenshot ref.
- **No secrets** in screenshots or notes (cookies.txt, .env already gitignored).
- At end: write a FINDINGS report to `docs/UI-WALKTHROUGH-FINDINGS.md` (or append to BACKLOG.md §Report 3 status).

---

## 7. Deliverable

A findings report with:
- Per-page: status (OK / BROKEN / PARTIAL) + screenshot + console errors
- Which BACKLOG bugs are CONFIRMED vs STALE (already fixed but report didn't know)
- New bugs found during walkthrough
- Recommended fix order (cheap wins first)

Commit the findings to `main` when done (docs only, no code).

---

## 8. Quick reference

- Docs contract: `main/docs/` (ARCHITECTURE, VOCABULARY, DECISIONS, REFACTOR_PLAN, TASK-LIST, ROADMAP)
- Bug ledger: `main/BACKLOG.md`
- Operator working docs: `main/CONTEXT.md`, `main/NOTES.md`
- Design authority: `main/design-system/MASTER.md` (palette: profit #34D399, loss #FB7185, surface #15100B)
- 3-way separation: LIVE (dry_run=False) / PAPER (dry_run=True) / BACKTEST (isolated store)
