// TypeScript types matching backend api_schemas.py

export type Severity = 'info' | 'warning' | 'critical';
export type ClaimType = 'feature' | 'metric' | 'comparison' | 'privacy' | 'pricing' | 'security' | 'other';
export type AgentName = 'coach' | 'compliance' | 'persona';

export interface Claim {
  id: string;
  text: string;
  claim_type: ClaimType;
  timestamp: number;
  source: string;
  slide_number?: number;
  confidence: number;
}

export interface Finding {
  id: string;
  agent: AgentName;
  severity: Severity;
  title: string;
  detail: string;
  suggestion?: string;
  timestamp?: number;
  claim_id?: string;
  policy_reference?: string;
  persona?: string;
  live?: boolean;
  cue_hint?: string;
}

export interface PersonaQuestion {
  id: string;
  persona: string;
  question: string;
  follow_up?: string;
  timestamp?: number;
  difficulty: Severity;
}

export interface TimelineAnnotation {
  id: string;
  finding_id: string;
  category: string;
  timestamp: number;
  label: string;
  severity: Severity;
}

export interface DimensionScore {
  dimension: string;
  score: number;
  rationale: string;
}

export interface ReadinessScore {
  overall: number;
  dimensions: DimensionScore[];
  priority_fixes: string[];
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
  session_duration_seconds?: number;
  live_cues_count?: number;
  live_session_summary?: string;
}

// API response types

export type SessionStatus =
  | 'pending'
  | 'processing'
  | 'complete'
  | 'failed';

export interface StatusResponse {
  session_id: string;
  status: SessionStatus;
  progress: number;
  progress_message: string;
  error_message?: string;
}

export interface StartSessionResponse {
  session_id: string;
  status: SessionStatus;
  message: string;
}

// Persona definitions for UI configuration
export interface PersonaConfig {
  id: string;
  label: string;
  description: string;
  icon: string;
  enabled: boolean;
}
