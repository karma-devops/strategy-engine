# Architecture Decision Records

## ADR-008: Operator UI Authentication

**Date:** 2026-07-19

**Status:** Accepted

**Context:**
Per-user isolation (Tier 2 per-user work) made `_current_user_id()` reject the global
`AGENT_API_KEY` with 403 — no operator fallback. Previously the operator dashboard UI
injected `config.AGENT_API_KEY` into page source and used it for client-side API calls
(e.g. `GET /api/v2/credentials` in `account_secrets.html`). After isolation, that call
returns 403, breaking the operator's own credential-management UI.

**Decision:**
Inject the operator's per-user `puls_` API key into dashboard templates instead of the
global `AGENT_API_KEY`. A helper `get_dashboard_api_key()` loads the operator user,
Fernet-decrypts their stored `puls_` key, and returns it. Templates continue using
`{{ api_key }}` unchanged.

**Alternatives Considered:**
- Revert `_current_user_id()` to allow operator fallback — rejected: breaks the isolation
  model ("no operator fallback" is the locked rule).
- Add session-auth variants of the credential routes — rejected: creates special-case /
  implicit-superuser logic; mixes auth models.

**Consequences:**
- Operator authenticates as a tenant user (consistent with the isolation model). Aligns
  with VOCABULARY.md: Operator = a User with privileges, not a special global identity.
- Global `AGENT_API_KEY` is dead for all tenant routes (security improved).
- Template render logic updated: `get_dashboard_api_key()` replaces `config.AGENT_API_KEY`
  for pages that call tenant APIs.
- Implementation warning honored: the decrypted key lives only in the render-path memory
  (returned to the template, never written to disk/logs). A leaked operator `puls_` key is
  a single-tenant compromise, strictly less dangerous than a leaked global key.
- No circular dependency: `get_dashboard_api_key()` calls `get_or_seed_operator()` +
  `decrypt_api_key()`, neither of which calls `_current_user_id()`.

**Verification:**
- Operator (`puls_` key) → `GET /api/v2/credentials` → 200 (operator's own creds).
- Global `AGENT_API_KEY` → `GET /api/v2/credentials` → 403.
