/**
 * ReportSummary — editorial column layout for the results view.
 *
 * Brutalist redesign: bold Bebas Neue section headers, numbered priority
 * fixes with large red numbers, persona question cards with solid badges.
 */

import { useState } from 'react';
import { Clock } from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type { ReadinessReport, PersonaQuestion } from '@/types/api';

const PERSONA_BADGE: Record<string, string> = {
  skeptical_investor: 'badge-coach',
  technical_reviewer: 'badge-persona',
  compliance_officer: 'badge-compliance',
};

const DIFFICULTY_LABEL: Record<string, string> = {
  hard: 'HARD',
  medium: 'MED',
  easy: 'EASY',
};

const DIFFICULTY_COLOR: Record<string, string> = {
  hard: 'text-accent-red border-accent-red',
  medium: 'text-accent-amber border-accent-amber',
  easy: 'text-text-secondary border-text-muted',
};

function PersonaQuestionCard({ q, expanded, onToggle }: {
  q: PersonaQuestion;
  expanded: boolean;
  onToggle: () => void;
}) {
  const personaKey = q.persona.toLowerCase().replace(/\s+/g, '_');
  const badgeClass = PERSONA_BADGE[personaKey] ?? 'badge-persona';

  return (
    <div className="border-2 border-bg-border overflow-hidden">
      <div
        className="px-4 py-3 cursor-pointer hover:bg-bg-elevated flex items-start gap-3"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0 space-y-2">
          <p className="font-mono text-sm text-text-primary leading-snug font-bold">{q.question}</p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn('font-mono text-xs px-1.5 py-0.5 uppercase tracking-wide', badgeClass)}>
              {q.persona}
            </span>
            <span className={cn('font-mono text-xs border px-1 py-0.5', DIFFICULTY_COLOR[q.difficulty] ?? 'text-text-muted border-text-muted')}>
              {DIFFICULTY_LABEL[q.difficulty] ?? q.difficulty}
            </span>
            {q.timestamp !== undefined && (
              <span className="font-mono text-xs text-text-muted flex items-center gap-1">
                <Clock size={9} />
                {formatTime(q.timestamp)}
              </span>
            )}
          </div>
        </div>
        <span className="font-mono text-xs text-text-muted shrink-0 mt-1">
          {expanded ? '▲' : '▼'}
        </span>
      </div>

      {expanded && q.suggested_answer && (
        <div className="px-4 pb-4 bg-bg-elevated border-t-2 border-bg-border">
          <p className="font-display text-base tracking-wider text-text-primary mt-3 mb-1">
            SUGGESTED ANSWER
          </p>
          <p className="font-mono text-xs text-text-secondary leading-relaxed">{q.suggested_answer}</p>
        </div>
      )}
    </div>
  );
}

interface Props {
  report: ReadinessReport;
}

export function ReportSummary({ report }: Props) {
  const [expandedQ, setExpandedQ] = useState<string | null>(null);

  return (
    <div className="space-y-0 pb-4">

      {/* ── EXECUTIVE SUMMARY ── */}
      <section className="pb-6">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-display text-2xl tracking-wider text-text-primary">
            EXECUTIVE SUMMARY
          </span>
        </div>
        <div className="border-b-2 border-bg-border mb-3" />
        <div className="bg-bg-elevated border-2 border-bg-border p-4">
          <p className="font-mono text-sm text-text-secondary leading-relaxed">{report.summary}</p>
        </div>
      </section>

      {/* ── PRIORITY FIXES ── */}
      <section className="pb-6">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-display text-2xl tracking-wider text-text-primary">
            PRIORITY FIXES
          </span>
          <span className="font-mono text-xs text-accent-red border border-accent-red px-1.5 py-0.5">
            {report.priority_fixes.length} ITEMS
          </span>
        </div>
        <div className="border-b-2 border-bg-border mb-3" />

        <ol className="space-y-2">
          {report.priority_fixes.map((fix, i) => (
            <li key={i} className="flex items-start gap-4 border-2 border-bg-border bg-bg-surface">
              {/* Large numbered indicator */}
              <div className="shrink-0 w-12 h-full bg-accent-red flex items-center justify-center py-3 self-stretch">
                <span className="font-display text-2xl text-bg-base leading-none">
                  {i + 1}
                </span>
              </div>
              <p className="font-mono text-sm text-text-secondary leading-relaxed py-3 pr-4">
                {fix}
              </p>
            </li>
          ))}
        </ol>
      </section>

      {/* ── STAKEHOLDER QUESTIONS ── */}
      {report.stakeholder_questions.length > 0 && (
        <section className="pb-6">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-display text-2xl tracking-wider text-text-primary">
              PREPARE FOR THESE
            </span>
          </div>
          <div className="border-b-2 border-bg-border mb-3" />

          <div className="space-y-2">
            {report.stakeholder_questions.map((q) => (
              <PersonaQuestionCard
                key={q.id}
                q={q}
                expanded={expandedQ === q.id}
                onToggle={() => setExpandedQ(expandedQ === q.id ? null : q.id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* ── AGENTS RUN ── */}
      <section>
        <div className="flex items-center gap-3 mb-1">
          <span className="font-display text-2xl tracking-wider text-text-primary">AGENTS RUN</span>
        </div>
        <div className="border-b-2 border-bg-border mb-3" />

        <div className="flex gap-2 flex-wrap">
          {report.agents_run.map((agent) => (
            <span
              key={agent}
              className="px-3 py-1.5 bg-bg-elevated border-2 border-bg-border font-mono text-xs text-text-secondary uppercase tracking-wider"
            >
              {agent}
            </span>
          ))}
        </div>
      </section>

    </div>
  );
}
