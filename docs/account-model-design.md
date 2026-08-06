# SentinAI #3 — Account/Team Model: Design Doc

Status: DRAFT — planning phase, Aug 6 2026
Author: Ebenezer

## 1. Why this sprint exists

Roadmap item #3: replace the current single/multi shared-API-key scheme with
real multi-user support (admin/viewer roles). Discovered during planning that
there are currently **two separate, inconsistent auth systems** in the
codebase — this must be resolved as part of #3, not left as a third system.

## 2. Current-state audit

| Concern | `src/api/security.py` | `src/api/auth.py` |
|---|---|---|
| Protects | `routes.py` — incidents, suggestions, scan-now, settings/autonomy, settings/channels | `chat.py` only |
| Key source | `SENTINAI_API_KEY` (single) | `SENTINAI_API_KEYS` (JSON, multi-tenant), falls back to `SENTINAI_API_KEY` |
| Concept | boolean "authorized or not" | `Tenant` (name, tier) |
| Rate limiting | none | `middleware.py` exists (per-tenant token bucket) but **is never called** — `chat.py` resolves `Tenant` via `require_tenant` but never calls `enforce_rate_limit`. Dead code. |
| Fail-open behavior | if `SENTINAI_API_KEY` unset → logs warning, allows all requests | if neither env var set → returns synthetic "anonymous"/INTERNAL tenant, allows all requests |

**Confirmed Aug 6 2026:** both Render production and local `.env` only set
`SENTINAI_API_KEY`. Because `auth.py` falls back to that same var, both
systems currently resolve to the same key and nothing is exposed today. This
is incidental, not by design — adding `SENTINAI_API_KEYS` later for any
reason (or removing `SENTINAI_API_KEY` thinking it's superseded) would leave
`routes.py` running with **no auth at all**, since `security.py` fails open.

**Decision:** #3 replaces both files with one auth system built on real
accounts/users, not a third API-key scheme.

## 3. Data model

```
Account (was: implicit single-tenant)
  id            uuid
  name          str
  created_at    datetime

User
  id            uuid
  account_id    fk -> Account
  email         str (unique)
  password_hash str
  role          enum: admin | viewer
  created_at    datetime
  last_login_at datetime | null

Session (or use JWT — see 4.2)
  token         str (opaque, random)
  user_id       fk -> User
  expires_at    datetime
```

Notes:
- One `Account` = one team/organization. Everything currently global in
  `app_state` (incidents, suggestions, settings, notification channels,
  autonomy_mode) becomes scoped to `account_id`. This is the biggest actual
  migration cost — bigger than the auth layer itself.
- `role` kept as a flat enum (admin/viewer) per roadmap scope — no
  fine-grained permissions system. admin = full read/write incl. settings,
  autonomy mode, channels, and PR-triggering actions. viewer = read-only
  (incidents, suggestions, stats, metrics).
- Storage: existing pattern in `logs/settings.json` (file-cache, per
  `AppState`) doesn't scale to multi-account. Needs a real store — smallest
  viable step is SQLite (already a project dependency pattern?  verify) or
  extending the JSON file-cache to be keyed by `account_id`. To decide in
  section 6.

## 4. Auth flow

### 4.1 Migration path (must not break production on deploy)

1. On first boot with the new system, if no `Account` exists yet, auto-create
   one `Account` named e.g. "default" and one `admin` `User` from an
   env-provided bootstrap email/password (`SENTINAI_ADMIN_EMAIL` /
   `SENTINAI_ADMIN_PASSWORD`), so the existing single deployment doesn't lock
   itself out.
2. Existing `SENTINAI_API_KEY` clients (if any external caller uses it)
   break — confirm nothing external depends on it before cutover. Internal
   frontend switches to session/JWT auth in the same PR as the backend
   change, so this is a single atomic deploy, not a gradual one.
3. Delete `src/api/security.py` and `src/api/auth.py` (+ `middleware.py`'s
   dead rate-limiter, or revive it — see 4.3) once the new system covers
   every route currently in `_PROTECTED` and `chat.py`.

### 4.2 Session mechanism: JWT vs opaque session token

Open question to resolve before coding:
- **JWT** — stateless, no DB hit per request, but harder to revoke
  (logout / role change doesn't take effect until expiry unless a
  blocklist is added).
- **Opaque session token in DB/file store** — trivial revocation, one extra
  lookup per request. Given SentinAI's traffic is low (single-team tool,
  not high-QPS SaaS), the lookup cost is a non-issue.

Leaning opaque token for simplicity and because revocation (e.g. removing a
teammate) should be immediate. Final call in section 6.

### 4.3 Rate limiting

`middleware.py`'s token-bucket logic is solid and tested — don't discard it.
Rewire `enforce_rate_limit` to run off the new `User`/`Account` instead of
the old `Tenant`, and actually call it (currently never invoked — that's a
one-line bug fix, do it regardless of the rest of #3 since it's cheap and
currently silently doing nothing).

## 5. API changes

New endpoints:
- `POST /auth/login` — email + password → session token
- `POST /auth/logout` — invalidate session
- `GET /auth/me` — current user + role
- `GET /account/users` (admin only) — list team members
- `POST /account/users` (admin only) — invite/create a user
- `PATCH /account/users/{id}` (admin only) — change role, deactivate
- `DELETE /account/users/{id}` (admin only) — remove user

Existing endpoints in `routes.py`: swap `dependencies=_PROTECTED`
(`require_api_key`) for a new `require_user` dependency; admin-only actions
(`settings/*`, `scan-now` if it should trigger PR creation) get an additional
`require_role("admin")` check. Read-only endpoints (`/incidents`,
`/suggestions`, `/stats`) allow both roles.

`chat.py` moves off `require_tenant`/`Tenant` onto the same `require_user`
dependency — collapses the two parallel systems into one.

## 6. Decisions (Aug 6 2026)

1. Storage: **SQLite** — JSON file-cache doesn't give safe concurrent
   writes for multi-user; SQLite is durable without adding Postgres
   overhead at this scale.
2. Session mechanism: **opaque session token** — immediate revocation on
   role change / user removal, over JWT's stateless-but-hard-to-revoke
   tradeoff.
3. Password reset: **deferred** — not a blocker for shipping the core
   auth/role system; fast-follow.
4. Frontend login UI: **in scope this sprint** — needed to actually
   exercise the system end-to-end, not backend-only.
5. Account model: **keep the `Account` table now**, even with a single row
   — retrofitting account_id onto already-scoped data later is riskier
   than the small cost of including it from the start.

## 7. Suggested build order (once questions above are answered)

1. Fix the dead `enforce_rate_limit` call in `chat.py` (independent, cheap,
   safe to ship alone first).
2. Data model + migration/bootstrap (User, Session, and Account only if Q5
   says yes).
3. `require_user` / `require_role` dependencies, swap into `routes.py` and
   `chat.py`, delete `security.py` + `auth.py`.
4. `/auth/*` and `/account/users/*` endpoints.
5. Frontend: login page, auth context, route guards, user management UI
   (or defer per Q4).
6. Delete legacy `SENTINAI_API_KEY(S)` env vars from Render once cutover is
   confirmed working.
