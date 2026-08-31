/**
 * Centralized API client for the real 24FPS FastAPI backend.
 *
 * Every network call the frontend makes goes through this module: base
 * URL, authentication header injection, JSON/FormData handling, and
 * error normalization all live here rather than being scattered across
 * components (task Phase 23 scope, "API Client").
 *
 * No mock fallback exists anywhere in this file. A failed request always
 * throws an `ApiError`; callers render a real error state (task Phase 23
 * scope, "No Mock Fallback in Production").
 */

import type * as T from './apiTypes';

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000/api/v1';

const TOKEN_STORAGE_KEY = '24fps.auth.token';

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function getStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage unavailable (private browsing, etc.) -- the session simply
    // will not persist across reloads; never crash the app over it.
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  json?: unknown;
  form?: FormData;
  params?: Record<string, string | number | boolean | undefined | null>;
  /** Skip attaching the Authorization header (only used for login). */
  anonymous?: boolean;
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function extractErrorMessage(response: Response): Promise<{ message: string; code: string | null }> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') {
      return { message: body.detail, code: null };
    }
    if (body?.error?.message) {
      return { message: String(body.error.message), code: body.error.code ?? null };
    }
    if (Array.isArray(body?.detail)) {
      // FastAPI/pydantic validation error list.
      const first = body.detail[0];
      return { message: first?.msg ? String(first.msg) : 'Request validation failed', code: null };
    }
  } catch {
    // Response body was not JSON -- fall through to the generic message.
  }
  return { message: `Request failed with status ${response.status}`, code: null };
}

async function request<TResponse>(path: string, options: RequestOptions = {}): Promise<TResponse> {
  const headers: Record<string, string> = {};
  if (!options.anonymous) {
    const token = getStoredToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.params), {
      method: options.method ?? 'GET',
      headers,
      body,
    });
  } catch (networkError) {
    throw new ApiError(
      0,
      'Could not reach the 24FPS backend. Check that it is running and reachable at ' +
        API_BASE_URL,
      'NETWORK_ERROR'
    );
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  if (!response.ok) {
    const { message, code } = await extractErrorMessage(response);
    throw new ApiError(response.status, message, code);
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as TResponse;
  }
  return undefined as TResponse;
}

/** Fetch a binary artifact/report as a Blob (for playback or download), authenticated. */
async function requestBlob(path: string): Promise<Blob> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(buildUrl(path), { headers });
  if (!response.ok) {
    const { message, code } = await extractErrorMessage(response);
    throw new ApiError(response.status, message, code);
  }
  return response.blob();
}

/** Trigger a browser "save file" for a blob fetched from the backend. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/**
 * URL for streaming an artifact directly as a `<video src>` (native HTTP
 * Range-request seeking, which an authenticated `fetch`-to-Blob would
 * lose on a large derived recording). A `<video>` element cannot attach
 * an `Authorization` header, so the caller's own session token rides
 * along as a `?token=` query parameter instead -- the backend's
 * `GET /artifacts/{id}/download` route accepts that as a fallback only
 * when no header is present (`app.api.deps.
 * get_current_user_from_header_or_query`), and case access is still
 * fully enforced either way (Phase 25). Known trade-off: this puts the
 * session token in the URL (and so in reachable server/browser history),
 * not a new, narrower-scoped credential -- see that dependency's own
 * docstring.
 */
export function artifactDownloadUrl(artifactId: number): string {
  const token = getStoredToken();
  return buildUrl(`/artifacts/${artifactId}/download`, token ? { token } : undefined);
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  login: (username: string, password: string) =>
    request<T.LoginResponse>('/auth/login', { method: 'POST', json: { username, password }, anonymous: true }),
  me: () => request<{ user_id: number; username: string; display_name: string; role: string }>('/auth/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export const usersApi = {
  list: () => request<T.UserResponse[]>('/users'),
  create: (payload: { username: string; display_name: string; password: string; role: string }) =>
    request<T.UserResponse>('/users', { method: 'POST', json: payload }),
};

// ---------------------------------------------------------------------------
// Case access (Phase 25) -- admin-only case-assignment matrix, backed by
// real backend enforcement (app/core/case_authorization_service.py), never
// a client-side-only permission display.
// ---------------------------------------------------------------------------

export const caseAccessApi = {
  matrix: () => request<T.AccessMatrixResponse>('/admin/case-access'),
  listForCase: (caseId: number) =>
    request<T.CaseAccessResponse[]>(`/admin/cases/${caseId}/access`),
  grant: (caseId: number, userId: number, reason?: string) =>
    request<T.CaseAccessResponse>(`/admin/cases/${caseId}/access/${userId}`, {
      method: 'POST',
      json: reason ? { reason } : {},
    }),
  revoke: (caseId: number, userId: number, reason?: string) =>
    request<T.CaseAccessResponse>(`/admin/cases/${caseId}/access/${userId}`, {
      method: 'DELETE',
      json: reason ? { reason } : {},
    }),
};

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

export const casesApi = {
  list: (skip = 0, limit = 200) =>
    request<T.CaseResponse[]>('/cases', { params: { skip, limit } }),
  get: (caseId: number) => request<T.CaseResponse>(`/cases/${caseId}`),
  create: (payload: { case_id: string; name: string; description?: string; examiner?: string; case_number?: string }) =>
    request<T.CaseResponse>('/cases', { method: 'POST', json: payload }),
  update: (caseId: number, payload: Partial<{ name: string; description: string; examiner: string; status: string }>) =>
    request<T.CaseResponse>(`/cases/${caseId}`, { method: 'PATCH', json: payload }),
  listEvidence: (caseId: number) => request<T.EvidenceResponse[]>(`/cases/${caseId}/evidence`),
  registerEvidence: (caseId: number, payload: { evidence_id: string; source_type: string; source_path?: string; source_description?: string }) =>
    request<T.EvidenceResponse>(`/cases/${caseId}/evidence`, { method: 'POST', json: payload }),
  uploadEvidence: (caseId: number, form: FormData) =>
    request<T.EvidenceResponse>(`/cases/${caseId}/evidence/upload`, { method: 'POST', form }),
  timeline: (caseId: number, includeCorrelated = false) =>
    request<T.TimelineEventResponse[]>(`/cases/${caseId}/timeline`, {
      params: { include_correlated: includeCorrelated },
    }),
  aiResults: (caseId: number, recordingId?: number) =>
    request<T.AIResultResponse[]>(`/cases/${caseId}/ai-results`, { params: { recording_id: recordingId } }),
  correlationEvents: (caseId: number) =>
    request<T.CorrelationCandidateResponse[]>(`/cases/${caseId}/correlation/events`),
  runCorrelation: (caseId: number) =>
    request<{ candidates: T.CorrelationCandidateResponse[] }>(`/cases/${caseId}/correlation/run`, {
      method: 'POST',
      json: {},
    }),
  validationMetrics: (caseId: number) =>
    request<T.ValidationMetricResponse[]>(`/cases/${caseId}/validation`),
  auditEvents: (caseId: number) => request<T.ProcessingEventResponse[]>(`/cases/${caseId}/audit`),
  verifyAuditChain: (caseId: number) =>
    request<T.ChainVerificationResponse>(`/cases/${caseId}/audit/verify`),
  blockchainAnchors: (caseId: number) =>
    request<T.BlockchainAnchorResponse[]>(`/cases/${caseId}/blockchain/anchors`),
  anchorBlockchain: (caseId: number, reason?: string) =>
    request<T.BlockchainAnchorResponse>(`/cases/${caseId}/blockchain/anchor`, {
      method: 'POST',
      json: { reason },
    }),
  reports: (caseId: number) => request<T.ReportResponse[]>(`/cases/${caseId}/reports`),
  generateReports: (caseId: number, formats?: string[]) =>
    request<T.ReportResponse[]>(`/cases/${caseId}/reports`, { method: 'POST', json: { formats } }),
  process: (caseId: number, policy?: Record<string, unknown>) =>
    request<T.ProcessingRunResponse>(`/cases/${caseId}/process`, {
      method: 'POST',
      json: policy ? { policy } : {},
    }),
  processingRuns: (caseId: number) =>
    request<T.ProcessingRunResponse[]>(`/cases/${caseId}/processing`),
  findings: (caseId: number, statusFilter?: string, severity?: string) =>
    request<T.FindingResponse[]>(`/cases/${caseId}/findings`, {
      params: { status_filter: statusFilter, severity },
    }),
  videoSearch: (caseId: number, query: string, recordingIds?: number[]) =>
    request<T.VideoSearchResponse>(`/cases/${caseId}/video-search`, {
      method: 'POST',
      json: { query, recording_ids: recordingIds },
    }),
};

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

export const evidenceApi = {
  get: (evidenceId: number) => request<T.EvidenceResponse>(`/evidence/${evidenceId}`),
  hashes: (evidenceId: number) => request<T.HashResponse[]>(`/evidence/${evidenceId}/hashes`),
  hash: (evidenceId: number) =>
    request<T.HashResponse[]>(`/evidence/${evidenceId}/hash`, { method: 'POST' }),
  verify: (evidenceId: number) =>
    request<T.HashResponse[]>(`/evidence/${evidenceId}/verify`, { method: 'POST' }),
  identifyDevice: (evidenceId: number) =>
    request<T.DeviceIdentificationResult>(`/evidence/${evidenceId}/identify-device`, { method: 'POST' }),
  detectFormat: (evidenceId: number) =>
    request<T.DeviceIdentificationResult>(`/evidence/${evidenceId}/detect-format`, { method: 'POST' }),
  device: (evidenceId: number) => request<T.DeviceResponse>(`/evidence/${evidenceId}/device`),
  recordings: (evidenceId: number) =>
    request<T.RecordingResponse[]>(`/evidence/${evidenceId}/recordings`),
  recoveryResults: (evidenceId: number) =>
    request<T.RecoveryResultResponse[]>(`/evidence/${evidenceId}/recovery-results`),
  artifacts: (evidenceId: number) => request<T.ArtifactResponse[]>(`/evidence/${evidenceId}/artifacts`),
  captureAcquisitionManifest: (evidenceId: number) =>
    request<T.ArtifactResponse>(`/evidence/${evidenceId}/acquisition-manifest`, { method: 'POST' }),
  getAcquisitionManifest: (evidenceId: number) =>
    request<Record<string, unknown>>(`/evidence/${evidenceId}/acquisition-manifest`),
  custodyHistory: (evidenceId: number) =>
    request<T.CustodyTransferResponse[]>(`/evidence/${evidenceId}/custody/history`),
  currentCustodian: (evidenceId: number) =>
    request<T.CustodyTransferResponse | null>(`/evidence/${evidenceId}/custody/current`),
  recordIntake: (evidenceId: number, receivingUserId: number, location?: string, notes?: string) =>
    request<T.CustodyTransferResponse>(`/evidence/${evidenceId}/custody/intake`, {
      method: 'POST',
      json: { receiving_user_id: receivingUserId, location, notes },
    }),
  initiateHandoff: (evidenceId: number, receivingUserId: number, location?: string, notes?: string) =>
    request<T.InitiateHandoffResponse>(`/evidence/${evidenceId}/custody/handoff`, {
      method: 'POST',
      json: { receiving_user_id: receivingUserId, location, notes },
    }),
};

export const custodyApi = {
  inspectByToken: (token: string) =>
    request<T.CustodyTransferResponse>('/custody/handoff/inspect', { method: 'POST', json: { token } }),
  acceptByToken: (token: string) =>
    request<T.CustodyTransferResponse>('/custody/handoff/accept', { method: 'POST', json: { token } }),
  rejectByToken: (token: string) =>
    request<T.CustodyTransferResponse>('/custody/handoff/reject', { method: 'POST', json: { token } }),
  cancel: (transferId: number) =>
    request<T.CustodyTransferResponse>(`/custody/handoff/${transferId}/cancel`, { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Recordings / Artifacts
// ---------------------------------------------------------------------------

export const recordingsApi = {
  get: (recordingId: number) => request<T.RecordingResponse>(`/recordings/${recordingId}`),
  extract: (recordingId: number) =>
    request<T.RecordingResponse>(`/recordings/${recordingId}/extract`, { method: 'POST' }),
  metadata: (recordingId: number) =>
    request<T.RecordingMetadataResponse[]>(`/recordings/${recordingId}/metadata`),
};

export const artifactsApi = {
  get: (artifactId: number) => request<T.ArtifactResponse>(`/artifacts/${artifactId}`),
  downloadBlob: (artifactId: number) => requestBlob(`/artifacts/${artifactId}/download`),
};

// ---------------------------------------------------------------------------
// Recovery / AI / Devices
// ---------------------------------------------------------------------------

export const aiApi = {
  runJob: (payload: {
    case_id: number;
    recording_ids: number[];
    analysis_types: string[];
    sampling_strategy?: string;
    sampling_value?: number;
  }) => request<T.JobResponse>('/ai/jobs', { method: 'POST', json: payload }),
};

export const devicesApi = {
  supportMatrix: () => request<T.VendorSupportSummaryResponse[]>('/devices/support-matrix'),
};

// ---------------------------------------------------------------------------
// Findings / Notifications
// ---------------------------------------------------------------------------

export const findingsApi = {
  get: (findingId: number) => request<T.FindingResponse>(`/findings/${findingId}`),
  update: (findingId: number, payload: { status: string; resolved_by?: string; resolution_notes?: string }) =>
    request<T.FindingResponse>(`/findings/${findingId}`, { method: 'PATCH', json: payload }),
};

export const notificationsApi = {
  list: (unreadOnly = false) =>
    request<T.NotificationResponse[]>('/notifications', { params: { unread_only: unreadOnly } }),
  update: (notificationId: number, payload: { read?: boolean; acknowledged?: boolean }) =>
    request<T.NotificationResponse>(`/notifications/${notificationId}`, { method: 'PATCH', json: payload }),
};

// ---------------------------------------------------------------------------
// Processing
// ---------------------------------------------------------------------------

export const processingApi = {
  get: (rootJobId: number) => request<T.ProcessingRunResponse>(`/processing/${rootJobId}`),
  accuracy: (rootJobId: number) =>
    request<T.AccuracyValidationResponse>(`/processing/${rootJobId}/accuracy`),
  outputs: (rootJobId: number) =>
    request<T.OutputParametersResponse>(`/processing/${rootJobId}/outputs`),
};

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export const reportsApi = {
  get: (reportId: number) => request<T.ReportResponse>(`/reports/${reportId}`),
  downloadBlob: (reportId: number) => requestBlob(`/reports/${reportId}/download`),
};

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export const systemApi = {
  health: () => request<T.HealthResponse>('/health', { anonymous: true }),
  capabilities: () => request<T.SystemCapabilitiesResponse>('/system/capabilities', { anonymous: true }),
  info: () =>
    request<{ app_version: string; app_env: string; database_url_scheme: string }>('/system/info', {
      anonymous: true,
    }),
};
