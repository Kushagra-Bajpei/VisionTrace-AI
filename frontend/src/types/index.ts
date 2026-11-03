/**
 * Shared TypeScript domain models and API types for VisionTrace AI.
 */

// ── API response wrappers ──────────────────────────────────────────────────
export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ApiError {
  detail: string
  status_code?: number
}

// ── Health Telemetry ───────────────────────────────────────────────────────
export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error'
  service: string
  version: string
  environment: string
  timestamp: string
  uptime_seconds: number
}

export interface SubsystemStatus {
  status: 'ok' | 'not_configured' | 'unreachable' | 'error' | 'missing'
  note?: string
  details?: string
  path?: string
}

export interface DetailedHealthStatus extends HealthStatus {
  subsystems: {
    api: SubsystemStatus
    database: SubsystemStatus
    redis: SubsystemStatus
    storage: SubsystemStatus
  }
  runtime: {
    python: string
    platform: string
  }
}

// ── Video Domain Models ────────────────────────────────────────────────────
export type VideoStatus =
  | 'uploaded'
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'uploading'

export interface VideoMetadata {
  frame_count?: number
  extracted_frames_count?: number
  frame_interval_seconds?: number
  frames_dir?: string
  detections_count?: number
  tracks_count?: number
  detected_classes?: string[]
  yolo_model?: string
  tracker?: string
  format?: string
  bitrate_kbps?: number
  codec?: string
  [key: string]: unknown
}

export interface BoundingBox {
  x_min: number
  y_min: number
  x_max: number
  y_max: number
  box_format?: string
}

export interface DetectionEvent {
  id: string
  video_id: string
  track_id: string | null
  timestamp: number
  event_type: string
  description: string
  confidence: number
  bounding_box: BoundingBox | null
  frame_path: string | null
  attributes?: {
    class_name?: string
    class_id?: number
    frame_index?: number
    track_number?: number
    [key: string]: unknown
  }
  created_at: string
}

export interface ObjectTrack {
  id: string
  video_id: string
  track_id: number
  object_class: string
  start_time: number
  end_time: number
  start_frame: number
  end_frame: number
  confidence_avg: number
  attributes?: {
    detection_count?: number
    trajectory?: Array<{
      timestamp: number
      frame_index: number
      bbox: [number, number, number, number]
      confidence: number
    }>
    [key: string]: unknown
  }
  events?: DetectionEvent[]
  created_at: string
}

export interface Video {
  id: string
  filename: string
  original_filename: string
  file_path: string
  file_size: number
  duration: number | null
  width: number | null
  height: number | null
  fps: number | null
  status: VideoStatus
  processing_progress: number
  error_message: string | null
  thumbnail_path: string | null
  video_metadata: VideoMetadata | null
  camera_id: string | null
  uploaded_by: string | null
  file_hash?: string | null
  hash_algorithm?: string | null
  hashed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ExtractedFrame {
  index: number
  timestamp_seconds: number
  filename: string
  preview_url: string
}

export interface VideoStats {
  total_videos: number
  total_duration_seconds: number
  total_size_bytes: number
  uploaded_count: number
  processing_count: number
  completed_count: number
}

export interface VideoListParams {
  search?: string
  status?: string
  camera_id?: string
  skip?: number
  limit?: number
  sort_by?: 'created_at_desc' | 'created_at_asc' | 'duration_desc'
}

// ── Natural Language Search (Phase 5) ──────────────────────────────────────
export interface SearchQueryRequest {
  query: string
  video_id?: string
  object_class?: string
  min_confidence?: number
  time_min?: number
  time_max?: number
  visual_search?: boolean
  min_visual_similarity?: number
  limit?: number
  offset?: number
}

export interface ParsedFacets {
  target_classes: string[]
  min_confidence?: number | null
  time_min?: number | null
  time_max?: number | null
  track_number?: number | null
  temporal_intent: string
  visual_descriptors?: string[]
  is_visual_search?: boolean
  unsupported_facets: string[]
}

export interface SearchTrackMatch {
  id: string
  video_id: string
  video_name: string
  track_id: number
  object_class: string
  start_time: number
  end_time: number
  start_frame: number
  end_frame: number
  confidence_avg: number
  detection_count: number
  trajectory: Array<{
    timestamp: number
    frame_index: number
    bbox: [number, number, number, number]
    confidence: number
  }>
}

export interface SearchDetectionMatch {
  id: string
  video_id: string
  video_name: string
  track_id?: string | null
  track_number?: number | null
  timestamp: number
  object_class: string
  confidence: number
  visual_similarity_score?: number | null
  bounding_box: BoundingBox | null
  frame_path?: string | null
  annotated_frame_url?: string | null
  crop_image_url?: string | null
  is_visual_match?: boolean
}

export interface SearchVideoMatch {
  id: string
  original_filename: string
  duration?: number | null
  fps?: number | null
  resolution?: string | null
  thumbnail_url?: string | null
  matching_tracks_count: number
  matching_detections_count: number
}

export interface SearchQueryResponse {
  query: string
  search_mode?: string
  parsed_facets: ParsedFacets
  total_matches: number
  total_tracks: number
  evidence_summary: string
  videos: SearchVideoMatch[]
  tracks: SearchTrackMatch[]
  detections: SearchDetectionMatch[]
  offset: number
  limit: number
}

export interface SearchSuggestion {
  query: string
  description: string
  category: string
}

// ── Investigation Cases & Evidence Management (Phase 7) ─────────────────────
export type CaseStatus = 'open' | 'in_progress' | 'under_review' | 'closed'
export type CasePriority = 'low' | 'medium' | 'high' | 'critical'
export type EvidenceType = 'detection' | 'tracked_object' | 'keyframe' | 'visual_similarity' | 'note'

export interface InvestigationEvidence {
  id: string
  investigation_id: string
  video_id: string
  timestamp: number
  event_id?: string | null
  track_id?: string | null
  evidence_type: EvidenceType
  frame_path?: string | null
  crop_path?: string | null
  frame_url?: string | null
  crop_url?: string | null
  object_class?: string | null
  confidence?: number | null
  visual_similarity_score?: number | null
  notes?: string | null
  sequence_number: number
  custom_metadata?: Record<string, unknown> | null
  evidence_hash?: string | null
  hash_algorithm?: string | null
  hashed_at?: string | null
  created_at: string
  updated_at: string
  video_filename?: string | null
  video_title?: string | null
}

export interface InvestigationMessage {
  id: string
  investigation_id: string
  sender_type: string
  message: string
  references?: Record<string, unknown> | null
  created_at: string
}

export interface InvestigationCase {
  id: string
  title: string
  description?: string | null
  status: CaseStatus
  priority: CasePriority
  tags: string[]
  owner_id?: string | null
  reviewer_id?: string | null
  lead_investigator_id?: string | null
  evidence_count: number
  created_at: string
  updated_at: string
  evidence_items?: InvestigationEvidence[]
  messages?: InvestigationMessage[]
}

export interface CaseCreatePayload {
  title: string
  description?: string
  status?: CaseStatus
  priority?: CasePriority
  tags?: string[]
  reviewer_id?: string | null
  lead_investigator_id?: string | null
}

export interface CaseUpdatePayload {
  title?: string
  description?: string
  status?: CaseStatus
  priority?: CasePriority
  tags?: string[]
  reviewer_id?: string | null
  lead_investigator_id?: string | null
}

export interface EvidenceAddPayload {
  video_id: string
  timestamp: number
  event_id?: string | null
  track_id?: string | null
  evidence_type?: EvidenceType
  frame_path?: string | null
  crop_path?: string | null
  object_class?: string | null
  confidence?: number | null
  visual_similarity_score?: number | null
  notes?: string | null
  sequence_number?: number
  custom_metadata?: Record<string, unknown>
}

export interface EvidenceUpdatePayload {
  notes?: string
  sequence_number?: number
  custom_metadata?: Record<string, unknown>
}

export interface ReportGeneratePayload {
  title?: string
  executive_summary?: string
  include_evidence_thumbnails?: boolean
  custom_notes?: string
}

export interface CaseReport {
  id: string
  investigation_id: string
  case_title?: string | null
  title: string
  executive_summary: string
  pdf_path?: string | null
  download_url?: string | null
  pdf_hash?: string | null
  hash_algorithm?: string | null
  hashed_at?: string | null
  findings?: Record<string, unknown> | null
  evidence_timeline?: Record<string, unknown> | null
  status: string
  created_at: string
  updated_at: string
}

// ── Auth, RBAC & Audit Domain Models ────────────────────────────────────────
export type UserRole = 'admin' | 'investigator' | 'reviewer' | 'viewer'

export interface User {
  id: string
  email: string
  full_name?: string | null
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface MediaTokenResponse {
  media_token: string
  token_type: string
  resource_type: string
  resource_id: string
  expires_in: number
}

export interface AuditLog {
  id: string
  actor_id?: string | null
  actor_email?: string | null
  action: string
  target_type: string
  target_id?: string | null
  outcome: string
  client_ip?: string | null
  details?: Record<string, unknown> | null
  created_at: string
}

export interface IntegrityVerificationResult {
  status: 'verified' | 'mismatch' | 'unavailable' | 'not_recorded'
  expected_hash?: string | null
  computed_hash?: string | null
  actual_hash?: string | null
  verified: boolean
  details: string
  hash_algorithm?: string
  hashed_at?: string | null
  video_id?: string
  evidence_id?: string
  report_id?: string
}
