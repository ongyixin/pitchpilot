/**
 * InRoomModePage — minimal dark UI for live face-to-face presentations.
 *
 * Design principles:
 *   - Near-black background so the screen is invisible from the audience
 *   - Large, high-contrast cue text visible at a glance
 *   - Audio cues are the primary channel; on-screen text is the fallback
 *   - Controls are large and easy to tap under stress
 *   - All findings are stored for post-session review
 *
 * Layout:
 *   ┌──────────────────────────────────────────────┐
 *   │  ● LIVE IN-ROOM   [MUTED]   00:04:22         │  ← header bar
 *   ├──────────────────────────────────────────────┤
 *   │                                              │
 *   │           "slow down"                        │  ← active cue (large)
 *   │                                              │
 *   │   "compliance risk"       fading...          │  ← previous cue
 *   │   "mention privacy"       fading...          │
 *   │                                              │
 *   ├──────────────────────────────────────────────┤
 *   │  [🔇 MUTE]  [SENSITIVITY ▼]  [END SESSION]   │
 *   ├──────────────────────────────────────────────┤
 *   │  ▶ CUE LOG (last 10 cues)   [show/hide]      │
 *   └──────────────────────────────────────────────┘
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Volume2, VolumeX, StopCircle, ChevronDown, ChevronUp,
  Radio, Activity, AlertCircle, ArrowLeft,
} from 'lucide-react';
import type { EarpieceCue } from '@/types';
import type { UseLiveSessionReturn, CueSensitivity } from '@/hooks/useLiveSession';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
/** Max cues displayed in the recent panel */
const MAX_VISIBLE_CUES = 3;

const PRIORITY_COLOR: Record<string, string> = {
  critical: '#ff3b3b',
  warning:  '#f59e0b',
  info:     '#60a5fa',
};

const CATEGORY_LABEL: Record<string, string> = {
  compliance:    'COMPLIANCE',
  pacing:        'PACING',
  clarity:       'CLARITY',
  persona:       'PERSONA',
  coach:         'COACH',
};

const SENSITIVITY_LABELS: Record<CueSensitivity, string> = {
  high:   'HIGH',
  medium: 'MED',
  low:    'LOW',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface TimerProps { seconds: number }
function BigTimer({ seconds }: TimerProps) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts = [
    h > 0 ? String(h).padStart(2, '0') : null,
    String(m).padStart(2, '0'),
    String(s).padStart(2, '0'),
  ].filter(Boolean);
  return (
    <span className="font-mono tabular-nums" style={{ fontSize: '3.5rem', letterSpacing: '0.08em', color: '#a0a0a0' }}>
      {parts.join(':')}
    </span>
  );
}

interface ActiveCueDisplayProps {
  cues: EarpieceCue[];
}

function ActiveCueDisplay({ cues }: ActiveCueDisplayProps) {
  const recent = cues.slice(0, MAX_VISIBLE_CUES);

  if (recent.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4" style={{ minHeight: '320px' }}>
        <Radio size={36} style={{ color: '#333' }} />
        <p className="font-mono text-base" style={{ color: '#444', letterSpacing: '0.15em' }}>
          LISTENING…
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 px-10" style={{ minHeight: '320px' }}>
      {recent.map((cue, idx) => {
        const isActive = idx === 0;
        const color = PRIORITY_COLOR[cue.priority] ?? '#f59e0b';
        const opacity = isActive ? 1 : Math.max(0.15, 0.55 - idx * 0.2);

        return (
          <div
            key={cue.id}
            className="text-center transition-all duration-700"
            style={{ opacity, transform: `scale(${isActive ? 1 : 0.88 - idx * 0.06})` }}
          >
            {/* Category badge */}
            <div className="flex items-center justify-center gap-2.5 mb-3">
              <span
                className="font-mono text-sm tracking-widest"
                style={{ color: isActive ? color : '#555', fontSize: '0.8rem' }}
              >
                {CATEGORY_LABEL[cue.category] ?? cue.category.toUpperCase()}
              </span>
              <span
                className="font-mono text-sm"
                style={{ color: '#444', fontSize: '0.75rem' }}
              >
                {formatElapsed(cue.elapsed)}
              </span>
            </div>
            {/* Cue text */}
            <p
              className="font-mono font-bold tracking-wide"
              style={{
                fontSize: isActive ? '3rem' : '1.75rem',
                color: isActive ? color : '#666',
                letterSpacing: isActive ? '0.04em' : '0.02em',
                textTransform: 'lowercase',
                transition: 'all 0.4s ease',
              }}
            >
              {cue.text}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function formatElapsed(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

interface CueLogProps {
  cues: EarpieceCue[];
}

function CueLog({ cues }: CueLogProps) {
  const logCues = cues.slice(0, 30);
  return (
    <div className="divide-y" style={{ borderColor: '#1a1a1a' }}>
      {logCues.length === 0 ? (
        <p className="font-mono text-sm px-5 py-4" style={{ color: '#444' }}>
          No cues yet — history will appear here.
        </p>
      ) : (
        logCues.map((cue) => {
          const color = PRIORITY_COLOR[cue.priority] ?? '#f59e0b';
          return (
            <div key={cue.id} className="flex items-center gap-4 px-5 py-2.5">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: color }}
              />
              <span className="font-mono text-sm flex-1" style={{ color: '#888' }}>
                {cue.text}
              </span>
              <span className="font-mono text-sm flex-shrink-0" style={{ color: '#444' }}>
                {formatElapsed(cue.elapsed)}
              </span>
              <span
                className="font-mono text-sm flex-shrink-0"
                style={{ color: '#444', fontSize: '0.75rem', letterSpacing: '0.1em' }}
              >
                {CATEGORY_LABEL[cue.category] ?? cue.category.toUpperCase()}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

interface Props extends UseLiveSessionReturn {
  onSessionComplete: () => void;
  onHome?: () => void;
}

export function InRoomModePage({
  state,
  cues,
  findings,
  elapsedSeconds,
  muted,
  sensitivity,
  endSession,
  toggleMute,
  setSensitivity,
  transcript,
  onSessionComplete,
  onHome,
}: Props) {
  const [showLog, setShowLog] = useState(false);
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const confirmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Flash effect when a new cue arrives
  const [flashActive, setFlashActive] = useState(false);
  const prevCueCount = useRef(0);

  useEffect(() => {
    if (cues.length > prevCueCount.current) {
      setFlashActive(true);
      const t = setTimeout(() => setFlashActive(false), 300);
      prevCueCount.current = cues.length;
      return () => clearTimeout(t);
    }
    prevCueCount.current = cues.length;
  }, [cues.length]);

  // Transition to results when complete
  useEffect(() => {
    if (state === 'complete') onSessionComplete();
  }, [state, onSessionComplete]);

  const handleEndClick = useCallback(() => {
    if (showEndConfirm) {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
      setShowEndConfirm(false);
      endSession();
    } else {
      setShowEndConfirm(true);
      confirmTimeoutRef.current = setTimeout(() => setShowEndConfirm(false), 3000);
    }
  }, [showEndConfirm, endSession]);

  const criticalCount = cues.filter((c) => c.priority === 'critical').length;
  const lastTranscript = transcript[transcript.length - 1]?.text ?? '';

  return (
    <div
      className="h-screen flex flex-col select-none overflow-hidden"
      style={{ background: '#050508', color: '#fff' }}
    >
      {/* ── Flash overlay on new cue ── */}
      <div
        className="pointer-events-none fixed inset-0 z-50 transition-opacity duration-300"
        style={{
          background: 'rgba(245,158,11,0.06)',
          opacity: flashActive ? 1 : 0,
        }}
      />

      {/* ── Header ── */}
      <header
        className="flex items-center justify-between px-8 py-4 flex-shrink-0"
        style={{ borderBottom: '1px solid #111' }}
      >
        <div className="flex items-center gap-4">
          {/* Back to home */}
          {onHome && (
            <button
              onClick={onHome}
              className="flex items-center gap-1.5 px-3 py-2 font-mono text-sm uppercase tracking-wider transition-all duration-150"
              style={{ border: '1px solid #222', color: '#555', background: '#0f0f0f' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#888'; e.currentTarget.style.borderColor = '#333'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#555'; e.currentTarget.style.borderColor = '#222'; }}
            >
              <ArrowLeft size={14} />
              <span className="hidden sm:inline">Home</span>
            </button>
          )}
          {/* Live indicator */}
          <span className="flex items-center gap-2">
            {state === 'finalizing' ? (
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#f59e0b' }} />
            ) : (
              <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: '#ef4444' }} />
            )}
            <span className="font-mono text-sm tracking-widest" style={{ color: '#555' }}>
              {state === 'finalizing' ? 'FINALIZING' : 'LIVE IN-ROOM'}
            </span>
          </span>

          {/* Mute indicator pill */}
          {muted && (
            <span
              className="font-mono text-sm px-3 py-1 rounded-sm"
              style={{ background: '#1a1a1a', color: '#ef4444', fontSize: '0.75rem', letterSpacing: '0.12em' }}
            >
              MUTED
            </span>
          )}
        </div>

        <div className="flex items-center gap-6">
          {/* Findings count */}
          <span className="font-mono text-sm" style={{ color: '#333' }}>
            {findings.length} findings · {cues.length} cues
          </span>

          {/* Critical alert */}
          {criticalCount > 0 && (
            <div className="flex items-center gap-2">
              <AlertCircle size={14} style={{ color: '#ef4444' }} />
              <span className="font-mono text-sm" style={{ color: '#ef4444', fontSize: '0.8rem' }}>
                {criticalCount} CRITICAL
              </span>
            </div>
          )}

          <BigTimer seconds={elapsedSeconds} />
        </div>
      </header>

      {/* ── Active cue display ── */}
      <ActiveCueDisplay cues={cues} />

      {/* ── Transcript whisper (last spoken phrase) ── */}
      {lastTranscript && (
        <div
          className="px-10 pb-5 text-center"
          style={{ borderTop: '1px solid #0f0f0f' }}
        >
          <p
            className="font-mono text-sm italic truncate"
            style={{ color: '#2a2a2a', maxWidth: '60ch', margin: '0 auto', paddingTop: '0.75rem' }}
          >
            "{lastTranscript}"
          </p>
        </div>
      )}

      {/* ── Controls ── */}
      <div
        className="flex items-center justify-between gap-4 px-8 py-5 flex-shrink-0"
        style={{ borderTop: '1px solid #111' }}
      >
        {/* Mute button */}
        <button
          onClick={toggleMute}
          className="flex items-center gap-2.5 px-5 py-3 font-mono text-sm font-bold uppercase tracking-wider transition-all duration-150"
          style={{
            border: `1px solid ${muted ? '#ef4444' : '#222'}`,
            color: muted ? '#ef4444' : '#666',
            background: muted ? 'rgba(239,68,68,0.08)' : '#0f0f0f',
            minWidth: '120px',
          }}
        >
          {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          {muted ? 'UNMUTE' : 'MUTE'}
        </button>

        {/* Sensitivity selector */}
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-sm mr-3" style={{ color: '#333', fontSize: '0.75rem', letterSpacing: '0.12em' }}>
            SENSITIVITY
          </span>
          {(['high', 'medium', 'low'] as CueSensitivity[]).map((s) => (
            <button
              key={s}
              onClick={() => setSensitivity(s)}
              className="font-mono text-sm px-3 py-2 transition-all duration-100"
              style={{
                border: `1px solid ${sensitivity === s ? '#f59e0b' : '#1a1a1a'}`,
                color: sensitivity === s ? '#f59e0b' : '#444',
                background: sensitivity === s ? 'rgba(245,158,11,0.08)' : 'transparent',
                fontSize: '0.75rem',
                letterSpacing: '0.1em',
              }}
            >
              {SENSITIVITY_LABELS[s]}
            </button>
          ))}
        </div>

        {/* End session button */}
        <button
          onClick={handleEndClick}
          className="flex items-center gap-2.5 px-6 py-3 font-mono text-sm font-bold uppercase tracking-wider transition-all duration-150"
          style={{
            border: `1px solid ${showEndConfirm ? '#ef4444' : '#222'}`,
            color: showEndConfirm ? '#fff' : '#888',
            background: showEndConfirm ? '#ef4444' : '#0f0f0f',
            minWidth: '150px',
          }}
        >
          <StopCircle size={16} />
          {showEndConfirm ? 'CONFIRM END' : 'END SESSION'}
        </button>
      </div>

      {/* ── Cue log toggle ── */}
      <div style={{ borderTop: '1px solid #111' }} className="flex-shrink-0">
        <button
          onClick={() => setShowLog((v) => !v)}
          className="w-full flex items-center justify-between px-8 py-3 transition-colors duration-100"
          style={{ color: '#333' }}
        >
          <div className="flex items-center gap-2.5">
            <Activity size={14} style={{ color: '#333' }} />
            <span className="font-mono text-sm tracking-widest" style={{ fontSize: '0.75rem', letterSpacing: '0.12em' }}>
              CUE LOG · {cues.length} total
            </span>
          </div>
          {showLog
            ? <ChevronUp size={14} />
            : <ChevronDown size={14} />
          }
        </button>

        {showLog && (
          <div
            className="overflow-y-auto"
            style={{ maxHeight: '220px', background: '#08080a', borderTop: '1px solid #111' }}
          >
            <CueLog cues={cues} />
          </div>
        )}
      </div>

      {/* ── Finalizing overlay ── */}
      {state === 'finalizing' && (
        <div
          className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-5"
          style={{ background: 'rgba(5,5,8,0.92)' }}
        >
          <div className="w-4 h-4 rounded-full animate-pulse" style={{ background: '#f59e0b' }} />
          <p className="font-mono text-base tracking-widest" style={{ color: '#888' }}>
            BUILDING READINESS REPORT…
          </p>
        </div>
      )}
    </div>
  );
}
