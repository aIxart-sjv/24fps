/**
 * Types mirroring the real 24FPS FastAPI backend's response schemas
 * (backend/app/schemas/*.py) field-for-field. These are NOT invented
 * frontend-only shapes -- every field here corresponds to a real,
 * persisted backend value. Where the backend has no concept (e.g.
 * "clearance level", "camera" as a first-class entity), no type for it
 * exists here.
 */

export interface CaseResponse {
  id: number;
  case_id: string;
  case_number: string | null;
  name: string;
  description: string | null;
  examiner: string | null;
  created_at: string;
  updated_at: string;
  reference_time: string | null;
  status: 'draft' | 'active' | 'processing' | 'review' | 'completed' | 'archived';
  software_version: string | null;
  schema_version: string | null;
}

export interface EvidenceResponse {
  id: number;
  evidence_id: string;
  case_id: number;
  source_type: string;
  source_path: string | null;
  source_description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface RecordingResponse {
  id: number;
  evidence_id: number;
  recording_id: string;
  camera_id: string | null;
  channel: number | null;
  start_original: string | null;
  end_original: string | null;
  start_normalized: string | null;
  end_normalized: string | null;
  duration_ms: number | null;
  codec: string | null;
  container: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  source_location: string | null;
  recovery_status: string | null;
  recovery_method: string | null;
  confidence: number | null;
  artifact_id: string | null;
}

export interface RecordingMetadataResponse {
  id: number;
  recording_id: number;
  key: string;
  value: string | null;
  source: string | null;
  confidence: number | null;
}

export interface ArtifactResponse {
  id: number;
  evidence_id: number;
  parent_artifact_id: number | null;
  artifact_type: string;
  path: string;
  size_bytes: number | null;
  sha256: string | null;
  md5: string | null;
  created_at: string;
  created_by: string | null;
  tool_version: string | null;
  status: string;
}

export interface HashResponse {
  id: number;
  evidence_id: number;
  algorithm: 'sha256' | 'md5';
  hash_value: string;
  calculated_at: string;
  software_version: string | null;
  source_reference: string | null;
  verification_status: 'not_verified' | 'verified' | 'mismatch';
}

export interface DeviceResponse {
  id: number;
  evidence_id: number;
  vendor: string | null;
  model: string | null;
  firmware: string | null;
  serial_number: string | null;
  device_type: string | null;
  channel_count: number | null;
  camera_count: number | null;
  network_info: string | null;
  confidence: number | null;
  identification_method: string | null;
}

export interface DeviceIdentificationResult {
  status: 'identified' | 'partial' | 'unknown' | 'unsupported';
  vendor: string | null;
  model: string | null;
  firmware: string | null;
  device_type: string | null;
  serial_number: string | null;
  storage_format: string | null;
  filesystem_type: string | null;
  sector_size: number | null;
  capacity: number | null;
  identification_method: string;
  confidence: number;
  warnings: string[];
  supporting_evidence: string[];
  parser_selection_hints: string[];
}

export interface VendorSupportSummaryResponse {
  vendor: string;
  model_pattern: string;
  firmware_pattern: string | null;
  model_scope: string;
  support_level: number;
  support_level_label: string;
  evidence_basis: string[];
  capabilities: string[];
  limitations: string[];
  adapter_version: string;
}

export interface RecoveryResultResponse {
  id: number;
  evidence_id: number;
  recording_id: number;
  artifact_id: number | null;
  method: string;
  status: string;
  fragments_found: number | null;
  fragments_used: number | null;
  fragments_missing: number | null;
  frames_expected: number | null;
  frames_recovered: number | null;
  recovery_rate: number | null;
  timestamp_error: number | null;
  frame_continuity: number | null;
  confidence: number | null;
  recovery_engine_version: string | null;
  parser_version: string | null;
  notes: string | null;
  created_at: string;
  validation_warning: string | null;
}

export interface JobResponse {
  id: number;
  case_id: number;
  evidence_id: number | null;
  parent_job_id: number | null;
  job_type: string;
  status: string;
  progress: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  worker: string | null;
  recording_ids: number[] | null;
  analysis_types: string[] | null;
  model_versions: Record<string, string> | null;
  parameters: Record<string, unknown> | null;
  software_version: string | null;
  results_count: number;
  input_artifacts: number[] | null;
  output_artifacts: number[] | null;
  error: string | null;
  warnings: string[] | null;
}

export interface ProcessingStageResponse {
  id: number;
  job_type: string;
  status: string;
  evidence_id: number | null;
  recording_ids: number[] | null;
  progress: number | null;
  results_count: number;
  error: string | null;
  warnings: string[] | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  high_resolution_timing: boolean | null;
  cpu_user_seconds: number | null;
  cpu_system_seconds: number | null;
  peak_rss_kb: number | null;
  rss_delta_kb: number | null;
  input_type: string | null;
  input_size: number | null;
  input_size_unit: string | null;
}

export interface ProcessingRunResponse {
  root_job: JobResponse;
  stages: ProcessingStageResponse[];
  stages_total: number;
  stages_completed: number;
  stages_failed: number;
  stages_skipped: number;
  stages_blocked: number;
  stages_requires_review: number;
  new_finding_ids: number[];
  notification_ids: number[];
  total_duration_seconds: number | null;
}

export type AccuracyStatus = 'VALIDATED' | 'CONTROLLED' | 'OBSERVATION' | 'UNVERIFIED' | 'N/A';

export interface AccuracyMetricResponse {
  module: string;
  metric: string;
  value: string;
  status: AccuracyStatus;
  basis: string;
  source: string;
  notes: string | null;
}

export interface AccuracyValidationResponse {
  root_job_id: number;
  metrics: AccuracyMetricResponse[];
}

export interface OutputParameterResponse {
  module: string;
  parameter: string;
  value: string;
  source: string;
  notes: string | null;
}

export interface OutputParametersResponse {
  root_job_id: number;
  parameters: OutputParameterResponse[];
}

export interface FindingResponse {
  id: number;
  case_id: number;
  evidence_id: number | null;
  recording_id: number | null;
  source_job_id: number | null;
  finding_type: string;
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical';
  confidence: string;
  title: string;
  description: string;
  status: 'open' | 'acknowledged' | 'in_review' | 'resolved' | 'dismissed';
  source_reference: Record<string, unknown> | null;
  limitations: string[] | null;
  occurrence_count: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
  resolved_recording_id: number | null;
  resolved_timestamp: string | null;
}

export interface NotificationResponse {
  id: number;
  recipient_user_id: number;
  finding_id: number;
  created_at: string;
  read_at: string | null;
  acknowledged_at: string | null;
  finding: FindingResponse;
}

export interface AIResultResponse {
  id: number;
  job_id: number | null;
  case_id: number;
  recording_id: number;
  analysis_type: string;
  model_name: string;
  model_version: string;
  frame_number: number;
  timestamp: string | null;
  class_name: string;
  confidence: number;
  bbox: { x_min: number; y_min: number; x_max: number; y_max: number };
  track_id: number | null;
  source_artifact: number;
  created_at: string;
}

export interface TimelineEventResponse {
  id: number;
  case_id: number;
  recording_id: number | null;
  camera_id: string | null;
  event_type: string;
  original_timestamp: string | null;
  normalized_timestamp: string | null;
  confidence: number | null;
  source: string | null;
  description: string | null;
  ai_reference: string | null;
  recovery_status: string | null;
  correlation_id: number | null;
  created_at: string;
  timestamp_status: string;
  timestamp_source: string | null;
  timezone_status: string;
  timezone_basis: string | null;
}

export interface CorrelationCandidateResponse {
  correlation_event_id: number;
  event_ids: string[];
  status: string;
  confidence: number | null;
  confidence_basis: string[];
  recovery_signals: Record<string, string>;
  max_gap_seconds: number;
  method: string;
  warnings: string[];
}

export interface ValidationMetricResponse {
  id: number;
  job_id: number;
  case_id: number;
  dataset_id: string;
  validation_type: string;
  metric_name: string;
  metric_value: number | null;
  numerator: number | null;
  denominator: number | null;
  threshold: number | null;
  notes: string | null;
  created_at: string;
}

export interface ProcessingEventResponse {
  id: number;
  case_id: number;
  evidence_id: number | null;
  job_id: number | null;
  operation: string;
  actor: string;
  actor_type: string;
  tool: string | null;
  tool_version: string | null;
  software_version: string | null;
  parameters: Record<string, unknown> | null;
  input_artifact_ids: number[] | null;
  output_artifact_ids: number[] | null;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  warnings: string[] | null;
  error: string | null;
  notes: string | null;
  description: string | null;
  location_reference: string | null;
  previous_hash: string | null;
  current_hash: string | null;
  created_at: string;
}

export interface ChainVerificationResponse {
  case_id: number;
  chain_scope: string;
  valid: boolean;
  event_count: number;
  first_event_id: number | null;
  last_event_id: number | null;
  failure: { event_id: number | null; reason: string; detail: string } | null;
}

export interface BlockchainAnchorResponse {
  id: number;
  case_id: number;
  chain_id: string;
  audit_state_hash: string;
  provider: string;
  network: string;
  transaction_reference: string;
  status: string;
  reason: string | null;
  error: string | null;
  created_at: string;
  verified_at: string | null;
}

export interface ReportResponse {
  id: number;
  case_id: number;
  job_id: number | null;
  report_type: string;
  report_hash: string | null;
  report_schema_version: string | null;
  software_version: string | null;
  status: string;
  error: string | null;
  warnings: string[] | null;
  created_at: string;
  completed_at: string | null;
}

export interface CustodyTransferResponse {
  id: number;
  evidence_id: number;
  transfer_type: 'INTAKE' | 'TRANSFER';
  status: 'PENDING' | 'ACCEPTED' | 'EXPIRED' | 'CANCELLED' | 'REJECTED';
  releasing_user_id: number | null;
  releasing_user_display_name: string | null;
  receiving_user_id: number;
  receiving_user_display_name: string;
  initiated_at: string;
  expires_at: string | null;
  accepted_at: string | null;
  location: string | null;
  notes: string | null;
  provenance_event_id: number | null;
}

export interface InitiateHandoffResponse {
  transfer: CustodyTransferResponse;
  token: string;
  qr_code_png_base64: string;
}

export interface UserResponse {
  id: number;
  username: string;
  display_name: string;
  role: 'officer' | 'lab_personnel' | 'admin';
  is_active: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Case access (Phase 25, "Case-Level Access Control / Admin Permission
// Matrix") -- real, backend-enforced per-(user, case) grants, not a
// decorative clearance level. See backend/app/core/case_authorization_service.py.
// ---------------------------------------------------------------------------

export interface CaseAccessResponse {
  id: number;
  case_id: number;
  case_business_id: string;
  user_id: number;
  username: string;
  user_display_name: string;
  status: 'active' | 'revoked';
  granted_by_user_id: number;
  granted_by_display_name: string;
  granted_at: string;
  revoked_at: string | null;
  revoked_by_user_id: number | null;
  revoked_by_display_name: string | null;
  reason: string | null;
}

export interface AccessMatrixCase {
  id: number;
  case_id: string;
  name: string;
}

export interface AccessMatrixUserRow {
  user_id: number;
  username: string;
  display_name: string;
  role: 'officer' | 'lab_personnel' | 'admin';
  /** Keyed by `AccessMatrixCase.id` (as a string, since it arrives as a
   * JSON object key) -- `true` for every case when `role === 'admin'`
   * (unconditional access is never a per-case grant row). */
  access_by_case_id: Record<string, boolean>;
}

export interface AccessMatrixResponse {
  cases: AccessMatrixCase[];
  users: AccessMatrixUserRow[];
}

export interface LoginResponse {
  token: string;
  expires_at: string;
  user_id: number;
  username: string;
  display_name: string;
  role: 'officer' | 'lab_personnel' | 'admin';
}

export interface VideoSearchSightingResponse {
  recording_id: number;
  camera_id: string | null;
  start_frame: number;
  end_frame: number;
  start_timestamp: string | null;
  end_timestamp: string | null;
  matched_color: string;
  match_confidence: number;
  ai_result_ids: number[];
  track_id: number | null;
  class_name: string;
  source_artifact: number;
}

export interface VideoSearchResponse {
  case_id: number;
  query: string;
  method: string;
  method_version: string;
  recognized_color: string | null;
  recognized_object_class: string | null;
  supported_colors: string[];
  supported_classes: string[];
  recognized: boolean;
  detections_examined: number;
  sightings: VideoSearchSightingResponse[];
  warnings: string[];
  disclaimer: string;
}

export interface SystemCapabilitiesResponse {
  subsystems: Array<{ name: string; implemented: boolean; notes: string }>;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  database_connected: boolean;
}
