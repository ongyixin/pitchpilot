/**
 * Timeline — horizontal strip of colour-coded markers.
 *
 * Clicking a marker seeks the video to that timestamp and highlights the
 * corresponding finding in the panel.
 *
 * Props accept the index.ts TimelineAnnotation shape (severity-based colour),
 * or the api.ts shape (colour field).  Both are handled.
 */

import { useRef } from 'react';
import { cn, formatTime } from '@/lib/utils';

export interface TimelineMarker {
  id: string;
  finding_id: string;
  timestamp: number;
  label: string;
  /** If provided, overrides severity-derived colour */
  color?: string;
  severity?: string;
  category?: string;
  agent?: string;
}

interface Props {
  markers: TimelineMarker[];
  /** Duration of the video in seconds (for scaling). Defaults to last marker + 10 %. */
  duration?: number;
  /** Called when user clicks a marker */
  onSeek?: (timestamp: number, findingId: string) => void;
  /** The currently active finding ID (highlighted marker) */
  activeFindingId?: string | null;
}

function markerColor(m: TimelineMarker): string {
  if (m.color) {
    const colorMap: Record<string, string> = {
      red: 'bg-marker-red border-marker-red',
      yellow: 'bg-marker-yellow border-marker-yellow',
      blue: 'bg-marker-blue border-marker-blue',
      purple: 'bg-marker-purple border-marker-purple',
    };
    return colorMap[m.color] ?? 'bg-text-muted border-text-muted';
  }
  if (m.severity) {
    const severityMap: Record<string, string> = {
      critical: 'bg-marker-red border-marker-red',
      warning: 'bg-marker-yellow border-marker-yellow',
      info: 'bg-marker-blue border-marker-blue',
    };
    return severityMap[m.severity] ?? 'bg-text-muted border-text-muted';
  }
  if (m.category) {
    const catMap: Record<string, string> = {
      compliance: 'bg-marker-red border-marker-red',
      risk: 'bg-marker-red border-marker-red',
      coach: 'bg-marker-yellow border-marker-yellow',
      clarity: 'bg-marker-yellow border-marker-yellow',
      structure: 'bg-marker-yellow border-marker-yellow',
      persona: 'bg-marker-purple border-marker-purple',
      persona_question: 'bg-marker-purple border-marker-purple',
      technical: 'bg-marker-blue border-marker-blue',
    };
    return catMap[m.category] ?? 'bg-marker-blue border-marker-blue';
  }
  return 'bg-text-muted border-text-muted';
}

const LEGEND = [
  { label: 'Compliance', color: 'bg-marker-red' },
  { label: 'Coach', color: 'bg-marker-yellow' },
  { label: 'Persona', color: 'bg-marker-purple' },
  { label: 'Technical', color: 'bg-marker-blue' },
];

export function Timeline({ markers, duration, onSeek, activeFindingId }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);

  const effectiveDuration =
    duration ??
    (markers.length > 0
      ? Math.max(...markers.map((m) => m.timestamp)) * 1.1
      : 300);

  const positionPct = (ts: number) =>
    Math.min(100, (ts / effectiveDuration) * 100);

  return (
    <div className="bg-bg-surface border border-bg-border rounded-md p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
          Timeline
        </span>
        <div className="flex items-center gap-3">
          {LEGEND.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5 text-xs text-text-muted">
              <span className={cn('w-2 h-2 rounded-full', l.color)} />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      {/* Track */}
      <div
        ref={trackRef}
        className="relative h-6 bg-bg-elevated rounded-sm overflow-visible cursor-default"
      >
        {/* Baseline */}
        <div className="absolute top-1/2 left-0 right-0 h-px bg-bg-border -translate-y-1/2" />

        {/* Markers */}
        {markers.map((m) => {
          const left = positionPct(m.timestamp);
          const isActive = m.finding_id === activeFindingId;
          const colorCls = markerColor(m);

          return (
            <button
              key={m.id}
              title={`${formatTime(m.timestamp)} — ${m.label}`}
              onClick={() => onSeek?.(m.timestamp, m.finding_id)}
              style={{ left: `${left}%` }}
              className={cn(
                'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
                'w-2.5 h-2.5 rounded-full border transition-all duration-150',
                colorCls,
                isActive ? 'scale-150 ring-1 ring-white/30' : 'hover:scale-125',
              )}
            />
          );
        })}
      </div>

      {/* Tick labels */}
      <div className="relative h-3">
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => (
          <span
            key={frac}
            style={{ left: `${frac * 100}%` }}
            className="absolute -translate-x-1/2 font-mono text-[9px] text-text-muted"
          >
            {formatTime(frac * effectiveDuration)}
          </span>
        ))}
      </div>

      {/* Marker count */}
      <p className="text-xs text-text-muted">
        {markers.length} annotation{markers.length !== 1 ? 's' : ''}
      </p>
    </div>
  );
}
