# Paper Trading Page Upgrade — Full Plan

**Author:** Aetheris · **Date:** 2026-07-16 · **Session:** e3f7461df4ce
**Source skill:** ui-ux-pro-max + trading-dashboard-patterns + backup-versioning
**Operator choice:** Option C — keep what works, improve what is broken

---

## Context — Why this work matters

The paper trading page (`/app/testing/paper`) is currently **display-only**. The operator's report: "I cannot edit the strategy or run it." The fleet cards have `cursor:pointer` styling but no `onclick`. There are no action buttons (Start/Stop/Close/Restart/⚙). No sparkline. No SSE console. No live refresh. The page is a decoration, not a working panel.

Same pattern broken on `live_paper.html` and `account.html` (deferred to next session).

This plan upgrades paper trading to a **fully functional operator panel** with the 3-part structure below.

---

## Part 1 — Functional Core (~45 min)

Make the page actually work. Every change is a discrete phase with backup, edit, verify, commit.

| Phase | Change | Files | Backup slug | Verify |
|---|---|---|---|---|
| 1.1 | Clickable fleet cards + sparkline container | `app/templates/testing_paper.html` | `v104_pt1-fleet-clickable-sparks_2026-07-16_1440` | curl 200 + DOM has onclick + `#spark-{slug}` |
| 1.2 | Per-engine action buttons (Start/Stop/Close/Restart/⚙) | `app/templates/testing_paper.html` | `v105_pt1-engine-action-buttons_2026-07-16_1450` | DOM shows 4 buttons per fleet card + curl 200 |
| 1.3 | Bump buttons to 36px desktop / 44px mobile via token | `app/templates/testing_paper.html` | `v106_pt1-touch-targets-44px_2026-07-16_1500` | Computed height = 36px (mobile 44px) |
| 1.4 | Add aria-labels to all icon-only buttons | `app/templates/testing_paper.html` | `v107_pt1-aria-labels_2026-07-16_1510` | DOM: every button has aria-label |
| 1.5 | Live API refresh loop (3s poll) | `app/templates/testing_paper.html` | `v108_pt1-live-refresh_2026-07-16_1520` | Network shows fetch /api/v2/summary every 3s |
| 1.6 | SSE runner console | `app/templates/testing_paper.html` | `v109_pt1-sse-console_2026-07-16_1530` | DOM has `.console-log` + SSE dot turns green |
| 1.7 | Fix PnL color: --color-profit/--color-loss (was brand teal) | `app/templates/testing_paper.html` | `v110_pt1-pnl-color-fix_2026-07-16_1540` | Computed color: positive=emerald, negative=coral |

### Per-phase AEE cycle

1. **THINK** — what change, what slug
2. **PLAN** — read file, identify exact lines
3. **BACKUP** — `tar czf backups/v{N}_...tar.gz --exclude=... app/templates/testing_paper.html` + update `backups/VERSIONING.md`
4. **EXECUTE ONE** — single `patch` (find/replace, unique context)
5. **VERIFY** — `wc -l` + `git diff --stat` + live `curl -o /dev/null -w '%{http_code}'` + DOM inspection via `browser_console`
6. **DOUBLE CHECK** — load page, check for regressions, edge cases
7. **COMMIT** — `git commit -m "feat(pt1.N): <description>"`

After all 7 phases done: live end-to-end test, then a final wrap-up commit if needed.

---

## Part 2 — UX Polish (~1.5h)

Skill-driven improvements to the now-functional panel. **Defer until Part 1 ships clean.**

| Phase | Change | Skill rule |
|---|---|---|
| 2.1 | Inline error UI for save failures (red text below field) | `error-clarity`, `error-placement` |
| 2.2 | Loading state on Save buttons (disable + "Saving...") | `loading-buttons` |
| 2.3 | "Run Backtest" primary CTA in page header | `primary-action` |
| 2.4 | Inline validation on inputs (validate on blur) | `inline-validation` |
| 2.5 | Primary action = "Run Backtest" (teal CTA), secondary = "Add Paper Engine" (outline) | `primary-action`, `destructive-emphasis` |
| 2.6 | Loading skeleton for chart while data loads | `loading-states`, `skeleton-screen` |
| 2.7 | Empty state for "No trades yet" with "Start a paper engine →" CTA | `empty-states` |

---

## Part 3 — Empty States & Guidance (~45 min)

Helpful, not just decorative. **Defer until Part 2 ships.**

| Phase | Change | Skill rule |
|---|---|---|
| 3.1 | Empty state for "No paper engines" with inline Add button + brief explainer | `empty-states` |
| 3.2 | Tooltips on KPI cards (what each metric means) | `info-tip` pattern from design system |
| 3.3 | "How paper trading works" expandable section | `progressive-disclosure` |
| 3.4 | Keyboard shortcut hints ("R" refresh, "T" toggle mode) — discoverable, not hidden | `keyboard-shortcuts` |
| 3.5 | ARIA live region for save feedback | `aria-live-errors` |

---

## What's NOT in this plan (deferred / out of scope)

- **No new backend endpoints** — per operator's "no new features" rule. All buttons use existing `/api/v2/*` routes.
- **No "Promote to Live" button** — would need new state transition logic + UI flow. Defer.
- **No "Compare to Live" toggle** — would need parallel fetch + side-by-side render. Defer.
- **No new design tokens** — reuse existing `--color-profit`, `--color-loss`, `--surface-card`, etc.
- **No layout overhaul (bento / 2fr/1fr)** — that's a separate DS14-DS16 phase. This plan only makes paper trading functionally equivalent to engines.html, no new layout pattern.
- **No mobile-specific redesign** — the skill's mobile-first rule applies broadly. The 44px touch targets in Part 1.3 cover the most critical mobile case; full mobile redesign is a separate concern.
- **Same fix on `live_paper.html` and `account.html`** — operator said paper trading first; if this works, replicate later.

---

## Backup procedure (backup-versioning skill compliant)

Per phase, before any edit:

```bash
mkdir -p backups
tar czf backups/v{N}_{slug}_2026-07-16_{HHMM}.tar.gz \
  --exclude=backups \
  --exclude=venv \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  --exclude='data/*.db' \
  --exclude='data/*.db-wal' \
  --exclude='data/*.db-shm' \
  --exclude='.env' \
  app/templates/testing_paper.html
stat -c'%n: %s bytes' backups/v{N}_*.tar.gz
```

After tar success, append to `backups/VERSIONING.md` (one section per phase). **Only mark STABLE after live verification confirms the change works.**

---

## Rollback

If any phase breaks the page, restore from the previous phase's STABLE tar:

```bash
tar xzf backups/v{N-1}_STABLE_2026-07-16_HHMM.tar.gz -C /tmp/
cp /tmp/app/templates/testing_paper.html app/templates/testing_paper.html
```

Then re-debug from the last known-good state.

---

## Success criteria — Part 1 is "done" when

1. Operator can click a paper engine card → navigates to its detail page
2. Operator can click ▶ Start → engine actually starts, status updates within 3s
3. Operator can click ⏹ Stop → engine stops, status updates
4. Operator can click ⚙ Edit Settings → modal opens
5. Every button has a visible label or aria-label
6. Every button meets 44px touch target on mobile
7. PnL on a closed position renders emerald (positive) or coral (negative)
8. SSE console streams live log messages
9. All tests pass: `pytest tests/ -v` (if tests exist for this path)
10. No regression: dashboard, engines page, settings, assistant still work
