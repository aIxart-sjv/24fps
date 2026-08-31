# Phase 25 — Case-Level Access Control / Admin Permission Matrix

Real, backend-enforced authorization controlling which authenticated users
may view or act on which cases. Implemented in
`backend/app/core/case_authorization_service.py` and enforced by the
`app.api.deps.require_case_access*` FastAPI dependencies on every
case-scoped route. This document explains the model; the code's own
docstrings (start at `case_authorization_service.py`) are the
authoritative, always-current reference — this file summarizes and links
them, it never restates logic that could drift from the code.

## 1. Role model

`UserRole` (`backend/app/models/user.py`, unchanged by this phase):

| Role | Meaning |
|---|---|
| `ADMIN` | Full system administration. |
| `OFFICER` | A normal investigating officer. |
| `LAB_PERSONNEL` | Laboratory/technical personnel. |

Role is a fixed property of a user account, resolved once at login and
carried on every authenticated request (`app.api.deps.get_current_user`).
It answers "what kind of user is this", never "which cases can they see".

## 2. Case access model

`CaseUserAccess` (`backend/app/models/case_access.py`) is the second,
independent axis: one row per (user, case) pair, `ACTIVE` or `REVOKED`.
This is deliberately the *only* new concept this phase introduces — no
clearance levels, no per-field permissions, no time-boxed grants. A
`(user_id, case_id)` DB-level `UNIQUE` constraint guarantees at most one
row per pair; granting/revoking toggles that one row rather than
appending new ones (the history of *when* it changed lives in the
existing audit chain instead — see §5).

**Policy** (enforced in `CaseAuthorizationService.can_view_case`):

- **`ADMIN`** — unconditional access to every case. Never represented as
  a `CaseUserAccess` row, so a normal case assignment can never
  accidentally restrict an admin.
- **`OFFICER`** — access only to cases with an `ACTIVE` grant for
  exactly that user. No implicit access from evidence ownership, custody
  history, or any other signal.
- **`LAB_PERSONNEL`** — identical policy to `OFFICER`. No lab-specific
  workflow or automatic-access concept exists elsewhere in this codebase
  to plug into (confirmed by inspection at the time this phase was
  built), so the conservative, spec-compliant default applies: explicit
  grant required, same as any officer.

Role and case access are never conflated: there is no "OFFICER = L1,
TEAM LEAD = L2, DIRECTOR = L3" clearance hierarchy anywhere in this
system, decorative or otherwise. A prior, frontend-only mock of exactly
that hierarchy was removed rather than wired up to real enforcement — see
`frontend/src/components/admin/AdminAccessControl.tsx`'s own history.

## 3. Backend enforcement

Every case-scoped route depends on one of the `app.api.deps.
require_case_access*` FastAPI dependencies (by exact resource-identifier
shape: `case_id`, `evidence_id`, `recording_id`, `artifact_id`, `job_id`,
`finding_id`, `report_id`, `transfer_id`) or, for the handful of routes
where `case_id` lives in a request body rather than the URL
(`POST /ai/jobs`, `POST /validation/jobs`, `POST /timestamps/normalize`),
authorizes manually against the parsed body via
`CaseAuthorizationService.require_case_access` directly. Every dependency
funnels through the same service function, so the actual decision logic
exists in exactly one place (`case_authorization_service.py`), never
duplicated per route.

Coverage spans the full case data graph named in this phase's own task
scope: cases, evidence, recordings, artifacts (including streamed
download), recovery, timeline, correlation, AI results, visual search,
findings, validation, reports, provenance/audit, blockchain anchors,
custody, and processing runs. `backend/tests/test_case_authorization_api.py`
(`TestEveryCaseScopedRouteRejectsUnauthorizedOfficer`,
`TestIDOR`) exercises every one of these route categories against a real
HTTP client and asserts a `403`, including the literal "an officer edits
the case ID in the request" scenario.

Two intentional exceptions, both documented in code where they live:

- **Artifact streaming** (`GET /artifacts/{id}/download`): the frontend
  loads this directly as a `<video src>` for native HTTP Range-request
  seeking, which cannot attach an `Authorization` header. This one route
  additionally accepts the caller's own session token as a `?token=`
  query parameter (`app.api.deps.get_current_user_from_header_or_query`)
  — never a new, wider-scoped credential, and case access is still fully
  enforced either way. See that function's own docstring for the
  trade-off (the token can end up in server/browser logs for this URL).
- **QR custody handoff** (`inspect`/`accept`/`reject`/`cancel`): these
  are already restricted to a *narrower* per-transfer authorization
  (only the transfer's specific, pre-designated receiver/initiator, set
  by someone who already had case access when they created the
  transfer) than plain case membership. Case access is still checked as
  an additional layer on the token-based routes, but never substitutes
  for the transfer-specific check. See `app/api/routes/custody.py`'s
  module docstring.

## 4. Case listing

`GET /cases` returns every case for an `ADMIN`, and exactly the cases
with an `ACTIVE` grant for anyone else — filtered server-side
(`CaseAuthorizationService.list_user_cases`). The frontend never fetches
the full case list and hides rows client-side.

## 5. Case creation

`POST /cases` (`app/api/routes/cases.py::create_case`): the creator
automatically receives access to their own new case, so a case can never
end up accidentally inaccessible.

- `ADMIN` creator: no explicit grant needed (access is already
  unconditional).
- `OFFICER`/`LAB_PERSONNEL` creator: `CaseAuthorizationService.
  grant_initial_access_to_creator` creates the grant directly — a
  distinct method from the admin-gated `grant_case_access`, since the
  creator is not (necessarily) an admin and this is the platform
  bootstrapping their own access as a direct consequence of creation,
  not one user granting another.

## 6. Admin API

All under `/api/v1/admin/...`, gated by `app.api.deps.require_admin`
(`app/api/routes/admin_access.py`):

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/case-access` | Full user × case matrix (3 queries total, never one per cell). |
| `GET` | `/admin/cases/{case_id}/access` | Every grant (active or revoked) ever recorded for one case. |
| `POST` | `/admin/cases/{case_id}/access/{user_id}` | Grant (idempotent). |
| `DELETE` | `/admin/cases/{case_id}/access/{user_id}` | Revoke. |

The acting admin's identity always comes from the authenticated session
(`get_current_user`), never a request-body field — there is no way for a
caller to name a different admin as the one performing the grant.

## 7. Frontend

`frontend/src/components/admin/AdminAccessControl.tsx` renders the real
matrix returned by `GET /admin/case-access` — every cell is live backend
state, and clicking one (admin only) calls the real grant/revoke
endpoint and re-reads the matrix. `frontend/src/components/police/
CaseWorkspace.tsx` renders a distinct `AccessDeniedState` (`frontend/src/
components/common/CommonUI.tsx`) on a `403`, never a silent redirect or
fabricated data.

## 8. Audit trail / hash chain

Grant and revoke both call `app.core.provenance_manager.ProvenanceManager
.record_event` with `operation="case_access_change"`
(`app.audit.events.ProcessingOperation.CASE_ACCESS_CHANGE`) and
`parameters={"action": "grant"|"revoke", "target_user_id", "target_username"}`
— the existing Phase 15/16 hash-linked `ProcessingEvent` chain, not a
second logging system. `record_event` seals every event into the case's
chain via the existing `AuditChainManager.seal_event` exactly like any
other operation, so `GET /cases/{id}/audit/verify` detects tampering with
an access-change event the same way it detects tampering with any other
event.

## 9. Migration

`backend/migrations/versions/d886e2345a1b_phase_25_case_user_access.py`
adds the `case_user_access` table only — a brand-new table with plain FKs
to `cases`/`users`, no changes to any existing table.

## 10. Limitations

- No time-boxed/expiring grants — a grant is active until an admin
  explicitly revokes it.
- No bulk grant/revoke (e.g. "assign this officer to every case in this
  district") — one (user, case) pair per call, matching the task's own
  minimal-model scope.
- `LAB_PERSONNEL` has no role-specific workflow beyond the same
  explicit-grant policy as `OFFICER` — if a genuine lab-specific access
  pattern is ever required, it should be designed then, not guessed at
  now.
- The QR custody token-based routes' case-access check runs *after*
  `CustodyManager`'s own per-transfer receiver/initiator check (§3) —
  for `accept`/`reject`, a caller who is the pre-designated receiver but
  lacks case access still causes the manager's mutation to run before
  the case-access check returns a `403`. This is a narrow, already-gated
  edge case (the receiver was chosen by someone who did have case
  access), not an open authorization gap, but it is not perfectly
  atomic — see `app/api/routes/custody.py`'s module docstring.
- The artifact-download query-token fallback (§3) puts a real session
  token in a URL, which is more exposed (server access logs, browser
  history) than the header form. It remains bound to the same TTL and
  revocation as any other use of that token; it is not a new, longer-lived
  or wider-scoped credential.
