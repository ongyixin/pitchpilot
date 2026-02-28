/**
 * PitchPilot — Frontend TypeScript types.
 *
 * These mirror the Pydantic models in backend/api_schemas.py exactly.
 * When you rename or add a field in the backend, update here too.
 *
 * UUID fields arrive as strings in JSON (FastAPI serialises UUID → str).
 */

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type SessionStatus = "pending" | "processing" | "complete" | "failed";

/**
 * Three canonical presentation modes.
 *
 * "upload" and "live" are kept for backward compatibility.
 * Use "review", "live_in_room", and "live_remote" for new code.
 *
 * Backend mapping:
 *   review       → SessionMode.REVIEW  (post-hoc analysis, video upload)
 *   live_in_room → SessionMode.LIVE_IN_ROOM  (face-to-face, earpiece cues)
 *   live_remote  → SessionMode.LIVE_REMOTE   (virtual demo, on-screen overlay)
 */
export type SessionMode =
  | "upload"       // legacy alias for review
  | "live"         // legacy alias for live sessions
  | "review"       // canonical: post-hoc rehearsal analysis
  | "live_in_room" // canonical: face-to-face earpiece coaching
  | "live_remote"; // canonical: remote demo presenter overlay

export function isLiveMode(mode: SessionMode): boolean {
  return mode === "live" || mode === "live_in_room" || mode === "live_remote";
}

export function isReviewMode(mode: SessionMode): boolean {
  return mode === "upload" || mode === "review";
}

export type AgentType = "coach" | "compliance" | "persona";

export type Severity = "info" | "warning" | "critical";

export type ClaimType =
  | "feature"
  | "metric"
  | "comparison"
  | "privacy"
  | "pricing"
  | "security"
  | "other";

/** Drives colour coding in the Timeline component */
export type TimelineCategory = "compliance" | "coach" | "persona";

// ---------------------------------------------------------------------------
// Domain objects
// ---------------------------------------------------------------------------

export interface Claim {
  id: string;
  text: string;
  claim_type: ClaimType;
  /** Seconds from video start */
  timestamp: number;
  /** "transcript" | "slide" | "both" */
  source: string;
  slide_number?: number;
  /** 0.0 – 1.0 */
  confidence: number;
}

export interface Finding {
  id: string;
  agent: AgentType;
  severity: Severity;
  /** One-line title shown in UI card header */
  title: string;
  detail: string;
  suggestion?: string;
  /** Seconds into the video */
  timestamp: number;
  claim_id?: string;
  /** Compliance agent only */
  policy_reference?: string;
  /** Persona agent only */
  persona?: string;
  /** True when finding was produced during a live session */
  live?: boolean;
  /** 3-6 word earpiece cue phrase (live_in_room mode) */
  cue_hint?: string;
}

export interface TimelineAnnotation {
  id: string;
  finding_id: string;
  category: TimelineCategory;
  timestamp: number;
  /** Short label ≤ 60 chars */
  label: string;
  severity: Severity;
}

export interface DimensionScore {
  dimension: string;
  /** 0 – 100 */
  score: number;
  rationale: string;
}

export interface ReadinessScore {
  /** 0 – 100 composite */
  overall: number;
  dimensions: DimensionScore[];
  /** Ordered list of highest-priority improvements */
  priority_fixes: string[];
}

export interface PersonaQuestion {
  id: string;
  persona: string;
  question: string;
  follow_up?: string;
  timestamp?: number;
  difficulty: Severity;
}

export interface ReadinessReport {
  session_id: string;
  score: ReadinessScore;
  findings: Finding[];
  persona_questions: PersonaQuestion[];
  claims: Claim[];
  summary: string;
  created_at: string;
  /** Present on reports produced by live sessions; absent for review/upload mode */
  session_mode?: string;
  /** Duration of the live session in seconds */
  session_duration_seconds?: number;
  /** Number of earpiece cues (in-room) or overlay cards (remote) delivered live */
  live_cues_count?: number;
  /** Post-hoc narrative of what happened during the live session */
  live_session_summary?: string;
}

// ---------------------------------------------------------------------------
// API response wrappers
// ---------------------------------------------------------------------------

export interface SessionStartResponse {
  session_id: string;
  status: SessionStatus;
  message: string;
}

export interface SessionStatusResponse {
  session_id: string;
  status: SessionStatus;
  /** 0 – 100 */
  progress: number;
  progress_message: string;
  error_message?: string;
}

export interface TimelineResponse {
  session_id: string;
  annotations: TimelineAnnotation[];
}

export interface FindingsResponse {
  session_id: string;
  findings: Finding[];
  persona_questions: PersonaQuestion[];
}

// ---------------------------------------------------------------------------
// UI-only helpers (not from backend)
// ---------------------------------------------------------------------------

/** Hex colour for each category / agent type */
export const CATEGORY_COLORS: Record<TimelineCategory | AgentType, string> = {
  compliance: "#ef4444",
  coach:      "#3b82f6",
  persona:    "#a855f7",
};

export const SEVERITY_BADGE: Record<Severity, string> = {
  info:     "bg-blue-100 text-blue-700",
  warning:  "bg-yellow-100 text-yellow-800",
  critical: "bg-red-100 text-red-700",
};

export const AGENT_LABEL: Record<AgentType, string> = {
  coach:      "Coach",
  compliance: "Compliance",
  persona:    "Persona",
};

// ---------------------------------------------------------------------------
// Livestream mode types
// ---------------------------------------------------------------------------

export type LiveMessageType =
  | "session_created"
  | "transcript_update"
  | "finding"
  | "nudge"
  | "finalizing"
  | "session_complete"
  | "error"
  | "pong"
  // live_in_room
  | "earpiece_cue"
  // live_remote
  | "teleprompter"
  | "objection_prep"
  | "script_suggestion";

export interface LiveTranscriptSegment {
  text: string;
  start_time: number;
  end_time: number;
}

export interface LiveNudge {
  agent: AgentType;
  message: string;
  suggestion?: string;
  severity: Severity;
  elapsed: number;
  id: string;
}

// ---------------------------------------------------------------------------
// live_in_room — earpiece cue
// ---------------------------------------------------------------------------

export interface EarpieceCue {
  id: string;
  text: string;
  /** base64 audio blob or null (text-only fallback) */
  audio_b64: string | null;
  priority: Severity;
  category: string;
  elapsed: number;
}

// ---------------------------------------------------------------------------
// live_remote — presenter overlay payloads
// ---------------------------------------------------------------------------

export interface TeleprompterUpdate {
  points: string[];
  slide_context: string;
  elapsed: number;
}

export interface ObjectionCard {
  question: string;
  suggested_answer: string;
  persona?: string;
  difficulty: Severity;
}

export interface ObjectionPrepUpdate {
  questions: ObjectionCard[];
  elapsed: number;
}

export interface ScriptSuggestion {
  id: string;
  original: string;
  alternative: string;
  reason: string;
  agent: AgentType;
  elapsed: number;
}

// ---------------------------------------------------------------------------
// Generic live feed message (union of all WS message shapes)
// ---------------------------------------------------------------------------

export interface LiveFeedMessage {
  type: LiveMessageType;
  session_id?: string;
  mode?: SessionMode;
  // shared
  finding?: Finding;
  segments?: LiveTranscriptSegment[];
  agent?: AgentType;
  message?: string;
  suggestion?: string;
  severity?: Severity;
  elapsed?: number;
  // earpiece_cue
  text?: string;
  audio_b64?: string | null;
  priority?: Severity;
  category?: string;
  // teleprompter
  points?: string[];
  slide_context?: string;
  // objection_prep
  questions?: ObjectionCard[];
  // script_suggestion
  original?: string;
  alternative?: string;
  reason?: string;
}
