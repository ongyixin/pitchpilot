import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import type { SessionStatusResponse } from '@/types';

const PIPELINE_STEPS = [
  { threshold: 15,  label: 'Frame Extraction',   sub: 'Gemma 3n · OpenCV' },
  { threshold: 35,  label: 'Audio Transcription', sub: 'Gemma 3n · Audio' },
  { threshold: 55,  label: 'Claim Extraction',    sub: 'Gemma 3n · OCR + NLP' },
  { threshold: 85,  label: 'Agent Analysis',      sub: 'FunctionGemma · Gemma 3 4B' },
  { threshold: 100, label: 'Readiness Scoring',   sub: 'Aggregating findings' },
];

function getStepIndex(progress: number): number {
  return PIPELINE_STEPS.findIndex((s) => progress < s.threshold);
}

interface Props {
  status: SessionStatusResponse | null;
  sessionId: string | null;
}

export function AnalyzingPage({ status, sessionId }: Props) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 500);
    return () => clearInterval(t);
  }, []);

  const progress = status?.progress ?? 0;
  const currentStepIndex = getStepIndex(progress);
  const currentLabel = status?.progress_message ?? 'Initializing…';

  return (
    <div className="min-h-screen bg-bg-base flex flex-col">
      {/* Masthead */}
      <header className="border-b-4 border-bg-border px-8 pt-6 pb-4">
        <div className="max-w-lg mx-auto">
          <div className="flex items-end justify-between gap-4">
            <h1 className="font-display text-8xl leading-none text-text-primary tracking-wider">
              P<span className="italic">ITCH</span><span style={{ marginLeft: '0.1em' }}>PILOT</span>
            </h1>
            {sessionId && (
              <div className="text-right pb-2 shrink-0">
                <p className="font-mono text-xs text-text-muted uppercase tracking-widest">Session</p>
                <p className="font-mono text-xs text-text-secondary">{sessionId}</p>
              </div>
            )}
          </div>
          <div className="mt-3 pt-2 border-t-2 border-bg-border">
            <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
              Analysis In Progress
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col items-center px-6 py-12">
        <div className="w-full max-w-lg">

          {/* Big status headline */}
          <div className="mb-8">
            <div className="flex items-baseline gap-3 mb-1">
              <span className="font-display text-6xl text-text-primary leading-none">
                ANALYZING
              </span>
              {/* Blinking block cursor */}
              <span
                className={cn(
                  'font-display text-6xl leading-none text-accent-red',
                  tick % 2 === 0 ? 'opacity-100' : 'opacity-0',
                )}
              >
                ▐
              </span>
            </div>
            <p className="font-mono text-sm text-text-secondary uppercase tracking-widest">
              {currentLabel}
            </p>
          </div>

          {/* Progress bar */}
          <div className="mb-2">
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs text-text-muted uppercase tracking-widest">Progress</span>
              <span className="font-display text-2xl text-text-primary leading-none">{progress}%</span>
            </div>
            <div className="h-5 bg-bg-surface border-2 border-bg-border overflow-hidden">
              <div
                className="h-full bg-bg-border transition-all duration-700 ease-out relative overflow-hidden"
                style={{ width: `${progress}%` }}
              >
                {/* Shimmer on the fill */}
                <div className="absolute inset-0 animate-marquee bg-gradient-to-r from-transparent via-bg-surface/20 to-transparent" />
              </div>
            </div>
          </div>

          {/* Horizontal rule */}
          <div className="border-t-2 border-bg-border mt-8 mb-4" />

          {/* Pipeline steps — editorial bulletin list */}
          <div className="space-y-0">
            {PIPELINE_STEPS.slice(0, -1).map((step, i) => {
              const done = i < currentStepIndex;
              const active = i === currentStepIndex;
              const pending = i > currentStepIndex;

              return (
                <div
                  key={step.key}
                  className={cn(
                    'flex items-center gap-4 py-2.5 border-b border-bg-border',
                    active ? 'bg-bg-surface px-3 -mx-3' : '',
                  )}
                >
                  {/* Step number */}
                  <span className={cn(
                    'font-mono text-xs w-5 shrink-0 tabular-nums',
                    done ? 'text-text-muted' : active ? 'text-text-primary font-bold' : 'text-text-muted opacity-40',
                  )}>
                    {String(i + 1).padStart(2, '0')}
                  </span>

                  {/* Status glyph */}
                  <span className={cn(
                    'font-mono text-sm shrink-0 w-4',
                    done ? 'text-text-primary' : active ? 'text-text-primary' : 'text-text-muted opacity-30',
                  )}>
                    {done ? '✓' : active ? '▶' : '○'}
                  </span>

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <span className={cn(
                      'font-mono text-sm font-bold uppercase tracking-wider',
                      done ? 'text-text-muted line-through decoration-text-muted' : active ? 'text-text-primary' : 'text-text-muted opacity-40',
                    )}>
                      {step.label}
                    </span>
                    {step.sub && (
                      <span className={cn(
                        'font-mono text-xs ml-2',
                        done || active ? 'text-text-muted' : 'text-text-muted opacity-30',
                      )}>
                        — {step.sub}
                      </span>
                    )}
                  </div>

                  {/* Status badge */}
                  <div className="shrink-0 w-20 text-right">
                    {done && (
                      <span className="font-mono text-xs text-text-muted uppercase">DONE</span>
                    )}
                    {active && (
                      <span className={cn(
                        'font-mono text-xs uppercase font-bold text-text-primary',
                        tick % 2 === 0 ? 'opacity-100' : 'opacity-50',
                      )}>
                        RUNNING
                      </span>
                    )}
                    {pending && (
                      <span className="font-mono text-xs text-text-muted opacity-30 uppercase">QUEUED</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer model credit */}
          <div className="mt-8 border-t-2 border-bg-border pt-4">
            <p className="font-mono text-xs text-text-muted uppercase tracking-wider leading-relaxed">
              Gemma 3n · FunctionGemma 270M · Gemma 3 4B
              <br />
              All models running on-device
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
