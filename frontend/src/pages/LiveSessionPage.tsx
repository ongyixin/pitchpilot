/**
 * LiveSessionPage — the real-time copilot interface.
 *
 * Layout:
 *   ┌─────────────────────────────────────┐
 *   │ Header: timer · REC indicator · End │
 *   ├─────────────────┬───────────────────┤
 *   │  Video preview  │  Live findings    │
 *   │  (webcam/screen)│  feed (scrollable)│
 *   ├─────────────────┴───────────────────┤
 *   │  Transcript ticker (last N segments)│
 *   └─────────────────────────────────────┘
 *   + Nudge toasts (bottom-right, auto-dismiss)
 *   + Critical finding overlay (on video)
 */

import { useEffect, useRef, useState } from 'react';
import {
  Radio, StopCircle, AlertCircle, AlertTriangle, Info,
  Mic, Clock, ChevronDown, X, ArrowLeft,
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type { Finding, LiveNudge, Severity } from '@/types';
import type { UseLiveSessionReturn } from '@/hooks/useLiveSession';

// ---------------------------------------------------------------------------
// Agent style tokens
// ---------------------------------------------------------------------------

const AGENT_STYLES: Record<string, { label: string; dot: string; badge: string }> = {
  coach:      { label: 'Coach',      dot: 'bg-accent-amber',  badge: 'border-accent-amber/50 text-accent-amber' },
  compliance: { label: 'Compliance', dot: 'bg-accent-red',    badge: 'border-accent-red/50 text-accent-red' },
  persona:    { label: 'Persona',    dot: 'bg-accent-purple', badge: 'border-accent-purple/50 text-accent-purple' },
};

const SEVERITY_ICON: Record<Severity, typeof AlertCircle> = {
  critical: AlertCircle,
  warning:  AlertTriangle,
  info:     Info,
};


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RecordingDot() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="w-2.5 h-2.5 rounded-full bg-accent-red animate-pulse" />
      <span className="font-mono text-sm text-accent-red tracking-widest uppercase">Live</span>
    </span>
  );
}

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
      <Clock size={16} className="inline mr-1.5 opacity-60" />
      {parts.join(':')}
    </span>
  );
}

interface FindingCardProps {
  finding: Finding;
  isNew?: boolean;
}

function FindingCard({ finding, isNew }: FindingCardProps) {
  const [open, setOpen] = useState(false);
  const agent = AGENT_STYLES[finding.agent] ?? AGENT_STYLES['coach'];
  const SevIcon = SEVERITY_ICON[finding.severity as Severity] ?? Info;

  return (
    <div
      className={cn(
        'border bg-bg-base transition-all duration-300',
        isNew ? 'animate-fade-up shadow-brutal' : 'shadow-brutal-sm',
        finding.severity === 'critical'
          ? 'border-accent-red'
          : finding.severity === 'warning'
          ? 'border-accent-amber'
          : 'border-bg-border',
      )}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left"
      >
        <SevIcon
          size={16}
          className={cn(
            'flex-shrink-0 mt-0.5',
            finding.severity === 'critical' ? 'text-accent-red'
            : finding.severity === 'warning' ? 'text-accent-amber'
            : 'text-accent-blue',
          )}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('text-xs font-mono font-bold uppercase border px-1.5 py-0.5 leading-tight', agent.badge)}>
              {agent.label}
            </span>
            {finding.live && (
              <span className="text-[10px] font-mono text-text-muted uppercase border border-bg-border px-1.5 py-0.5">
                live
              </span>
            )}
          </div>
          <p className="text-sm font-mono font-semibold text-text-primary leading-snug line-clamp-2">
            {finding.title}
          </p>
        </div>
        <span className="font-mono text-xs text-text-muted flex-shrink-0 mt-0.5 tabular-nums">
          {formatTime(finding.timestamp)}
        </span>
        <ChevronDown
          size={14}
          className={cn('flex-shrink-0 mt-0.5 text-text-muted transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-bg-border space-y-2.5 pt-2.5">
          <p className="text-sm text-text-secondary leading-relaxed">{finding.detail}</p>
          {finding.suggestion && (
            <div className="flex gap-2.5 pt-1.5">
              <span className="font-mono text-xs text-text-muted uppercase flex-shrink-0">Fix:</span>
              <p className="text-sm text-text-primary leading-relaxed">{finding.suggestion}</p>
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

interface NudgeToastProps {
  nudge: LiveNudge;
  onDismiss: (id: string) => void;
}

function NudgeToast({ nudge, onDismiss }: NudgeToastProps) {
  const agent = AGENT_STYLES[nudge.agent] ?? AGENT_STYLES['coach'];

  return (
    <div
      className={cn(
        'w-80 border bg-bg-base shadow-brutal animate-fade-up flex gap-3 p-4',
        nudge.severity === 'critical' ? 'border-accent-red' : 'border-accent-amber',
      )}
    >
      <div className={cn('w-2 flex-shrink-0 self-stretch', agent.dot)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className={cn('text-xs font-mono font-bold uppercase border px-1.5 py-0.5 leading-tight', agent.badge)}>
            {agent.label}
          </span>
          <button onClick={() => onDismiss(nudge.id)} className="text-text-muted hover:text-accent-red transition-colors">
            <X size={12} />
          </button>
        </div>
        <p className="text-sm text-text-primary leading-snug">{nudge.message}</p>
        {nudge.suggestion && (
          <p className="text-xs text-text-muted mt-1.5 leading-snug">{nudge.suggestion}</p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

interface Props extends UseLiveSessionReturn {
  onSessionComplete: () => void;
  onHome?: () => void;
}

export function LiveSessionPage({
  state,
  findings,
  nudges,
  transcript,
  elapsedSeconds,
  mediaStream,
  endSession,
  dismissNudge,
  onSessionComplete,
  onHome,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const findingsFeedRef = useRef<HTMLDivElement>(null);
  const [newFindingIds, setNewFindingIds] = useState<Set<string>>(new Set());
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const prevFindingsLen = useRef(0);

  // Attach mediaStream to video element
  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream]);

  // Track newly arrived findings for animation
  useEffect(() => {
    if (findings.length > prevFindingsLen.current) {
      const newIds = new Set(
        findings.slice(0, findings.length - prevFindingsLen.current).map((f) => f.id),
      );
      setNewFindingIds(newIds);
      setTimeout(() => setNewFindingIds(new Set()), 2000);

      // Auto-scroll findings feed
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

  const criticalFindings = findings.filter((f) => f.severity === 'critical').slice(0, 1);
  const recentTranscript = transcript.slice(-3);

  const handleEndClick = () => {
    if (showEndConfirm) {
      setShowEndConfirm(false);
      endSession();
    } else {
      setShowEndConfirm(true);
      setTimeout(() => setShowEndConfirm(false), 3000);
    }
  };

  return (
    <div className="h-screen bg-bg-base flex flex-col overflow-hidden">

      {/* ── Header ── */}
      <header className="border-b-2 border-bg-border px-8 py-4 flex items-center justify-between flex-shrink-0 bg-bg-surface">
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
            <Mic size={18} className="text-text-primary" strokeWidth={2.5} />
            <span className="font-mono text-sm font-bold tracking-wider uppercase text-text-primary">
              P<span className="italic">itch</span><span className="ml-4">Pilot</span>
            </span>
          </div>
          <div className="w-px h-5 bg-bg-border" />
          <RecordingDot />
        </div>

        <div className="flex items-center gap-8">
          <ElapsedTimer seconds={elapsedSeconds} />
          <div className="flex items-center gap-2.5 font-mono text-sm text-text-muted">
            <span>{findings.length} findings</span>
          </div>
          <button
            onClick={handleEndClick}
            className={cn(
              'flex items-center gap-2 px-5 py-2 font-mono text-sm font-bold uppercase tracking-wider border-2 transition-all duration-150',
              showEndConfirm
                ? 'bg-accent-red text-white border-accent-red shadow-brutal-red'
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

        {/* Left: Video preview */}
        <div className="flex-1 flex flex-col overflow-hidden border-r-2 border-bg-border relative min-w-0">
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
              /* Mock mode placeholder */
              <div className="flex flex-col items-center gap-5 text-text-muted">
                <div className="w-32 h-32 border-2 border-[#3A3A3A] flex items-center justify-center">
                  <Radio size={48} className="text-[#3A3A3A]" />
                </div>
                <div className="space-y-1.5 text-center">
                  <p className="font-mono text-sm text-[#666] uppercase tracking-widest">
                    Demo Mode — No Camera
                  </p>
                  <p className="font-mono text-xs text-[#555]">
                    In production, your webcam preview appears here
                  </p>
                </div>
                {/* Scan line animation */}
                <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-10">
                  <div className="h-0.5 w-full bg-accent-red animate-scan" style={{ top: '50%' }} />
                </div>
              </div>
            )}

            {/* Critical finding overlay — brief banner on the video */}
            {criticalFindings.length > 0 && (
              <div className="absolute bottom-6 left-6 right-6">
                {criticalFindings.map((f) => (
                  <div
                    key={f.id}
                    className="flex items-start gap-2.5 border-2 border-accent-red bg-bg-base/95 px-4 py-3 shadow-brutal-red"
                  >
                    <AlertCircle size={16} className="text-accent-red flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="font-mono text-xs font-bold text-accent-red uppercase">Critical</p>
                      <p className="text-sm text-text-primary leading-snug truncate">{f.title}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Transcript ticker */}
          <div className="border-t-2 border-bg-border bg-bg-surface px-5 py-3 flex-shrink-0 min-h-[64px]">
            <div className="flex items-center gap-2.5 mb-1.5">
              <span className="font-mono text-xs text-text-muted uppercase tracking-widest">Transcript</span>
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
            </div>
            <div className="space-y-1 overflow-hidden max-h-[48px]">
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
                      i === recentTranscript.length - 1
                        ? 'text-text-primary'
                        : 'text-text-muted',
                    )}
                  >
                    {seg.text}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Live findings feed */}
        <div className="w-96 flex flex-col overflow-hidden flex-shrink-0 bg-bg-base">
          <div className="border-b-2 border-bg-border px-5 py-3 flex-shrink-0 flex items-center justify-between bg-bg-surface">
            <span className="font-mono text-xs font-bold uppercase tracking-widest text-text-secondary">
              Agent Findings
            </span>
            <div className="flex items-center gap-4">
              {(['coach', 'compliance', 'persona'] as const).map((agent) => {
                const count = findings.filter((f) => f.agent === agent).length;
                if (count === 0) return null;
                const s = AGENT_STYLES[agent];
                return (
                  <div key={agent} className="flex items-center gap-1.5">
                    <span className={cn('w-2 h-2 rounded-full', s.dot)} />
                    <span className="font-mono text-xs text-text-muted">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            ref={findingsFeedRef}
            className="flex-1 overflow-y-auto divide-y-2 divide-bg-border"
          >
            {findings.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
                <div className="w-14 h-14 border-2 border-bg-border flex items-center justify-center">
                  <Radio size={24} className="text-text-muted" />
                </div>
                <p className="font-mono text-sm text-text-muted leading-relaxed">
                  Listening for claims…<br />
                  Findings will appear here as you speak.
                </p>
              </div>
            ) : (
              findings.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  isNew={newFindingIds.has(f.id)}
                />
              ))
            )}
          </div>

          {/* Finalizing state indicator */}
          {state === 'finalizing' && (
            <div className="border-t-2 border-bg-border px-5 py-4 bg-bg-surface flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 bg-accent-red animate-pulse flex-shrink-0" />
              <p className="font-mono text-sm text-text-secondary">Building readiness report…</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Nudge toasts (bottom-right) ── */}
      {nudges.length > 0 && (
        <div className="fixed bottom-8 right-8 flex flex-col gap-3 z-50 pointer-events-none">
          {nudges.slice(0, 3).map((nudge) => (
            <div key={nudge.id} className="pointer-events-auto">
              <NudgeToast nudge={nudge} onDismiss={dismissNudge} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
