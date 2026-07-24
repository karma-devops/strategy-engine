# Sprint Plan v2 — PULS-R Functional Design Overhaul

**Author:** Aetheris · **Date:** 2026-07-16 · **Session:** e3f7461df4ce
**Scope:** DS5 → DS21 (full sprint) rebuilt around operator's 5 new requirements
**Estimated effort:** ~10.5 hours of focused work (1-2 phases per turn, 1-2 sessions per day)

---

## 0. Design Principles (Locked from Operator)

1. **Functional design first** — every UI element must serve a user need. No decorative elements without purpose.
2. **Most relevant info above the fold** — first viewport (1280×800 desktop, 375×812 mobile) shows the primary action + key state for the current page task.
3. **Bento-style cards** — varied card sizes (1×, 2×, 3×, 4×) in a single grid, organizing information by importance and size.
4. **Better legibility** — minimum `--text-sm` (12px) for body, 1.5 line-height, ample whitespace, no inline font-size overrides.
5. **Good contrast everywhere** — WCAG AA minimum: 4.5:1 body text, 3:1 large text (18px+ or 14px+bold), 3:1 UI components. Both light AND dark modes must pass.

---

## 1. Sprint Phases (15 phases, grouped into 4 pillars)

### 🟢 PILLAR A — Design System Foundation (DS5-DS9, ~2 hours)

Fix the token system so all rendering is consistent and AA-compliant.

| Phase | Action | Verify | Time |
|---|---|---|---|
| **DS5** | Fix `.chart-card` rule in layout.html line 210-215: replace `var(--glass-bg)`/`var(--glass-border)` with proper token names. Add `--card-shadow` to make cards feel elevated. | Browser: dashboard cards visible with bg+border. Light + dark. | 10 min |
| **DS6** | Audit ALL color combos against WCAG AA. Specifically check: text-muted on surface-card (--text-3 #8A7A64 on #15100B). If fails, bump --text-3 to lighter brown or use --text-2 instead. | Compute contrast ratios, document. Both modes. | 20 min |
| **DS7** | Add missing tokens: `--card-shadow`, `--shadow-color`, proper teal palette. Resolve any other undefined token refs (--chart-grid, --chart-axis, etc.). | grep for undefined vars = 0. | 15 min |
| **DS8** | Fix h2 font-size override. Root cause: probably `.empty` class or media query shrinks h2 to 9.75px. Trace + fix. | Browser: chart-card h2 renders 12px (--text-sm) on desktop, 14px on mobile. | 20 min |
| **DS9** | Standardize type scale usage: every text element uses --text-* token, no inline `font-size:11px` etc. | grep for `font-size:` in templates = only in tokens.css and a few intentional spots. | 30 min |

### 🔵 PILLAR B — Functional Information Architecture (DS10-DS13, ~3 hours)

Restructure each page so the most-actionable info is first. Above the fold = primary action + key state.

| Phase | Action | Verify | Time |
|---|---|---|---|
| **DS10** | **Dashboard** restructure: above-the-fold = 3 KPI cards (Account Value hero) + Pulse Graph (live) + Fleet status grid (3 cards). Below = Active Live Trades + Agent Console. **Bento layout: Account Value = 2× wide, Realized PnL = 1×, Best Engine = 1×, Pulse = 2× wide, Fleet = 1× each.** | Browser + DOM: above-fold contains all 3 KPIs and at least 1 fleet card. | 1h |
| **DS11** | **Engines page** restructure: above-fold = 5 KPI metrics (Active, Open PnL, Win Rate, Closed, Mode) + first 2 engine cards. Below = remaining engines + charts. **Bento: each engine card = 1× wide.** | Browser: 5 KPIs + 2 engine cards visible without scroll. | 45 min |
| **DS12** | **Engine Detail** restructure: above-fold = Status + Position + Settings button + Recent Performance sparkline. Below = Trade History + Signals. **Bento: status = 1×, position = 1×, performance = 2× wide.** | Browser: status, position, performance visible above fold. | 45 min |
| **DS13** | **Trades + Strategies + Testing/Historical** restructure similarly. Each page: above-fold = the page's primary action (filter trades / browse strategies / run backtest). | Each page's primary action reachable in 1 click from above-fold. | 30 min |

### 🟣 PILLAR C — Bento-Style Card Architecture (DS14-DS16, ~3 hours)

Replace uniform `.chart-card` with a proper bento grid system. Cards sized by importance.

| Phase | Action | Verify | Time |
|---|---|---|---|
| **DS14** | Define bento grid system in tokens.css: `--bento-grid-gap`, `--bento-cell-1x`, `--bento-cell-2x`, `--bento-cell-3x`, `--bento-cell-4x`. Add to layout.html CSS. Define `.bento-grid`, `.bento-{1x,2x,3x,4x}` classes. | Browser: dashboard renders with varied card sizes. | 1h |
| **DS15** | Apply bento to **Dashboard** specifically. Rewrite the kpi-grid + chart-card structure as a bento layout. Account Value gets 2× wide, Realized PnL 1×, Best Engine 1×, Pulse 2×, Fleet cards each 1×, Active Trades 2×, Console 2×. | Visual: dashboard looks like a bento grid, not a uniform stack. | 1.5h |
| **DS16** | Apply bento to **Engine Detail** (most card-dense page). Performance hero = 4× wide full bleed, Status/Position/Strategy cards = 1× each in row, Trade History = 3× wide, Signals = 1× wide. | Visual + DOM: each card has correct grid span. | 30 min |

### 🔴 PILLAR D — Security & Data Integrity (DS17-DS21, ~2 hours)

Fix the security bugs so the design actually protects what it displays. This is "function follows design" — the data has to be secure for the UI to mean anything.

| Phase | Action | Verify | Time |
|---|---|---|---|
| **DS17** | **CRITICAL: Password hashing.** Replace `hashlib.sha256` with `bcrypt` in `app/routes.py:891`. Install `bcrypt` via pip. Migration: keep old SHA256 hashes working until user re-logs in. | All existing users can still log in. New passwords use bcrypt. | 30 min |
| **DS18** | **CRITICAL: Whitelist allowed fields in `update_instance`** (`api/instances.py:318`). Replace `hasattr(inst, key)` with explicit whitelist. | Operator cannot write to `user_id`/`api_key`/etc via PUT. | 20 min |
| **DS19** | Add validation: leverage (1-50), max_position_pct (0-1.0), token (must be in HL universe). | Invalid values rejected with 400. | 30 min |
| **DS20** | Fix `saveSettings()` JS: add min/max validation, dry-run-stop-first guard, disable-during-save state. | UI prevents bad saves + warns on dry_run change. | 30 min |
| **DS21** | Add success banner to `settings.html` for `{saved: True}`. Add aria-labels to 16 avatar emojis. Fix $0.0 → $0.00 number format drift. Remove legacy 301 redirects. | All UX feedback + a11y clean. | 30 min |

---

## 2. Execution Order (dependencies respected)

1. **Pillar A (DS5-DS9) MUST come first** — without the foundation, bento redesign would re-introduce bugs.
2. **Pillar B (DS10-DS13) follows A** — needs the design system stable to restructure.
3. **Pillar C (DS14-DS16) follows B** — builds bento infrastructure, then applies it.
4. **Pillar D (DS17-DS21) is parallel** — security is independent of visual, can run at any time.

**Suggested session ordering:**

| Session | Phases | Work | Time |
|---|---|---|---|
| 1 (today) | DS5 + DS6 + DS7 | Foundation fixes | ~45 min |
| 2 | DS8 + DS9 | Legibility + type scale | ~50 min |
| 3 | DS10 + DS11 | Dashboard + Engines restructure | ~1h 45m |
| 4 | DS12 + DS13 | Engine Detail + other pages | ~1h 15m |
| 5 | DS14 + DS15 | Bento grid + dashboard apply | ~2h 30m |
| 6 | DS16 | Engine detail bento | ~30 min |
| 7 | DS17 + DS18 + DS19 | Security | ~1h 20m |
| 8 | DS20 + DS21 | JS validation + a11y | ~1h |

Compressed: 1-2 phases per turn, 2-3 turns per day, full sprint done in ~3-4 days.

---

## 3. What I'm NOT Doing in This Sprint

- **Not redesigning the entire visual identity** — colors, fonts, brand stay the same.
- **Not touching the runner / trading engine logic** — this is UI + security only.
- **Not adding new features** — bug fixes, restructure, and security only. No new endpoints, no new pages.
- **Not implementing 2FA** — the field exists but the implementation is out of scope. Removed in DS21.

---

## 4. Success Criteria

**The sprint is "done" when ALL of these are true:**

1. **WCAG AA contrast passes** for ALL text on every page, in BOTH light and dark modes. Verified by computed-style audit.
2. **Above-the-fold rule:** on every page, the primary action + key state are visible without scroll at 1280×800 desktop. Verified by manual scroll + DOM inspection.
3. **Bento grid** on Dashboard and Engine Detail (the 2 most-trafficked pages). Each card has a clear `bento-Nx` class.
4. **No critical security bugs** — password hash upgraded, PUT whitelisted, validation in place.
5. **All template inline styles replaced with tokens** — `grep font-size:` and `grep height:` in templates return only token-driven styles.
6. **Git history** — 15-17 commits, one per phase, each with a `wc -l` and `git diff --stat` verify.

---

## 5. Backup Strategy

Before each phase, snapshot the affected files. Per AEE protocol.

```
backups/v102_ds5-chart-card-fix_2026-07-16_1400/snapshot.tar.gz
backups/v103_ds6-contrast-audit_2026-07-16_1410/snapshot.tar.gz
...
backups/v116_ds21-ux-cleanup_2026-07-16_1800/snapshot.tar.gz
```

**One backup per phase.** If something breaks, restore from the last good backup.

---

## 6. Open Questions for Operator (awaiting approval)

1. **Pillar A — token name change:** I'll rename `--glass-bg` → `--card-bg` in CSS, keep the old name as a shim alias (DS1 pattern). Confirm?
2. **Pillar B — Dashboard restructure:** I'll keep all current data, just reorder. The bento layout means the Pulse Graph will be 2× wide (taller too) to make the equity curve more prominent. Confirm?
3. **Pillar C — bento size assignments:** I sized cards by "what's the most important info to see first" — Account Value is the primary KPI, so it gets 2×. Confirm sizing is right?
4. **Pillar D — bcrypt migration:** I'll install bcrypt via pip. Old SHA256 hashes will still work (with a `legacy_` prefix check) until user re-logs in. New passwords use bcrypt. Confirm?
5. **Scope guard — no new features:** Per AEE protocol, I will NOT add any new endpoints, pages, or features in this sprint. Pure fix + restructure. Confirm?
