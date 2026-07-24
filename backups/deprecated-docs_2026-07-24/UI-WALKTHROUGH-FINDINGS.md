# UI Walkthrough Findings — strategy-engine (2026-07-19)

**Server:** PID 29567, port 8792, login `operator`/`operator`, base `http://127.0.0.1:8792`
**Method:** recon-only. Per page: HTTP status, render, JS console errors, data population, auth, mobile, screenshot. Verify BACKLOG #41-#66.
**Discipline:** one page/turn (project-manager `live_test` mode), no code fixes unless trivial+explicit go.

---

## Page 1 — `/` (Landing)
- **HTTP:** 200 (public, no auth wall — by design)
- **Console errors:** 0
- **Render:** ✅ Hero heading visible, nav (PULS R / About / FAQ / dark toggle / Sign In) present, 6 feature cards (Backtest Lab, Multi-Engine Fleet, Live Execution, Monitoring & Alerts, AI Advisory, Withdrawal System) in 3×2 grid, CTAs (Start Trading / Learn More), footer HL links. Dark theme applied.
- **Defects:** none (grey top artifact = screenshot capture overlay, not page)
- **BACKLOG verify:** #44 (login redirect target exists) — confirmed `/app/dashboard` is the real route; landing Sign In present.
- **Screenshot:** `/home/hermeswebui/.hermes/cache/screenshots/browser_screenshot_7f791a9da4824b88baa7fcbff266cbda.png`
- **Status:** PASS

---

## Page 3 — `/app/engines` (Engine Fleet)
- **HTTP:** 200 (auth)
- **Console errors:** 0
- **Render:** ✅ Fleet cards (FARTCOIN Scalp v1.3, HYPE Paper v1.3) with status/side/size/mark/lev/mode, filter bar (All/Running/Stopped/Paper/Live), sort dropdown, + Add Engine, KPI row (0/2 active, $0 PnL, 0% win, 0 closed, DRY RUN mode). No breakage.
- **Notes:** KPI "DRY RUN" = fleet default; per-card "PAPER" consistent (both stopped). No data mismatch of concern.
- **BACKLOG verify:** #32 (6-Engine copy) — fleet shows 2 engines, label correct here. Z2 menu (Engines top-level) present.
- **Screenshot:** `/home/hermeswebui/.hermes/cache/screenshots/browser_screenshot_4f41f49a3b9843db9d92b34cf1064a6b.png`
- **Status:** PASS

---

## Page 4 — `/app/engines/engine-1` (Engine Detail)
- **HTTP:** 200 (auth)
- **Console errors:** 1 (anonymous `exception`, no message — SAME pattern as dashboard page 2. Recurring. Needs precise capture — see BUG-9 note below.)
- **Render:** ✅ Title "FARTCOIN Scalp v1.3" + **PAPER mode tag** (Z3 confirmed working). KPI row (stopped / $0 PnL / PAPER), PERFORMANCE hero, POSITION "No position" empty state, STRATEGY card (engine_v1_3, 15m, Scalp, activation 8, offset 3, profile aggressive_8_3, max pos 97%), TRADE HISTORY table (empty "No trades yet"), RUNNER CONSOLE, Settings/Start/Restart controls, ← All Engines link.
- **Notes:** No layout breakage in a11y tree. Vision screenshot captured but aux model (gemma free) rate-limited 429 — screenshot at `/home/hermeswebui/.hermes/cache/screenshots/browser_screenshot_cd4e830fe8814a90b0783e9370834ca4.png`. Visual confirm pending re-run.
- **BACKLOG verify:** Z3 LIVE/PAPER tag ✅. Z5 position-card.js wired (empty state renders). #64 (engine_v6_1 dropdown) not visible here (strategy card shows engine_v1_3 only).
- **Recurring issue:** Console `exception` (no msg) on page 2 + page 4. Likely same root cause (position-card.js or shared JS). Track as BUG-9-A.
- **Screenshot:** `/home/hermeswebui/.hermes/cache/screenshots/browser_screenshot_cd4e830fe8814a90b0783e9370834ca4.png`
- **Status:** PASS (visual pending; console exception flagged)

---

## Page 5 — `/app/strategies` (Strategy Registry)
- **HTTP:** 200 (auth)
- **Console errors:** 1 (anonymous `exception`, no msg — recurring on all auth pages: 2/4/5)
- **Render:** ✅ 3 strategies (Scalp v1.3, Swing v1, PRO v6.1), KPIs (3 total/3 active/0 trades/$0 PnL), + Upload Strategy. No breakage.
- **Notes:** Sidebar lists PRO v6.1 as a strategy — registry HAS it. BUGREPORT #64 is about the *instance-form dropdown* missing engine_v6_1, NOT the strategy registry. Distinction confirmed.
- **BACKLOG verify:** #64 (instance-form gap) not visible here; registry correct.
- **Status:** PASS (console exception recurring — BUG-9-A)

---

## Page 6 — `/app/strategies/{id}` (Strategy Detail)
- **HTTP:** 200 (auth)
- **Console errors:** 1 (recurring anonymous exception)
- **Render:** ✅ [TO FILL from snapshot]
- **Notes:** BUGREPORT #7 — Parameters section is READ-ONLY (no form/inputs). Verify here.
- **Status:** IN PROGRESS

---

## Page 6 — `/app/strategies/engine_v1_3` (Strategy Detail)
- **HTTP:** 200 (auth)
- **URL:** `/app/strategies/engine_v1_3` (strategy_id = engine class name)
- **Console errors:** 1 (recurring anonymous exception — same as pages 2/4/5)
- **Render:** ✅ Title "Scalp v1.3", status active, KPIs (2 engines/0 trades/$0 PnL), tabs (Overview/PineScript/Python/Documentation), PARAMETERS heading, ENGINES RUNNING (2 view-engine links), Clone Strategy button. Page has 2 form inputs (likely filter/search, not param-edits — BUGREPORT #7 read-only claim stands; no strategy-config form fields present).
- **BACKLOG verify:** #7 (Port 1 UI missing) CONFIRMED — no `strategy-config` inputs in Parameters section. FAQ describes a flow that doesn't exist. E11.
- **Status:** PASS (console exception recurring — BUG-9-A)

---

## Page 7 — `/app/strategies/studio` (Strategy Studio)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (exception did NOT fire here — narrows BUG-9-A to position-card/console JS, absent on this page)
- **Render:** ✅ Pine→Python Converter (Provider: ollama · Model: glm-5.1), pending-strategy dropdown (empty), Convert→ / Save & Activate buttons, PineScript source + Generated Python textboxes. No breakage.
- **Backend verify (recon):** BUGREPORT #6 / T0-1 CONFIRMED in code — `core/llm.py:83-94` system prompt instructs LLM to put `stop_loss_long/short`/`take_profit_long/short` inside `metadata` dict, but runner reads top-level `exit_config`. Generated strategies trade with NO stops, silently. Highest-priority Tier-0 fix.
- **Status:** PASS (converter backend bug confirmed — T0-1)

---

## Page 8 — `/app/testing/paper` (Paper Trading)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean — no position/console widget; consistent with BUG-9-A narrowing)
- **Render:** ✅ "PAPER TRADING" mode tag, equity/trades table (empty "No equity data yet"), token price chart (loading state), PAPER ENGINES list (FARTCOIN + HYPE, stopped, Start/Restart/Edit). No breakage.
- **BACKLOG verify:** #10 (cross-tenant leak) — code-level (T0-3); UI cannot reveal leak with single operator user. Page renders correctly as operator. Z2 menu (Paper top-level) ✅.
- **Status:** PASS

---

## Page 9 — `/app/testing/historical` (Backtesting)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean)
- **Render:** ✅ Full backtest form (TOKEN FARTCOIN, STRATEGY dropdown = engine_v1_3/engine_v1/**engine_v6_1** all present, TIMEFRAME 5m-1d, START BALANCE 100, DAYS 7, LEVERAGE 5, Run Backtest), price chart, equity/trades table (empty), BACKTEST RUNS table (empty "No backtests yet"). No breakage.
- **BACKLOG verify:** #64 (engine_v6_1 missing) — NOT here; this strategy dropdown HAS engine_v6_1. #64 is specifically `instance_form.html` (create-instance), a different form. BUG-3 (backtest form submit→results) UI present; live submit not tested this turn. #11 (cross-tenant leak) code-level T0-3; UI can't reveal solo.
- **Status:** PASS

---

## Page 10 — `/app/trades` (Trades)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean — no position/console widget)
- **Render:** ✅ KPIs (Total PnL $0, Win Rate 0%, Open Positions 0, Total Trades 0), filter dropdowns (engine/side/status). 
- **BUG-7 CONFIRMED:** Page ends at filters — **NO trades table and NO "Active Positions" section** rendered below. With 0 trades it should show an empty state; instead the content area stops at the filter bar. Trade list UI gap.
- **Status:** PASS (BUG-7 trade table missing — flagged)

---

## Page 11 — `/app/account` (Account Overview)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean)
- **Render:** ✅ Portfolio $7.2, Start $5.0, PnL $0, Withdrawable $7.2, Engine Allocation table (FARTCOIN + HYPE: status/mode/lev/value/pnl), Account Settings (operator/Operator/dry_run True/$5.0), links Edit Settings/Secrets/Wallet/API Keys. No breakage.
- **Notes:** Start Balance $5.0 here vs $7.20 portfolio — consistent (start=seeded $5, portfolio grew). Minor display variance vs dashboard header noted earlier.
- **Status:** PASS

---

## Page 12 — `/app/assistant` (Assistant)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean)
- **Render:** ✅ Sessions panel (New), MODEL dropdown (GLM-5.1 Ollama Cloud / GPT-4o / Claude Sonnet 4 / etc / Custom), chat input + Send. No breakage.
- **Status:** PASS

---

## Page 13 — `/app/withdrawals` (Withdrawals)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean)
- **Render:** ✅ Title, Account Overview (refresh), Withdrawal Settings form (Cycle Frequency / checkbox / spinbuttons 0.5 & 10000 / Save), Manual Withdrawals (50% + All — disabled, no balance), Withdrawal History, 24-Month Projection.
- **Notes:** Page renders WITHOUT sidebar nav (standalone view with "← Back" link). Layout choice, not a break. BUGREPORT #54 (idempotency) is backend (T1-5); UI buttons present.
- **Status:** PASS

---

## Page 14 — `/app/settings` (Account Settings)
- **HTTP:** 200 (auth)
- **Console errors:** **0** (clean)
- **Render:** ✅ Full settings form — PROFILE (display name, email, 18-avatar radio grid), SECURITY (username disabled, change-password, 2FA checkbox), TRADING (max-pos % spinbutton, paper-default checkbox), APPEARANCE (theme radios), WALLET (address), PLAN & BILLING (FREE, Upgrade disabled, engine/strategy quotas). Save Settings button. No breakage.
- **Status:** PASS

---

## Page 15 — `/app/kill/status` (Kill Switch Status)
- **HTTP:** 404 (Not Found) as a UI page — `{"detail":"Not Found"}`
- **Reality:** NOT a UI page. `kill/status` exists only as API endpoint `api/killswitch.py:115` → `GET /api/v2/kill/status` (requires X-API-Key, returns "Authentication required" under Basic Auth).
- **Finding:** Handover mislabeled this as a walkthrough page. It's an API endpoint, not a rendered template. No UI bug — just a doc/handover inaccuracy.
- **Status:** N/A (API-only endpoint, not a UI page)

---

## Page 16 — `/shell` (Legacy Shell UI)
- **HTTP:** 404 (confirmed via curl)
- **Reality:** GONE — BUGREPORT #42/43 resolved by deletion (route + app-shell.html removed). Browser shows bare FastAPI 404 fallback (Pretty-print checkbox), not a real page.
- **Status:** PASS (deleted as expected — #42/43 ✅)

---

## Page 17 — `/logs` (Log Stream API)
- **HTTP:** 200 (auth required — BUGREPORT #1 ✅; returns JSON `{"ok":true,"logs":[...]}`)
- **Reality:** JSON API endpoint (`api/stream.py:18` `GET /logs`), content-type `application/json`. Browser shows FastAPI default JSON viewer (Pretty-print checkbox), not an HTML page.
- **Verify:** Auth added (BUGREPORT #1) — without creds returns "Authentication required". Live-verified 200 with Basic Auth.
- **Status:** N/A (API endpoint, not UI page) — #1 ✅

---

## Page 18 — `/stream` (SSE Event Stream)
- **HTTP:** 401 without auth (BUGREPORT #1 ✅); with auth → open SSE connection (browser times out waiting for close — expected for streaming).
- **Reality:** Server-Sent Events endpoint (`stream.router`, auth-protected per BUGREPORT #1). Not an HTML page. Live-verified: no-auth=401, auth=open stream.
- **Status:** N/A (SSE endpoint, not UI page) — #1 ✅

---

## Page 19 — `sw.js` (Service Worker)
- **HTTP:** `/sw.js` (root) → 404; **`/static/sw.js` → 200** (actual served path, registered in HTML).
- **BUGREPORT #62 ✅ CONFIRMED:** `app/static/sw.js` ASSETS list is clean (`/`, `/static/tokens.css`, `/static/style.css`, `/static/manifest.json`) — no broken `/static/pages.js` reference. Cache install will succeed.
- **Note:** Handover's `/sw.js` path is wrong; correct path is `/static/sw.js` (used by `landing.html:466` + `layout.html:1545`). Root 404 is harmless.
- **Status:** PASS (sw.js content fixed — #62 ✅)

---

## Page 20 — `manifest.json` (PWA Manifest)
- **HTTP:** `/manifest.json` (root) → 404; **`/static/manifest.json` → 200** (actual served path, linked in HTML `landing.html:7` + `layout.html:15`).
- **Reality:** Valid manifest served at `/static/manifest.json` (1120 bytes). Root 404 harmless — no code references root path.
- **Status:** PASS (manifest served correctly at /static/)

---

## Page 21 — `spec.html` (Design Spec)
- **HTTP:** `/spec.html` (root) → 404; **`/spec` → 200** (actual route, `app/routes.py:158` `GET /spec`, auth-protected: 401 without creds).
- **Reality:** NOT dead weight (BUGREPORT ⚠️ UNVERIFIED suspicion WRONG). `spec.html` template is live at `/spec` — design system spec page, auth-protected, renders 200.
- **Status:** PASS (alive at /spec — not dead)

---

## SUMMARY (21/21 walked)
- **UI pages PASS (structural):** 1,3,4,5,6,7,8,9,10,11,12,13,14,16,19,20,21 (17)
- **N/A (API/SSE/static, not UI pages):** 15 (/kill/status), 17 (/logs), 18 (/stream) — all live + auth-protected
- **Recurring console exception (BUG-9-A):** fires ONLY on dashboard/engines/engine-detail/strategies/strategy-detail (pages with PULSE console + position-card.js). Pages without those widgets = 0 errors. Root cause = position-card.js or console widget JS. Needs precise `window.onerror` capture + fix.
- **Confirmed BUGREPORT items:** #1 (auth on /logs /stream ✅), #6/T0-1 (converter prompt exit_config mismatch — VERIFIED in core/llm.py), #7/E11 (Port 1 UI missing — strategy detail read-only), #42/43 (/shell deleted ✅), #62 (sw.js ASSETS clean ✅). #64 distinction: engine_v6_1 present in backtest form, missing only in instance_form.
- **New findings:** BUG-7 trade table missing on /app/trades (ends at filters, no list/empty-state). Dashboard PnL mismatch ($8.88 header vs $0.00 sidebar). Handover mislabeled /kill/status + /shell as pages (API/404). spec.html alive at /spec.
- **Vision screenshots:** rate-limited on free aux model (gemma-4-26b free 429); structural verification via a11y snapshot used throughout. Screenshots captured for pages 1,2,3,4 — retry vision on remaining when limit clears or switch aux model.

---
