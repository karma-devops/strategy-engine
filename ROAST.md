# Fund Manager — Coder Roast Sheet

**Version:** 1.0  
**Date:** 2026-07-11  
**Purpose:** Find the holes before production does.  
**Audience:** Development team. Read this before writing code.

---

## 🔥 HOW TO USE THIS

| Step | Action |
|------|--------|
| **1. Read all sections** | Don't skip. Don't assume. |
| **2. Flag what's already done** | Mark ✅ next to covered items. |
| **3. Flag what needs work** | Mark ❌ next to gaps. |
| **4. Assign ownership** | Who fixes what? By when? |
| **5. Document decisions** | Write the "why" not just the "what." |

---

## 🚨 SECTION 1: CRITICAL VULNS (Fix Before Any Live Capital)

### 1.1 Fernet Key = Single Point of Failure

| Field | Value |
|-------|-------|
| **Severity** | 🔴 Critical |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
If someone gets your DB backup + env var, they have every API key. Key rotation is "manual" with no documented procedure.

**What Needs To Happen:**
- [ ] Document the actual rotation steps (line-by-line)
- [ ] Write a re-encryption script that runs without downtime
- [ ] Define who has access to the master key
- [ ] Define where the master key lives (env var? vault? secrets manager?)
- [ ] Define what happens during rotation (downtime? transparent?)

**Acceptance Criteria:**
- Rotation can be done in < 30 minutes
- No trading interruption during rotation
- Old keys are securely destroyed after rotation

---

### 1.2 No Rate Limiting On API Endpoints

| Field | Value |
|-------|-------|
| **Severity** | 🔴 Critical |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
`/api/v2/instances/{slug}/start` can be hammered. DDoS your own bot. Exhaust HL rate limits. Get banned.

**What Needs To Happen:**
- [ ] Add rate limiting middleware (e.g., `slowapi` or custom)
- [ ] Define limits per endpoint type:
  - Read endpoints: 100 req/min
  - Write endpoints: 20 req/min
  - Auth endpoints: 5 req/min
- [ ] Return `429 Too Many Requests` with retry-after header
- [ ] Log rate limit violations for security audit

**Acceptance Criteria:**
- Rate limits enforced at API gateway layer
- Legitimate traffic not impacted
- Attack traffic gracefully rejected

---

### 1.3 Kill Switch Behavior Undefined

| Field | Value |
|-------|-------|
| **Severity** | 🔴 Critical |
| **Effort** | Medium |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
Is the kill switch at API layer? Engine layer? Both? What if engine is mid-trade when kill is pressed? Does it cancel open positions or just stop new signals?

**What Needs To Happen:**
- [ ] Define kill switch levels:
  - **Global:** Stops all engines, cancels all open orders
  - **Per-engine:** Stops one engine, cancels its open orders
  - **Withdrawal:** Blocks all withdrawal execution
- [ ] Define behavior on activation:
  - Cancel open orders? Yes/No
  - Close open positions? Yes/No (default: No, just stop new signals)
  - Persist kill state across restarts? Yes
- [ ] Define who can activate (roles)
- [ ] Define how kill state is stored (DB table, encrypted?)

**Acceptance Criteria:**
- Kill switch activates in < 5 seconds
- Kill state persists across restarts
- Manual reset required to resume trading

---

### 1.4 No Position Limits Defined

| Field | Value |
|-------|-------|
| **Severity** | 🔴 Critical |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
What prevents engine-3 from going 100% portfolio on a shitcoin? Max position per engine? Per portfolio? Stop loss enforcement?

**What Needs To Happen:**
- [ ] Define max position per engine (% of portfolio)
- [ ] Define max position per asset (across all engines)
- [ ] Define max total portfolio exposure (% in trades vs cash)
- [ ] Define stop loss enforcement (hard stop? soft alert?)
- [ ] Add validation in trade execution layer

**Acceptance Criteria:**
- No single engine can exceed its allocation
- No single asset can exceed portfolio limit
- Stop loss triggers are enforced, not just alerted

---

### 1.5 No Idempotency On Trade Execution

| Field | Value |
|-------|-------|
| **Severity** | 🔴 Critical |
| **Effort** | Medium |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
What prevents duplicate orders if the same signal fires twice? Unique constraint on what? Signal ID? Timestamp + engine?

**What Needs To Happen:**
- [ ] Add idempotency key to every trade signal
- [ ] Store idempotency keys in DB with TTL (e.g., 24 hours)
- [ ] Check for duplicate key before order execution
- [ ] Return same response for duplicate request (don't re-execute)
- [ ] Log duplicate attempts for debugging

**Acceptance Criteria:**
- Same signal fired twice = one order
- Idempotency window is configurable
- Duplicate attempts are logged and alertable

---

## 🟠 SECTION 2: HIGH CONCERNS (Fix Before Production Deploy)

### 2.1 SQLite WAL Checkpoint Locking

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
WAL mode is fine until checkpoint. Any lock contention during high-frequency trading? What's the max QPS before SQLite chokes?

**What Needs To Happen:**
- [ ] Benchmark SQLite WAL under load (simulate 6 engines trading)
- [ ] Define max QPS threshold
- [ ] Add monitoring for lock wait time
- [ ] Document Postgres migration trigger (when to switch)

**Acceptance Criteria:**
- Lock wait time < 100ms under normal load
- Alert if lock wait exceeds threshold
- Migration path to Postgres is documented and tested

---

### 2.2 Circuit Breaker Reset Undefined

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
5 consecutive tick errors → pause. How does it *unpause*? Manual only? What if you're asleep and it's a transient issue?

**What Needs To Happen:**
- [ ] Define reset behavior:
  - **Auto:** Resume after N minutes of no errors
  - **Manual:** Operator must explicitly resume
  - **Hybrid:** Auto after N minutes, but alert operator
- [ ] Define error counter reset conditions
- [ ] Add circuit breaker status to API + UI

**Acceptance Criteria:**
- Reset behavior is documented and configurable
- Operator is alerted on circuit breaker trigger
- Reset does not happen during active trade

---

### 2.3 Reconciliation Source of Truth

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Medium |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
When DB and HL diverge, which wins? You say "alert at 2%" but don't say what happens *after* the alert. Manual intervention? Auto-correct?

**What Needs To Happen:**
- [ ] Define source of truth: **Exchange (HL) wins**
- [ ] Define reconciliation frequency (e.g., every 5 minutes)
- [ ] Define auto-correct behavior:
  - Balance: Auto-adjust DB to match HL
  - Positions: Alert only, require manual confirmation
- [ ] Add "Reconcile Now" button to UI
- [ ] Log all reconciliation events

**Acceptance Criteria:**
- Divergence > 2% triggers alert
- Auto-correction is logged and auditable
- Manual override available for edge cases

---

### 2.4 Clock Drift Enforcement Missing

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Low |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
"Alert if > 5 seconds" — but what enforces NTP sync? Is there an actual NTP client or just checking system time? HL will reject stale orders.

**What Needs To Happen:**
- [ ] Implement NTP client check (e.g., `ntplib`)
- [ ] Define max drift threshold (5 seconds)
- [ ] Define behavior on drift exceeded:
  - Alert operator
  - Pause trading until synced
  - Auto-sync if possible
- [ ] Add clock status to health check

**Acceptance Criteria:**
- Clock drift is monitored continuously
- Trading pauses if drift exceeds threshold
- Operator is alerted immediately

---

### 2.5 Backup Restore Never Tested

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Medium |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
"Tested before production deploy" — when? By whom? What's the RTO? If restore takes 4 hours, can you trade during that window?

**What Needs To Happen:**
- [ ] Schedule backup restore test (date, owner)
- [ ] Document restore procedure step-by-step
- [ ] Measure and record RTO (Recovery Time Objective)
- [ ] Measure and record RPO (Recovery Point Objective)
- [ ] Define acceptable RTO/RPO thresholds

**Acceptance Criteria:**
- Restore test completed and documented
- RTO < 1 hour
- RPO < 24 hours
- Test repeated quarterly

---

### 2.6 API Auth Mechanism Unspecified

| Field | Value |
|-------|-------|
| **Severity** | 🟠 High |
| **Effort** | Medium |
| **Owner** | TBD |
| **Status** | ❌ Open |

**The Problem:**  
What protects write endpoints? API key? JWT? Session? Is it consistent across all endpoints?

**What Needs To Happen:**
- [ ] Define auth mechanism (recommend: API key + secret)
- [ ] Define which endpoints require auth (all write endpoints)
- [ ] Define how keys are stored (hashed, not plaintext)
- [ ] Define how keys are rotated
- [ ] Add auth middleware to FastAPI

**Acceptance Criteria:**
- All write endpoints require valid auth
- Keys are hashed in DB
- Invalid auth returns 401 with consistent response

---

## 🟡 SECTION 3: MEDIUM NITS (Fix Before Scale)

| # | Issue | Effort | Status |
|---|-------|--------|--------|
| 3.1 | Scoring warm-up trap (engines that don't hit 10 trades) | Low | ❌ |
| 3.2 | Partial fill position tracking (how is running position calculated?) | Medium | ❌ |
| 3.3 | Alert channel cascade failure (what if all channels fail?) | Low | ❌ |
| 3.4 | LLM context injection risk (sanitize input) | Low | ❌ |
| 3.5 | Concurrent engine lock contention (balance table locks) | Medium | ❌ |
| 3.6 | DRY_RUN=false prevention (confirmation prompt?) | Low | ❌ |
| 3.7 | Database migration strategy (auto? manual? rollback?) | Medium | ❌ |
| 3.8 | Health check frequency and depth | Low | ❌ |
| 3.9 | Rotation emergency override (operator unavailable) | Low | ❌ |
| 3.10 | Audit log for config changes | Low | ❌ |
| 3.11 | Trade cancellation endpoint | Medium | ❌ |
| 3.12 | Engine pause vs stop (state preservation) | Low | ❌ |
| 3.13 | Multi-user role system (future-proofing) | Medium | ❌ |
| 3.14 | Export format specified (CSV, JSON, both?) | Low | ❌ |
| 3.15 | Timezone standard declared (UTC everywhere) | Low | ❌ |
| 3.16 | Log rotation policy (retention, size cap) | Low | ❌ |
| 3.17 | Staging environment for testing | Medium | ❌ |
| 3.18 | Dependency version pinning | Low | ❌ |
| 3.19 | Disaster recovery runbook | Medium | ❌ |

---

## 📋 SECTION 4: DOCUMENTATION GAPS (Write Before Production)

### 4.1 Fernet Key Rotation Procedure

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Owner** | TBD |
| **Status** | ❌ Not Written |

**What Needs To Be Documented:**
- Step-by-step rotation procedure
- Who has access to initiate rotation
- Expected downtime (if any)
- Rollback procedure if rotation fails
- Post-rotation verification steps

---

### 4.2 Disaster Recovery Runbook

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Owner** | TBD |
| **Status** | ❌ Not Written |

**What Needs To Be Documented:**
- Server dies at 3 AM: literal step-by-step
- Who to contact (escalation chain)
- Backup restore procedure
- Health verification checklist
- Trading resume checklist

---

### 4.3 Deployment Procedure

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Owner** | TBD |
| **Status** | ❌ Not Written |

**What Needs To Be Documented:**
- Pre-deployment checklist
- Migration execution steps
- Rollback procedure
- Post-deployment verification
- Health check confirmation

---

### 4.4 Incident Response Playbook

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Owner** | TBD |
| **Status** | ❌ Not Written |

**What Needs To Be Documented:**
- Kill switch activation procedure
- Reconciliation mismatch response
- API error rate spike response
- Drawdown threshold breach response
- Communication templates (what to tell stakeholders)

---

### 4.5 Monitoring Dashboard Guide

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Owner** | TBD |
| **Status** | ❌ Not Written |

**What Needs To Be Documented:**
- What metrics are exposed
- Where to find them
- What each alert means
- Who to contact for each alert type
- Escalation timelines

---

## ✅ SECTION 5: SIGNOFF CHECKLIST

| Section | Reviewed By | Date | Status |
|---------|-------------|------|--------|
| Critical Vulns (1.x) | | | |
| High Concerns (2.x) | | | |
| Medium Nits (3.x) | | | |
| Documentation Gaps (4.x) | | | |

---

## 📝 NOTES

_Use this space for decisions, exceptions, and technical debt acknowledgments._