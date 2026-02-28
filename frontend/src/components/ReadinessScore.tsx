import { cn } from '@/lib/utils';
import type { ReadinessReport } from '@/types/api';

interface Props {
  report: ReadinessReport;
}

function computeGrade(overall: number): string {
  if (overall >= 90) return 'A';
  if (overall >= 80) return 'B';
  if (overall >= 70) return 'C';
  if (overall >= 60) return 'D';
  return 'F';
}

export function ReadinessScore({ report }: Props) {
  const { overall, dimensions } = report.score;
  const grade = computeGrade(overall);

  const scoreColor =
    overall >= 80 ? 'text-text-primary' :
    overall >= 60 ? 'text-accent-amber' : 'text-accent-red';

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
            {overall}
          </span>
          <span className="font-mono text-sm text-text-muted pb-3">/100</span>
        </div>

        {/* Dimension bars */}
        <div className="space-y-3">
          {dimensions.map((dim) => {
            const barColor =
              dim.score >= 80 ? 'bg-text-primary' :
              dim.score >= 60 ? 'bg-accent-amber' : 'bg-accent-red';

            return (
              <div key={dim.dimension}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs text-text-secondary uppercase tracking-wider">
                    {dim.dimension}
                  </span>
                  <span className="font-display text-lg text-text-primary leading-none">
                    {dim.score}
                  </span>
                </div>
                <div className="h-3 bg-bg-base border-2 border-bg-border overflow-hidden">
                  <div
                    className={cn('h-full transition-all duration-700', barColor)}
                    style={{ width: `${dim.score}%` }}
                  />
                </div>
                {dim.rationale && (
                  <p className="font-mono text-xs text-text-muted mt-0.5 leading-snug">
                    {dim.rationale}
                  </p>
                )}
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
