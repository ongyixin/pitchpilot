/**
 * AnalysisResults — Three-panel results view.
 *
 * Layout:
 *   ┌──────────────────────┬─────────────────────────┐
 *   │  Video / Score       │  Agent Findings (tabbed) │
 *   └──────────────────────┴─────────────────────────┘
 *   │  Timeline (full width)                          │
 *   └─────────────────────────────────────────────────┘
 *   │  Priority fixes  │  Persona Questions           │
 *   └──────────────────┴──────────────────────────────┘
 *
 * Data adaptation:
 *   This component accepts ReadinessReport from src/types/index.ts (which
 *   matches the backend API schema) and adapts it for the existing UI
 *   components that were built against the src/types/api.ts schema.
 */

import { useRef, useState, useCallback } from 'react';
import type { ReadinessReport, TimelineAnnotation, Finding, PersonaQuestion } from '@/types';
import type { TimelineMarker } from './Timeline';
import { Timeline } from './Timeline';
import { FindingsPanel } from './FindingsPanel';
import { ReadinessScore } from './ReadinessScore';
import type { ReadinessReport as ApiReport, Finding as ApiFinding } from '@/types/api';
import { cn, formatTime } from '@/lib/utils';
import { AlertCircle, AlertTriangle, Info, ChevronRight, Clock, User } from 'lucide-react';

interface Props {
  report: ReadinessReport;
  /** Timeline annotations from /api/session/{id}/timeline */
  timeline: TimelineAnnotation[];
}

// ---------------------------------------------------------------------------
// Data adapters (index.ts → api.ts shapes for existing components)
// ---------------------------------------------------------------------------

function scoreToGrade(score: number): string {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B+';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C';
  if (score >= 50) return 'D';
  return 'F';
}

function adaptReportForScoreComponent(report: ReadinessReport): ApiReport {
  const criticals = report.findings.filter((f) => f.severity === 'critical').length;
  const warnings = report.findings.filter((f) => f.severity === 'warning').length;

  const dimensions = Object.fromEntries(
    report.score.dimensions.map((d) => [
      d.dimension.toLowerCase(),
      {
        name: d.dimension,
        score: d.score,
        weight: 0.25,
        issues_count: warnings + criticals,
        critical_count: criticals,
        summary: d.rationale,
      },
    ])
  );

  return {
    session_id: String(report.session_id),
    overall_score: report.score.overall,
    grade: scoreToGrade(report.score.overall),
    dimensions,
    agents_run: [...new Set(report.findings.map((f) => f.agent))],
    top_issues: [],
    priority_fixes: report.score.priority_fixes,
    stakeholder_questions: [],
    findings: [],
    timeline: [],
    summary: report.summary,
  };
}

function adaptFindingsForPanel(findings: Finding[]): ApiFinding[] {
  return findings.map((f) => ({
    id: f.id,
    agent: f.agent,
    severity: f.severity,
    category: f.agent, // api.ts finding has category
    title: f.title,
    description: f.detail, // index.ts has 'detail', api.ts has 'description'
    timestamp: f.timestamp,
    suggestion: f.suggestion,
    claim_text: undefined,
    slide_ref: undefined,
    persona: f.persona,
  }));
}

function adaptTimelineMarkers(
  timeline: TimelineAnnotation[],
  findings: Finding[]
): TimelineMarker[] {
  // Try to use the timeline from the API; fall back to deriving from findings
  if (timeline.length > 0) {
    return timeline.map((t) => ({
      id: t.id,
      finding_id: t.finding_id,
      timestamp: t.timestamp,
      label: t.label,
      severity: t.severity,
      category: t.category,
    }));
  }
  // Fallback: derive from findings
  return findings
    .filter((f) => f.timestamp > 0)
    .sort((a, b) => a.timestamp - b.timestamp)
    .map((f) => ({
      id: f.id,
      finding_id: f.id,
      timestamp: f.timestamp,
      label: f.title,
      severity: f.severity,
      category: f.agent,
    }));
}

// ---------------------------------------------------------------------------
// Priority Fixes panel
// ---------------------------------------------------------------------------

function PriorityFixes({ fixes }: { fixes: string[] }) {
  return (
    <div className="bg-bg-surface border border-bg-border rounded-md p-4 space-y-3">
      <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
        Priority Fixes
      </span>
      <ol className="space-y-2">
        {fixes.map((fix, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-accent-red/10 border border-accent-red/30 text-accent-red font-mono text-xs flex items-center justify-center mt-0.5">
              {i + 1}
            </span>
            <p className="text-sm text-text-secondary leading-relaxed">{fix}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Persona Questions panel
// ---------------------------------------------------------------------------

const DIFFICULTY_STYLE: Record<string, string> = {
  critical: 'text-accent-red border-accent-red/30 bg-accent-red/5',
  warning: 'text-accent-amber border-accent-amber/30 bg-accent-amber/5',
  info: 'text-accent-blue border-accent-blue/30 bg-accent-blue/5',
};

const DIFFICULTY_LABEL: Record<string, string> = {
  critical: 'hard',
  warning: 'medium',
  info: 'easy',
};

function PersonaQuestions({
  questions,
  onSeek,
}: {
  questions: PersonaQuestion[];
  onSeek?: (ts: number) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const personas = [...new Set(questions.map((q) => q.persona))];
  const [activePersona, setActivePersona] = useState<string | null>(null);

  const filtered = activePersona ? questions.filter((q) => q.persona === activePersona) : questions;

  return (
    <div className="bg-bg-surface border border-bg-border rounded-md flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-bg-border flex items-center justify-between flex-shrink-0">
        <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
          Stakeholder Questions
        </span>
        <span className="font-mono text-xs text-text-secondary">{questions.length} questions</span>
      </div>

      {/* Persona filter */}
      <div className="flex gap-1 px-4 py-2 border-b border-bg-border overflow-x-auto flex-shrink-0">
        <button
          onClick={() => setActivePersona(null)}
          className={cn(
            'px-2.5 py-1 rounded-sm text-xs font-mono transition-colors whitespace-nowrap',
            !activePersona
              ? 'bg-bg-elevated text-text-primary'
              : 'text-text-muted hover:text-text-secondary'
          )}
        >
          All
        </button>
        {personas.map((p) => (
          <button
            key={p}
            onClick={() => setActivePersona(activePersona === p ? null : p)}
            className={cn(
              'px-2.5 py-1 rounded-sm text-xs font-mono transition-colors whitespace-nowrap',
              activePersona === p
                ? 'bg-bg-elevated text-text-primary'
                : 'text-text-muted hover:text-text-secondary'
            )}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Questions list */}
      <div className="overflow-y-auto flex-1 divide-y divide-bg-border">
        {filtered.map((q) => {
          const isExpanded = expanded === q.id;
          const diffStyle = DIFFICULTY_STYLE[q.difficulty] ?? DIFFICULTY_STYLE.warning;

          return (
            <div key={q.id}>
              <div
                className="px-4 py-3 cursor-pointer hover:bg-bg-elevated flex items-start gap-3"
                onClick={() => {
                  setExpanded(isExpanded ? null : q.id);
                  if (q.timestamp) onSeek?.(q.timestamp);
                }}
              >
                <User size={13} className="text-accent-purple flex-shrink-0 mt-0.5" strokeWidth={2} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-text-primary leading-snug font-medium">
                      {q.question}
                    </p>
                    <ChevronRight
                      size={12}
                      className={cn(
                        'text-text-muted flex-shrink-0 mt-0.5 transition-transform',
                        isExpanded && 'rotate-90'
                      )}
                    />
                  </div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className={cn('text-xs px-1.5 py-0.5 rounded-sm border font-mono', diffStyle)}>
                      {DIFFICULTY_LABEL[q.difficulty] ?? q.difficulty}
                    </span>
                    <span className="text-xs text-text-muted font-mono">{q.persona}</span>
                    {q.timestamp !== undefined && (
                      <span className="text-xs text-text-muted flex items-center gap-1">
                        <Clock size={9} />
                        {formatTime(q.timestamp)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {isExpanded && q.follow_up && (
                <div className="px-4 pb-4 bg-bg-elevated border-t border-bg-border">
                  <p className="text-xs text-text-muted italic pt-3">Follow-up: {q.follow_up}</p>
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="py-10 text-center">
            <p className="text-sm text-text-muted">No questions from this persona.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Video placeholder (no src available in demo/upload flow)
// ---------------------------------------------------------------------------

function VideoPlaceholder({
  filename,
  onSeek,
  currentTime,
}: {
  filename?: string;
  onSeek?: (ts: number) => void;
  currentTime?: number;
}) {
  return (
    <div className="bg-bg-surface border border-bg-border rounded-md p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
          Rehearsal Recording
        </span>
        {filename && (
          <span className="font-mono text-xs text-text-secondary truncate max-w-[200px]">
            {filename}
          </span>
        )}
      </div>
      <div className="aspect-video bg-bg-elevated rounded-sm border border-bg-border flex flex-col items-center justify-center gap-2">
        <div className="text-3xl opacity-30">▶</div>
        <p className="text-xs text-text-muted text-center px-4">
          Video playback is available when running with a real recording.
          <br />
          Timeline markers are linked to timestamps.
        </p>
      </div>
      {currentTime !== undefined && (
        <p className="font-mono text-xs text-text-secondary text-right">
          {formatTime(currentTime)}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AnalysisResults({ report, timeline }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState<number>(0);

  const adaptedReport = adaptReportForScoreComponent(report);
  const adaptedFindings = adaptFindingsForPanel(report.findings);
  const markers = adaptTimelineMarkers(timeline, report.findings);

  // Estimate video duration from last timeline marker
  const videoDuration =
    markers.length > 0 ? Math.max(...markers.map((m) => m.timestamp)) * 1.15 : 360;

  const handleSeek = useCallback(
    (timestamp: number, findingId?: string) => {
      setCurrentTime(timestamp);
      if (findingId) setActiveFindingId(findingId);
      if (videoRef.current) {
        videoRef.current.currentTime = timestamp;
        videoRef.current.play().catch(() => {});
      }
    },
    []
  );

  const handleFindingSelect = useCallback((finding: ApiFinding) => {
    setActiveFindingId(finding.id);
    if (finding.timestamp !== undefined) {
      setCurrentTime(finding.timestamp);
      if (videoRef.current) {
        videoRef.current.currentTime = finding.timestamp;
      }
    }
  }, []);

  return (
    <div className="flex flex-col gap-4 p-4 h-full animate-fade-up">
      {/* Top two-panel row */}
      <div className="grid grid-cols-5 gap-4" style={{ minHeight: '380px' }}>
        {/* Left: video + score */}
        <div className="col-span-2 flex flex-col gap-4">
          <VideoPlaceholder
            filename={undefined}
            onSeek={handleSeek}
            currentTime={currentTime}
          />
          <ReadinessScore report={adaptedReport} />
        </div>

        {/* Right: findings panel */}
        <div className="col-span-3 h-full">
          <FindingsPanel
            findings={adaptedFindings}
            onSelectFinding={handleFindingSelect}
            activeTimestamp={currentTime}
          />
        </div>
      </div>

      {/* Timeline */}
      <Timeline
        markers={markers}
        duration={videoDuration}
        onSeek={(ts, fid) => handleSeek(ts, fid)}
        activeFindingId={activeFindingId}
      />

      {/* Bottom row */}
      <div className="grid grid-cols-2 gap-4">
        <PriorityFixes fixes={report.score.priority_fixes} />
        <PersonaQuestions
          questions={report.persona_questions}
          onSeek={(ts) => handleSeek(ts)}
        />
      </div>

      {/* Summary */}
      <div className="bg-bg-surface border border-bg-border rounded-md p-4">
        <p className="font-mono text-xs text-text-muted uppercase tracking-widest mb-2">
          Executive Summary
        </p>
        <p className="text-sm text-text-secondary leading-relaxed">{report.summary}</p>
      </div>
    </div>
  );
}
