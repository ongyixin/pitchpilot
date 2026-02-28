import { useState } from 'react';
import { Clock } from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type { Finding, AgentName } from '@/types/api';

const TABS: { id: AgentName | 'all'; label: string }[] = [
  { id: 'all', label: 'ALL' },
  { id: 'coach', label: 'COACH' },
  { id: 'compliance', label: 'COMPLIANCE' },
  { id: 'persona', label: 'PERSONA' },
];

const SEVERITY_GLYPH: Record<string, string> = {
  critical: '■',
  warning: '▲',
  info: '◆',
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'text-accent-red',
  warning: 'text-accent-amber',
  info: 'text-text-muted',
};

interface Props {
  findings: Finding[];
  onSelectFinding?: (finding: Finding) => void;
  activeTimestamp?: number;
}

export function FindingsPanel({ findings, onSelectFinding, activeTimestamp }: Props) {
  const [activeTab, setActiveTab] = useState<AgentName | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = activeTab === 'all' ? findings : findings.filter((f) => f.agent === activeTab);

  const counts: Record<string, number> = {
    all: findings.length,
    coach: findings.filter((f) => f.agent === 'coach').length,
    compliance: findings.filter((f) => f.agent === 'compliance').length,
    persona: findings.filter((f) => f.agent === 'persona').length,
  };

  return (
    <div className="bg-bg-surface border-2 border-bg-border flex flex-col overflow-hidden h-full">
      {/* Panel header */}
      <div className="px-4 py-2 border-b-2 border-bg-border flex items-center justify-between flex-shrink-0 bg-bg-elevated">
        <span className="font-display text-xl tracking-wider text-text-primary">
          AGENT FINDINGS
        </span>
        <span className="font-mono text-xs text-text-muted border border-current px-1.5 py-0.5">
          {findings.length} ITEMS
        </span>
      </div>

      {/* Tabs */}
      <div className="flex border-b-2 border-bg-border flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 py-2 font-mono text-xs transition-colors relative border-r border-bg-border last:border-r-0',
              activeTab === tab.id
                ? 'bg-bg-border text-bg-base'
                : 'text-text-muted hover:bg-bg-elevated',
            )}
          >
            {tab.label}
            {counts[tab.id] > 0 && (
              <span className={cn(
                'ml-1 font-mono text-xs',
                activeTab === tab.id ? 'text-bg-surface' : 'text-text-muted',
              )}>
                {counts[tab.id]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Findings list */}
      <div className="overflow-y-auto flex-1 divide-y-2 divide-bg-border">
        {filtered.map((finding) => {
          const glyph = SEVERITY_GLYPH[finding.severity] ?? '◆';
          const glyphColor = SEVERITY_COLOR[finding.severity] ?? 'text-text-muted';
          const isExpanded = expanded === finding.id;
          const isActive = activeTimestamp !== undefined &&
            finding.timestamp !== undefined &&
            Math.abs(finding.timestamp - activeTimestamp) < 5;

          return (
            <div
              key={finding.id}
              className={cn(
                'transition-colors',
                isActive ? 'bg-bg-elevated' : '',
              )}
            >
              {/* Summary row */}
              <div
                className="px-4 py-3 cursor-pointer hover:bg-bg-elevated flex items-start gap-3"
                onClick={() => {
                  setExpanded(isExpanded ? null : finding.id);
                  onSelectFinding?.(finding);
                }}
              >
                {/* Severity glyph */}
                <span className={cn('font-mono text-sm shrink-0 mt-0.5 leading-none', glyphColor)}>
                  {glyph}
                </span>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-mono text-sm text-text-primary leading-snug font-bold">
                      {finding.title}
                    </p>
                    <span className="font-mono text-xs text-text-muted shrink-0 mt-0.5">
                      {isExpanded ? '▲' : '▼'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    {/* Solid agent badge */}
                    <span className={cn(
                      'font-mono text-xs px-1.5 py-0.5 uppercase tracking-wide',
                      finding.agent === 'coach' ? 'badge-coach' :
                      finding.agent === 'compliance' ? 'badge-compliance' :
                      'badge-persona',
                    )}>
                      {finding.agent}
                    </span>
                    {finding.timestamp !== undefined && (
                      <span className="font-mono text-xs text-text-muted flex items-center gap-1">
                        <Clock size={9} />
                        {formatTime(finding.timestamp)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="px-4 pb-4 space-y-3 bg-bg-elevated border-t-2 border-bg-border">
                  <p className="font-mono text-xs text-text-secondary leading-relaxed pt-3">
                    {finding.description}
                  </p>
                  {finding.claim_text && (
                    <blockquote className="border-l-4 border-bg-border pl-3 font-mono text-xs text-text-muted italic">
                      "{finding.claim_text}"
                    </blockquote>
                  )}
                  {finding.suggestion && (
                    <div className="bg-bg-surface border-2 border-bg-border p-3">
                      <p className="font-display text-base tracking-wider text-text-primary mb-1">
                        SUGGESTION
                      </p>
                      <p className="font-mono text-xs text-text-secondary leading-relaxed">
                        {finding.suggestion}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="py-10 text-center">
            <p className="font-display text-2xl text-text-muted">NO FINDINGS</p>
            <p className="font-mono text-xs text-text-muted mt-1">No findings for this agent.</p>
          </div>
        )}
      </div>
    </div>
  );
}
