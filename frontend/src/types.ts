/**
 * Frontend-only UI types. Real domain data (cases, evidence, findings,
 * ...) is typed in `src/lib/apiTypes.ts`, mirroring the backend's own
 * response schemas -- this file holds only navigation/UI-state concepts
 * that have no backend representation.
 */

import type { UserResponse } from './lib/apiTypes';

/** Coarse UI split. Maps from the real backend `UserResponse.role`:
 * `admin` -> admin workspace, everything else (`officer`/`lab_personnel`)
 * -> the police/investigator workspace. Per-case access (which cases an
 * officer/lab_personnel can actually open) is real and backend-enforced
 * (Phase 25, `app.core.case_authorization_service`) -- this UI split is
 * only ever a navigation convenience, never itself a security boundary;
 * every case-scoped API call is authorized server-side regardless of
 * which workspace the request came from. */
export type UiRole = 'police' | 'admin';

export function uiRoleFor(user: UserResponse | null): UiRole {
  return user?.role === 'admin' ? 'admin' : 'police';
}

export type CaseTab =
  | 'overview'
  | 'evidence'
  | 'acquisition'
  | 'recovery'
  | 'timeline'
  | 'ai'
  | 'integrity'
  | 'custody'
  | 'findings'
  | 'report';

export type AdminSection =
  | 'dashboard'
  | 'cases'
  | 'users'
  | 'access'
  | 'audit'
  | 'security'
  | 'system'
  | 'oem'
  | 'ml'
  | 'storage';
