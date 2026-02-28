// TypeScript types matching backend schemas.py

export type Severity = 'info' | 'warning' | 'critical';
export type ClaimType = 'product' | 'compliance_sensitive' | 'technical' | 'comparison' | 'general';
export type AgentName = 'coach' | 'compliance' | 'persona';
export type MarkerColor = 'red' | 'yellow' | 'blue' | 'purple';

export interface Finding {
  id: string;
  agent: AgentName;
  severity: Severity;
  category: string;
  title: string;
  description: string;
  timestamp?: number;
  slide_ref?: string;
  suggestion?: string;
  claim_text?: string;
  persona?: string;
}

export interface PersonaQuestion {
  id: string;
  persona: string;
  question: string;
  difficulty: 'easy' | 'medium' | 'hard';
  category: string;
  timestamp?: number;
  suggested_answer?: string;
}

export interface TimelineAnnotation {
  timestamp: number;
  category: string;
  color: MarkerColor;
  label: string;
  finding_id: string;
  agent: AgentName;
}

export interface DimensionScore {
  name: string;
  score: number;
  weight: number;
  issues_count: number;
  critical_count: number;
  summary: string;
}

export interface ReadinessReport {
  session_id: string;
  overall_score: number;
  grade: string;
  dimensions: Record<string, DimensionScore>;
  top_issues: Finding[];
  priority_fixes: string[];
  stakeholder_questions: PersonaQuestion[];
  findings: Finding[];
  timeline: TimelineAnnotation[];
  summary: string;
  agents_run: string[];
}

// API response types

export type SessionStatus =
  | 'pending'
  | 'processing'
  | 'extracting_frames'
  | 'transcribing'
  | 'extracting_claims'
  | 'running_agents'
  | 'scoring'
  | 'complete'
  | 'error';

export interface StatusResponse {
  session_id: string;
  status: SessionStatus;
  progress: number; // 0–100
  current_step: string;
  error?: string;
}

export interface StartSessionResponse {
  session_id: string;
  status: SessionStatus;
}

// Persona definitions for UI configuration
export interface PersonaConfig {
  id: string;
  label: string;
  description: string;
  icon: string;
  enabled: boolean;
}
