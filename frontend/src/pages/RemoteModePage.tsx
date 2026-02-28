/**
 * RemoteModePage — Live Remote Mode presenter-only overlay.
 *
 * Two-zone layout designed for screen-share presentations:
 *
 *   ┌───────────────────────┬─────────────────────────────────────┐
 *   │  ▶ AUDIENCE SEES THIS │  🔒 PRESENTER ONLY — NOT SHARED     │
 *   │                       │                                     │
 *   │   [webcam preview]    │  TELEPROMPTER                       │
 *   │                       │  · Talking point 1                  │
 *   │   ● REMOTE  00:04:12  │  · Talking point 2                  │
 *   │   8 findings          │  · Talking point 3                  │
 *   │                       ├─────────────────────────────────────┤
 *   │                       │  ACTIVE CUES (3)  [COMPLIANCE ▾] [≡]│
 *   │                       │  ■ 'Fully automated' conflicts...   │
 *   │   [transcript ticker] │  ▲ Pacing is fast — slow down       │
 *   │                       ├─────────────────────────────────────┤
 *   │                       │  OBJECTION PREP (2)   [expand all] │
 *   │                       │  ▸ Q: How is this different...      │
 *   │                       │  ▸ Q: What's the latency?          │
 *   └───────────────────────┴─────────────────────────────────────┘
 *
 *   + Script suggestion toasts (dismissable, float inside presenter panel)
 *   + Controls: compact toggle · filter by type · show/hide panel
 */

import { useEffect, useRef, useState } from 'react';
import {
  Monitor, Lock, StopCircle, AlertCircle, AlertTriangle, Info,
  ChevronDown, ChevronRight, X, Eye, EyeOff, AlignJustify,
  Minimize2, Filter, Clock, Radio, Zap, ArrowLeft,
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type {
  Finding, ObjectionCard, ScriptSuggestion, Severity,
} from '@/types';
import type { UseLiveSessionReturn } from '@/hooks/useLiveSession';

// ---------------------------------------------------------------------------
// Style tokens
// ---------------------------------------------------------------------------

const AGENT_STYLES: Record<string, { label: string; dot: string; badge: string; border: string }> = {
  coach:      { label: 'Coach',      dot: 'bg-accent-amber',  badge: 'bg-accent-amber text-bg-base', border: 'border-accent-amber' },
  compliance: { label: 'Compliance', dot: 'bg-accent-red',    badge: 'bg-accent-red text-bg-base',   border: 'border-accent-red' },
  persona:    { label: 'Persona',    dot: 'bg-accent-purple', badge: 'bg-accent-purple text-bg-base', border: 'border-accent-purple' },
};

const SEVERITY_GLYPH: Record<Severity, string> = {
  critical: '■',
  warning:  '▲',
  info:     '◆',
};

const SEVERITY_COLOR: Record<Severity, string> = {
  critical: 'text-accent-red',
  warning:  'text-accent-amber',
  info:     'text-text-muted',
};

const SEVERITY_BORDER: Record<Severity, string> = {
  critical: 'border-accent-red',
  warning:  'border-accent-amber',
  info:     'border-bg-border',
};

const DIFFICULTY_LABEL: Record<Severity, string> = {
  critical: 'HARD',
  warning:  'MEDIUM',
  info:     'EASY',
};

// ---------------------------------------------------------------------------
// Elapsed timer
// ---------------------------------------------------------------------------

function ElapsedTimer({ seconds }: { seconds: number }) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts = [
    h > 0 ? String(h).padStart(2, '0') : null,
    String(m).padStart(2, '0'),
    String(s).padStart(2, '0'),
  ].filter(Boolean);
  return (
    <span className="font-mono text-base text-text-secondary tabular-nums">
      <Clock size={14} className="inline mr-1.5 opacity-60" />
      {parts.join(':')}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Teleprompter strip
// ---------------------------------------------------------------------------

interface TeleprompterProps {
  points: string[];
  compact: boolean;
}

function TeleprompterSection({ points, compact }: TeleprompterProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when points update
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [points]);

  return (
    <div className="border-b-2 border-bg-border flex-shrink-0">
      <div className="px-4 py-2 bg-bg-elevated flex items-center justify-between border-b border-bg-border">
        <span className="font-display text-xl tracking-wider text-text-primary flex items-center gap-2.5">
          <Zap size={16} className="text-accent-amber" />
          TELEPROMPTER
        </span>
        {points.length > 0 && (
          <span className="font-mono text-xs text-accent-amber border border-accent-amber px-1.5 py-0.5">
            LIVE
          </span>
        )}
      </div>

      <div
        ref={containerRef}
        className={cn('overflow-y-auto px-3', compact ? 'py-2 max-h-20' : 'py-3 max-h-32')}
      >
        {points.length === 0 ? (
          <p className="font-mono text-sm text-text-muted italic">
            Waiting for first talking points<span className="animate-blink">_</span>
          </p>
        ) : (
          <ul className="space-y-2">
            {points.map((pt, i) => (
              <li
                key={`${i}-${pt.slice(0, 10)}`}
                className={cn(
                  'font-mono text-sm text-text-primary leading-snug flex items-start gap-2.5',
                  'animate-fade-up',
                )}
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <span className="text-accent-amber flex-shrink-0 mt-px">·</span>
                <span>{pt}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Script suggestion toast (inline, dismissable)
// ---------------------------------------------------------------------------

interface ScriptToastProps {
  suggestion: ScriptSuggestion;
  onDismiss: (id: string) => void;
}

function ScriptSuggestionToast({ suggestion, onDismiss }: ScriptToastProps) {
  const agent = AGENT_STYLES[suggestion.agent] ?? AGENT_STYLES['coach'];
  return (
    <div className={cn(
      'border-2 bg-bg-base shadow-brutal animate-fade-up',
      agent.border,
    )}>
      <div className="px-4 py-2.5 flex items-center justify-between gap-2.5 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <span className={cn('font-mono text-xs px-2 py-0.5 font-bold uppercase', agent.badge)}>
            {agent.label}
          </span>
          <span className="font-display text-base tracking-wider text-text-primary">SCRIPT SUGGESTION</span>
        </div>
        <button
          onClick={() => onDismiss(suggestion.id)}
          className="text-text-muted hover:text-accent-red transition-colors"
        >
          <X size={14} />
        </button>
      </div>
      <div className="px-4 py-2.5 space-y-2">
        <div className="flex gap-2.5 items-start">
          <span className="font-mono text-xs text-text-muted uppercase flex-shrink-0 mt-0.5">Instead:</span>
          <p className="font-mono text-sm text-text-muted line-through leading-snug">{suggestion.original}</p>
        </div>
        <div className="flex gap-2.5 items-start">
          <span className="font-mono text-xs text-accent-amber uppercase flex-shrink-0 mt-0.5">Say:</span>
          <p className="font-mono text-sm text-text-primary font-semibold leading-snug">{suggestion.alternative}</p>
        </div>
        {suggestion.reason && (
          <p className="font-mono text-xs text-text-muted leading-snug border-t border-bg-border pt-2">
            {suggestion.reason}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Active cue card
// ---------------------------------------------------------------------------

interface CueCardProps {
  finding: Finding;
  isNew: boolean;
  compact: boolean;
  onDismiss?: (id: string) => void;
}

function CueCard({ finding, isNew, compact, onDismiss }: CueCardProps) {
  const [open, setOpen] = useState(false);
  const agent = AGENT_STYLES[finding.agent] ?? AGENT_STYLES['coach'];
  const glyph = SEVERITY_GLYPH[finding.severity as Severity] ?? '◆';
  const glyphColor = SEVERITY_COLOR[finding.severity as Severity] ?? 'text-text-muted';
  const borderColor = SEVERITY_BORDER[finding.severity as Severity] ?? 'border-bg-border';
  const SevIcon = finding.severity === 'critical' ? AlertCircle
    : finding.severity === 'warning' ? AlertTriangle : Info;

  if (compact) {
    return (
      <div className={cn('flex items-center gap-2.5 px-4 py-2.5 border-b border-bg-border', isNew && 'animate-fade-up')}>
        <span className={cn('font-mono text-base flex-shrink-0', glyphColor)}>{glyph}</span>
        <span className={cn('font-mono text-xs px-1.5 py-0.5 font-bold uppercase', agent.badge)}>
          {agent.label[0]}
        </span>
        <p className="font-mono text-sm text-text-primary truncate flex-1">{finding.title}</p>
        {finding.timestamp !== undefined && (
          <span className="font-mono text-xs text-text-muted flex-shrink-0">{formatTime(finding.timestamp)}</span>
        )}
      </div>
    );
  }

  return (
    <div className={cn('border-2 bg-bg-base transition-all', borderColor, isNew && 'animate-fade-up shadow-brutal')}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left"
      >
        <SevIcon size={15} className={cn('flex-shrink-0 mt-0.5', glyphColor)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('font-mono text-xs px-1.5 py-0.5 font-bold uppercase', agent.badge)}>
              {agent.label}
            </span>
            {finding.live && (
              <span className="font-mono text-[10px] text-text-muted border border-bg-border px-1.5 py-0.5">live</span>
            )}
          </div>
          <p className="font-mono text-sm font-semibold text-text-primary leading-snug line-clamp-2">
            {finding.title}
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {finding.timestamp !== undefined && (
            <span className="font-mono text-xs text-text-muted tabular-nums">{formatTime(finding.timestamp)}</span>
          )}
          {onDismiss && (
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(finding.id); }}
              className="text-text-muted hover:text-accent-red transition-colors ml-1"
            >
              <X size={11} />
            </button>
          )}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-bg-border pt-2.5 space-y-2.5">
          <p className="font-mono text-sm text-text-secondary leading-relaxed">{finding.detail}</p>
          {finding.suggestion && (
            <div className="bg-bg-elevated border border-bg-border p-2.5">
              <span className="font-mono text-xs text-text-muted uppercase tracking-wider">Suggestion</span>
              <p className="font-mono text-sm text-text-primary leading-snug mt-1">{finding.suggestion}</p>
            </div>
          )}
          {finding.policy_reference && (
            <p className="font-mono text-xs text-accent-red">{finding.policy_reference}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Objection prep card
// ---------------------------------------------------------------------------

interface ObjectionCardProps {
  card: ObjectionCard & { id?: string };
  defaultOpen?: boolean;
}

function ObjectionPrepCard({ card, defaultOpen = false }: ObjectionCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const diffColor = card.difficulty === 'critical' ? 'text-accent-red border-accent-red'
    : card.difficulty === 'warning' ? 'text-accent-amber border-accent-amber'
    : 'text-text-muted border-text-muted';

  return (
    <div className="border-b border-bg-border last:border-b-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-bg-elevated transition-colors"
      >
        <span className="text-text-muted flex-shrink-0 mt-0.5">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 mb-1">
            {card.persona && (
              <span className="font-mono text-xs text-text-muted border border-bg-border px-1.5 truncate max-w-[120px]">
                {card.persona}
              </span>
            )}
            <span className={cn('font-mono text-[10px] border px-1.5 py-0.5 font-bold uppercase', diffColor)}>
              {DIFFICULTY_LABEL[card.difficulty as Severity] ?? 'MEDIUM'}
            </span>
          </div>
          <p className="font-mono text-sm text-text-primary leading-snug line-clamp-2">{card.question}</p>
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 bg-bg-elevated border-t border-bg-border">
          <div className="pt-2.5 space-y-2.5">
            <div>
              <span className="font-mono text-xs text-text-muted uppercase tracking-wider">Q:</span>
              <p className="font-mono text-sm text-text-secondary leading-snug mt-1 italic">{card.question}</p>
            </div>
            <div>
              <span className="font-mono text-xs text-accent-amber uppercase tracking-wider">Suggested Answer:</span>
              <p className="font-mono text-sm text-text-primary leading-snug mt-1">{card.suggested_answer}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type AgentFilter = 'all' | 'coach' | 'compliance' | 'persona';

interface Props extends UseLiveSessionReturn {
  onSessionComplete: () => void;
  onHome?: () => void;
}

export function RemoteModePage({
  state,
  findings,
  transcript,
  elapsedSeconds,
  mediaStream,
  teleprompterPoints,
  objections,
  scriptSuggestions,
  endSession,
  dismissScriptSuggestion,
  onSessionComplete,
  onHome,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const findingsFeedRef = useRef<HTMLDivElement>(null);
  const [newFindingIds, setNewFindingIds] = useState<Set<string>>(new Set());
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [showPresenterPanel, setShowPresenterPanel] = useState(true);
  const [compact, setCompact] = useState(false);
  const [agentFilter, setAgentFilter] = useState<AgentFilter>('all');
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const prevFindingsLen = useRef(0);

  // Attach mediaStream
  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream]);

  // Track new findings for animations
  useEffect(() => {
    if (findings.length > prevFindingsLen.current) {
      const newIds = new Set(
        findings.slice(0, findings.length - prevFindingsLen.current).map((f) => f.id),
      );
      setNewFindingIds(newIds);
      setTimeout(() => setNewFindingIds(new Set()), 2500);
      if (findingsFeedRef.current) {
        findingsFeedRef.current.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
    prevFindingsLen.current = findings.length;
  }, [findings]);

  // Transition to results when complete
  useEffect(() => {
    if (state === 'complete') {
      onSessionComplete();
    }
  }, [state, onSessionComplete]);

  const handleEndClick = () => {
    if (showEndConfirm) {
      setShowEndConfirm(false);
      endSession();
    } else {
      setShowEndConfirm(true);
      setTimeout(() => setShowEndConfirm(false), 3000);
    }
  };

  const dismissCue = (id: string) => setDismissedIds((prev) => new Set([...prev, id]));

  const visibleFindings = findings
    .filter((f) => !dismissedIds.has(f.id))
    .filter((f) => agentFilter === 'all' || f.agent === agentFilter);

  const recentTranscript = transcript.slice(-3);
  const criticalFinding = findings.find((f) => f.severity === 'critical');

  const agentCounts = {
    all: findings.filter((f) => !dismissedIds.has(f.id)).length,
    coach: findings.filter((f) => f.agent === 'coach' && !dismissedIds.has(f.id)).length,
    compliance: findings.filter((f) => f.agent === 'compliance' && !dismissedIds.has(f.id)).length,
    persona: findings.filter((f) => f.agent === 'persona' && !dismissedIds.has(f.id)).length,
  };

  return (
    <div className="h-screen bg-bg-base flex flex-col overflow-hidden">

      {/* ── Global header ── */}
      <header className="border-b-4 border-bg-border px-6 py-3.5 flex items-center justify-between flex-shrink-0 bg-bg-surface">
        <div className="flex items-center gap-5">
          {onHome && (
            <button
              onClick={onHome}
              className="flex items-center gap-1.5 px-3 py-2 font-mono text-sm border-2 border-bg-border text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors"
            >
              <ArrowLeft size={14} />
              <span className="hidden sm:inline uppercase tracking-wider">Home</span>
            </button>
          )}
          <div className="flex items-center gap-2.5">
            <Monitor size={16} className="text-text-primary" strokeWidth={2.5} />
            <span className="font-display text-3xl tracking-wider text-text-primary">P<span className="italic">ITCH</span><span className="ml-4">PILOT</span></span>
          </div>
          <div className="w-px h-5 bg-bg-border" />
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-accent-red animate-pulse" />
            <span className="font-mono text-sm text-accent-red tracking-widest uppercase font-bold">Remote</span>
          </span>
          <ElapsedTimer seconds={elapsedSeconds} />
        </div>

        <div className="flex items-center gap-4">
          <span className="font-mono text-sm text-text-muted">
            {findings.length} finding{findings.length !== 1 ? 's' : ''}
          </span>
          {/* Toggle presenter panel */}
          <button
            onClick={() => setShowPresenterPanel((v) => !v)}
            title={showPresenterPanel ? 'Hide presenter panel' : 'Show presenter panel'}
            className="flex items-center gap-2 px-3 py-2 font-mono text-sm border-2 border-bg-border hover:bg-bg-elevated transition-colors"
          >
            {showPresenterPanel ? <EyeOff size={14} /> : <Eye size={14} />}
            <span className="hidden sm:inline">{showPresenterPanel ? 'Hide' : 'Show'} overlay</span>
          </button>
          <button
            onClick={handleEndClick}
            className={cn(
              'flex items-center gap-2 px-5 py-2 font-mono text-sm font-bold uppercase tracking-wider border-2 transition-all duration-150',
              showEndConfirm
                ? 'bg-accent-red text-bg-base border-accent-red shadow-brutal-red'
                : 'bg-bg-base border-bg-border text-text-secondary hover:border-accent-red hover:text-accent-red',
            )}
          >
            <StopCircle size={14} />
            {showEndConfirm ? 'Confirm End' : 'End Session'}
          </button>
        </div>
      </header>

      {/* ── Main content ── */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* ── LEFT ZONE: Shared-safe screen area ── */}
        <div className={cn(
          'flex flex-col overflow-hidden border-r-4 border-bg-border relative',
          showPresenterPanel ? 'flex-1' : 'flex-1',
        )}>
          {/* Zone badge */}
          <div className="px-5 py-2 bg-bg-elevated border-b-2 border-bg-border flex items-center gap-2.5 flex-shrink-0">
            <span className="w-2.5 h-2.5 border-2 border-text-primary bg-text-primary" />
            <span className="font-mono text-xs font-bold uppercase tracking-widest text-text-secondary">
              Audience Sees This
            </span>
            <span className="font-mono text-xs text-text-muted">— share this window in your meeting</span>
          </div>

          {/* Video / placeholder */}
          <div className="flex-1 bg-[#1A1A1A] flex items-center justify-center relative overflow-hidden">
            {mediaStream ? (
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center gap-5 text-center px-8">
                <div className="w-32 h-32 border-2 border-[#3A3A3A] flex items-center justify-center">
                  <Radio size={48} className="text-[#3A3A3A]" />
                </div>
                <div className="space-y-1.5">
                  <p className="font-mono text-sm text-[#666] uppercase tracking-widest">Demo Mode — No Camera</p>
                  <p className="font-mono text-xs text-[#555]">
                    In production, your webcam appears here.<br />
                    Share only this left panel in your meeting.
                  </p>
                </div>
                <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-10">
                  <div className="h-0.5 w-full bg-accent-red animate-scan" />
                </div>
              </div>
            )}

            {/* Critical alert banner on video */}
            {criticalFinding && !dismissedIds.has(criticalFinding.id) && (
              <div className="absolute bottom-6 left-6 right-6 border-2 border-accent-red bg-bg-base/95 px-4 py-3 shadow-brutal-red flex items-start gap-2.5">
                <AlertCircle size={16} className="text-accent-red flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="font-mono text-xs font-bold text-accent-red uppercase">Critical</p>
                  <p className="text-sm text-text-primary leading-snug truncate">{criticalFinding.title}</p>
                </div>
              </div>
            )}
          </div>

          {/* Transcript ticker */}
          <div className="border-t-2 border-bg-border bg-bg-surface px-5 py-3 flex-shrink-0 min-h-[64px]">
            <div className="flex items-center gap-2.5 mb-1.5">
              <span className="font-mono text-xs text-text-muted uppercase tracking-widest">Transcript</span>
              <span className="w-1.5 h-1.5 bg-accent-red animate-pulse" />
            </div>
            <div className="overflow-hidden max-h-[48px]">
              {recentTranscript.length === 0 ? (
                <p className="font-mono text-sm text-text-muted italic">
                  Waiting for speech<span className="animate-blink">_</span>
                </p>
              ) : (
                recentTranscript.map((seg, i) => (
                  <p
                    key={`${seg.start_time}-${i}`}
                    className={cn(
                      'font-mono text-sm leading-snug truncate',
                      i === recentTranscript.length - 1 ? 'text-text-primary' : 'text-text-muted',
                    )}
                  >
                    {seg.text}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── RIGHT ZONE: Presenter-only overlay ── */}
        {showPresenterPanel && (
          <div className={cn(
            'flex flex-col overflow-hidden flex-shrink-0 bg-bg-surface',
            compact ? 'w-72' : 'w-[480px]',
          )}>

            {/* Presenter badge + controls */}
            <div className="px-4 py-2.5 border-b-2 border-bg-border flex items-center justify-between gap-2.5 flex-shrink-0 bg-bg-elevated">
              <div className="flex items-center gap-2.5">
                <Lock size={12} className="text-accent-purple flex-shrink-0" />
                <span className="font-mono text-xs font-bold uppercase tracking-widest text-accent-purple">
                  Presenter Only
                </span>
                <span className="font-mono text-[10px] text-text-muted border border-text-muted px-1.5 hidden sm:inline">
                  not shared
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {/* Compact toggle */}
                <button
                  onClick={() => setCompact((v) => !v)}
                  title={compact ? 'Expand view' : 'Compact view'}
                  className="p-1.5 border border-bg-border hover:bg-bg-base transition-colors"
                >
                  {compact ? <AlignJustify size={12} /> : <Minimize2 size={12} />}
                </button>
              </div>
            </div>

            {/* Teleprompter */}
            <TeleprompterSection points={teleprompterPoints} compact={compact} />

            {/* Active cues section */}
            <div className="flex flex-col min-h-0 flex-1 border-b-2 border-bg-border overflow-hidden">
              <div className="px-4 py-2 bg-bg-elevated border-b border-bg-border flex items-center justify-between gap-2.5 flex-shrink-0">
                <span className="font-display text-xl tracking-wider text-text-primary">
                  ACTIVE CUES
                  <span className="font-mono text-sm text-text-muted font-normal ml-2">({visibleFindings.length})</span>
                </span>
                {/* Agent filter */}
                <div className="flex items-center gap-1">
                  <Filter size={11} className="text-text-muted mr-1.5" />
                  {(['all', 'coach', 'compliance', 'persona'] as const).map((agent) => (
                    <button
                      key={agent}
                      onClick={() => setAgentFilter(agent)}
                      className={cn(
                        'font-mono text-[10px] px-2 py-0.5 uppercase border transition-colors',
                        agentFilter === agent
                          ? agent === 'all' ? 'bg-bg-border text-bg-base border-bg-border'
                            : agent === 'coach' ? 'bg-accent-amber text-bg-base border-accent-amber'
                            : agent === 'compliance' ? 'bg-accent-red text-bg-base border-accent-red'
                            : 'bg-accent-purple text-bg-base border-accent-purple'
                          : 'bg-bg-surface text-text-muted border-bg-border hover:bg-bg-base',
                      )}
                    >
                      {agent === 'all' ? `${agentCounts.all}` : agent[0].toUpperCase()}
                      {agent !== 'all' && agentCounts[agent] > 0 && (
                        <span className="ml-0.5">{agentCounts[agent]}</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Script suggestion toasts (inline at top of cues) */}
              {scriptSuggestions.length > 0 && !compact && (
                <div className="px-2 pt-2 space-y-2 border-b border-bg-border flex-shrink-0">
                  {scriptSuggestions.slice(0, 2).map((s) => (
                    <ScriptSuggestionToast
                      key={s.id}
                      suggestion={s}
                      onDismiss={dismissScriptSuggestion}
                    />
                  ))}
                </div>
              )}

              <div ref={findingsFeedRef} className="overflow-y-auto flex-1">
                {compact ? (
                  <div className="divide-y divide-bg-border">
                    {visibleFindings.map((f) => (
                      <CueCard
                        key={f.id}
                        finding={f}
                        isNew={newFindingIds.has(f.id)}
                        compact
                      />
                    ))}
                    {visibleFindings.length === 0 && (
                      <p className="px-4 py-5 font-mono text-sm text-text-muted text-center">No findings yet</p>
                    )}
                  </div>
                ) : (
                  <div className="p-2 space-y-2">
                    {visibleFindings.map((f) => (
                      <CueCard
                        key={f.id}
                        finding={f}
                        isNew={newFindingIds.has(f.id)}
                        compact={false}
                        onDismiss={dismissCue}
                      />
                    ))}
                    {visibleFindings.length === 0 && (
                      <div className="py-10 flex flex-col items-center gap-4 text-center">
                        <div className="w-14 h-14 border-2 border-bg-border flex items-center justify-center">
                          <Radio size={24} className="text-text-muted" />
                        </div>
                        <p className="font-mono text-sm text-text-muted leading-relaxed">
                          Listening for claims…<br />
                          Cues will appear as you speak.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Objection prep */}
            <div className="flex flex-col flex-shrink-0 overflow-hidden" style={{ maxHeight: compact ? '140px' : '260px' }}>
              <div className="px-4 py-2 bg-bg-elevated border-b border-bg-border flex items-center justify-between flex-shrink-0">
                <span className="font-display text-xl tracking-wider text-text-primary">
                  OBJECTION PREP
                  <span className="font-mono text-sm text-text-muted font-normal ml-2">({objections.length})</span>
                </span>
                {objections.length === 0 && (
                  <span className="font-mono text-xs text-text-muted italic">building…</span>
                )}
              </div>

              <div className="overflow-y-auto flex-1">
                {objections.length === 0 ? (
                  <p className="px-4 py-4 font-mono text-sm text-text-muted italic text-center">
                    Likely questions will appear as the session progresses
                  </p>
                ) : (
                  <div>
                    {objections.map((card, i) => (
                      <ObjectionPrepCard
                        key={(card as ObjectionCard & { id?: string }).id ?? `obj-${i}`}
                        card={card}
                        defaultOpen={i === 0 && !compact}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Finalizing indicator */}
            {state === 'finalizing' && (
              <div className="border-t-2 border-bg-border px-5 py-4 bg-bg-surface flex items-center gap-2.5 flex-shrink-0">
                <div className="w-2.5 h-2.5 bg-accent-red animate-pulse flex-shrink-0" />
                <p className="font-mono text-sm text-text-secondary">Building readiness report…</p>
              </div>
            )}
          </div>
        )}

        {/* Hidden-panel compact cue rail */}
        {!showPresenterPanel && findings.filter((f) => !dismissedIds.has(f.id)).length > 0 && (
          <div className="w-10 flex-shrink-0 bg-bg-surface border-l-2 border-bg-border flex flex-col items-center py-3 gap-2">
            <Lock size={12} className="text-accent-purple mb-1" />
            {findings.filter((f) => !dismissedIds.has(f.id)).slice(0, 8).map((f) => {
              const glyph = SEVERITY_GLYPH[f.severity as Severity] ?? '◆';
              const color = SEVERITY_COLOR[f.severity as Severity];
              return (
                <span key={f.id} title={f.title} className={cn('font-mono text-base cursor-default', color)}>
                  {glyph}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
