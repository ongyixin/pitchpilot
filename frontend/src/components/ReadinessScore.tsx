/**
 * ReadinessScore — Editorial big-number display + dimension breakdown.
 *
 * Brutalist redesign: no SVG arc gauge — instead a giant Bebas Neue score
 * number, a letter grade, and horizontal bar meters for each dimension.
 */

import { cn } from '@/lib/utils';
import type { ReadinessReport } from '@/types/api';

interface Props {
  report: ReadinessReport;
}

const DIMENSION_ORDER = ['clarity', 'compliance', 'defensibility', 'persuasiveness'];

export function ReadinessScore({ report }: Props) {
  const { overall_score, grade, dimensions } = report;

  const scoreColor =
    overall_score >= 80 ? 'text-text-primary' :
    overall_score >= 60 ? 'text-accent-amber' : 'text-accent-red';

  const dimList = DIMENSION_ORDER
    .map((key) => dimensions[key])
    .filter(Boolean);

  return (
    <div className="bg-bg-surface border-2 border-bg-border">
      {/* Panel header */}
      <div className="px-4 py-2 border-b-2 border-bg-border bg-bg-elevated flex items-center justify-between">
        <span className="font-display text-xl tracking-wider text-text-primary">READINESS SCORE</span>
        <span className={cn(
          'font-display text-xl border-2 border-current px-2 leading-tight',
          scoreColor,
        )}>
          {grade}
        </span>
      </div>

      {/* Big score number + dimension bars */}
      <div className="p-4">
        {/* Hero score */}
        <div className="flex items-end gap-3 mb-4 pb-4 border-b-2 border-bg-border">
          <span className={cn('font-display leading-none', scoreColor, 'text-[80px]')}>
            {overall_score}
          </span>
          <span className="font-mono text-sm text-text-muted pb-3">/100</span>
        </div>

        {/* Dimension bars */}
        <div className="space-y-3">
          {dimList.map((dim) => {
            const barColor =
              dim.score >= 80 ? 'bg-text-primary' :
              dim.score >= 60 ? 'bg-accent-amber' : 'bg-accent-red';

            return (
              <div key={dim.name}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs text-text-secondary uppercase tracking-wider">
                    {dim.name}
                  </span>
                  <div className="flex items-center gap-3">
                    {dim.issues_count > 0 && (
                      <span className="font-mono text-xs text-text-muted">
                        {dim.issues_count} issues
                      </span>
                    )}
                    <span className="font-display text-lg text-text-primary leading-none">
                      {dim.score}
                    </span>
                  </div>
                </div>
                {/* Track — square, thick border */}
                <div className="h-3 bg-bg-base border-2 border-bg-border overflow-hidden">
                  <div
                    className={cn('h-full transition-all duration-700', barColor)}
                    style={{ width: `${dim.score}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary */}
        {report.summary && (
          <p className="font-mono text-xs text-text-muted leading-relaxed border-t-2 border-bg-border pt-3 mt-4">
            {report.summary}
          </p>
        )}
      </div>
    </div>
  );
}
