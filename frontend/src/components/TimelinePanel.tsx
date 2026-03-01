/**
 * TimelinePanel — interactive timeline strip for the results view.
 *
 * Brutalist redesign: thick bordered track, square markers with hard colors,
 * bold tick labels in Courier Prime.
 */

import { useRef } from 'react';
import { cn, formatTime } from '@/lib/utils';
import type { TimelineAnnotation } from '@/types/api';

interface Props {
  annotations: TimelineAnnotation[];
  duration: number;
  currentTime: number;
  onSeek: (timestamp: number) => void;
  onSelectAnnotation: (ann: TimelineAnnotation) => void;
}

const MARKER_COLOR: Record<string, string> = {
  compliance: 'bg-accent-red border-accent-red',
  coach: 'bg-marker-yellow border-marker-yellow',
  persona: 'bg-accent-purple border-accent-purple',
};

const LEGEND = [
  { color: 'bg-accent-red', label: 'Compliance' },
  { color: 'bg-marker-yellow', label: 'Coach' },
  { color: 'bg-accent-purple', label: 'Persona' },
  { color: 'bg-accent-blue', label: 'Technical' },
];

export function TimelinePanel({ annotations, duration, currentTime, onSeek, onSelectAnnotation }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);

  const effectiveDuration = duration > 0 ? duration : 360;
  const positionPct = (ts: number) => Math.min(100, (ts / effectiveDuration) * 100);
  const playheadPct = positionPct(currentTime);

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    onSeek(frac * effectiveDuration);
  };

  return (
    <div className="space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="font-display text-xl tracking-wider text-text-primary">TIMELINE</span>
        <div className="flex items-center gap-4">
          {LEGEND.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5 font-mono text-xs text-text-muted">
              {/* Square legend swatch */}
              <span className={cn('w-2.5 h-2.5 border border-current', l.color)} />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      {/* Track — thick bordered, square */}
      <div
        ref={trackRef}
        onClick={handleTrackClick}
        className="relative h-8 bg-bg-base border-2 border-bg-border cursor-pointer overflow-visible"
      >
        {/* Baseline */}
        <div className="absolute top-1/2 left-0 right-0 h-px bg-bg-border -translate-y-1/2 opacity-40" />

        {/* Playhead — thick red line */}
        {currentTime > 0 && (
          <div
            className="absolute top-0 bottom-0 w-[2px] bg-accent-red pointer-events-none z-10"
            style={{ left: `${playheadPct}%` }}
          />
        )}

        {/* Annotation markers — square, not circular */}
        {annotations.map((ann, i) => {
          const left = positionPct(ann.timestamp);
          const colorCls = MARKER_COLOR[ann.category] ?? 'bg-text-muted border-text-muted';
          return (
            <button
              key={`${ann.finding_id}-${i}`}
              title={`${formatTime(ann.timestamp)} — ${ann.label}`}
              onClick={(e) => {
                e.stopPropagation();
                onSeek(ann.timestamp);
                onSelectAnnotation(ann);
              }}
              style={{ left: `${left}%` }}
              className={cn(
                'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
                'w-3 h-3 border-2 transition-transform hover:scale-150 active:scale-125 z-20',
                colorCls,
              )}
            />
          );
        })}
      </div>

      {/* Tick labels — clickable to seek */}
      <div className="relative h-4">
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const ts = frac * effectiveDuration;
          return (
            <button
              key={frac}
              onClick={() => onSeek(ts)}
              style={{ left: `${frac * 100}%` }}
              className="absolute -translate-x-1/2 font-mono text-[10px] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              {formatTime(ts)}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <p className="font-mono text-xs text-text-muted">
          {annotations.length} annotation{annotations.length !== 1 ? 's' : ''}
        </p>
        {currentTime > 0 && (
          <span className="font-mono text-xs text-text-primary font-bold">
            ▶ {formatTime(currentTime)}
          </span>
        )}
      </div>
    </div>
  );
}
