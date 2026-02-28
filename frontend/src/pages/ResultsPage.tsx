import { useRef, useState, useCallback } from 'react';
import { RotateCcw, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import { VideoPlayer, type VideoPlayerHandle } from '@/components/VideoPlayer';
import { FindingsPanel } from '@/components/FindingsPanel';
import { TimelinePanel } from '@/components/TimelinePanel';
import { ReadinessScore } from '@/components/ReadinessScore';
import { ReportSummary } from '@/components/ReportSummary';
import type { ReadinessReport, Finding, TimelineAnnotation } from '@/types/api';

interface Props {
  report: ReadinessReport;
  sessionId: string;
  videoFile?: File;
  onReset: () => void;
}

export function ResultsPage({ report, sessionId, videoFile, onReset }: Props) {
  const playerRef = useRef<VideoPlayerHandle>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeSection, setActiveSection] = useState<'findings' | 'report'>('findings');

  const videoSrc = videoFile ? URL.createObjectURL(videoFile) : undefined;

  const maxTimestamp = report.timeline.reduce((m, a) => Math.max(m, a.timestamp), 0);
  const duration = maxTimestamp > 0 ? maxTimestamp + 40 : 360;

  const handleFindingSelect = useCallback((finding: Finding) => {
    if (finding.timestamp !== undefined) {
      playerRef.current?.seekTo(finding.timestamp);
    }
  }, []);

  const handleAnnotationSelect = useCallback((ann: TimelineAnnotation) => {
    playerRef.current?.seekTo(ann.timestamp);
    const finding = report.findings.find((f) => f.id === ann.finding_id) ??
      report.top_issues.find((f) => f.id === ann.finding_id);
    if (finding) handleFindingSelect(finding);
  }, [report, handleFindingSelect]);

  const scoreColor =
    report.overall_score >= 80 ? 'text-text-primary' :
    report.overall_score >= 60 ? 'text-accent-amber' : 'text-accent-red';

  const allFindings = [...report.top_issues, ...report.findings.filter(
    (f) => !report.top_issues.find((t) => t.id === f.id),
  )];

  return (
    <div className="h-screen bg-bg-base flex flex-col overflow-hidden">
      {/* Masthead top bar */}
      <header className="border-b-4 border-bg-border px-6 pt-3 pb-2 flex-shrink-0">
        <div className="flex items-end justify-between gap-4">
          <div className="flex items-end gap-4">
            <h1 className="font-display text-5xl leading-none tracking-wider text-text-primary">
              PITCHPILOT
            </h1>
            <span className="font-mono text-xs text-text-muted pb-1">
              SESSION&nbsp;
              <span className="text-text-secondary">{sessionId}</span>
            </span>
          </div>

          <div className="flex items-center gap-3 pb-1">
            {/* Score pill — bold editorial */}
            <div className="border-2 border-bg-border px-3 py-1 flex items-center gap-2 bg-bg-surface">
              <span className="font-mono text-xs text-text-muted uppercase tracking-widest">Score</span>
              <span className={cn('font-display text-2xl leading-none', scoreColor)}>
                {report.overall_score}
              </span>
              <span className="font-mono text-xs text-text-muted">/100</span>
              <span className={cn(
                'font-display text-xl leading-none border-l-2 border-bg-border pl-2 ml-1',
                scoreColor,
              )}>
                {report.grade}
              </span>
            </div>

            <button
              onClick={() => {}}
              className="flex items-center gap-1.5 px-3 py-1.5 font-mono text-xs text-text-secondary border-2 border-bg-border hover:bg-bg-elevated transition-colors uppercase tracking-wider"
            >
              <Download size={11} />
              Export
            </button>

            <button
              onClick={onReset}
              className="flex items-center gap-1.5 px-3 py-1.5 font-mono text-xs text-text-secondary border-2 border-bg-border hover:bg-bg-elevated transition-colors uppercase tracking-wider"
            >
              <RotateCcw size={11} />
              New Session
            </button>
          </div>
        </div>
      </header>

      {/* Main workspace */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* Top panels */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left: Video + Score stacked */}
          <div className="w-[420px] flex-shrink-0 border-r-2 border-bg-border flex flex-col gap-0 overflow-y-auto">
            <div className="p-3 border-b-2 border-bg-border">
              <VideoPlayer
                ref={playerRef}
                src={videoSrc}
                onTimeUpdate={setCurrentTime}
              />
            </div>
            <div className="p-3">
              <ReadinessScore report={report} />
            </div>
          </div>

          {/* Right: Findings / Report tabs */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Tab bar — thick black underline style */}
            <div className="flex border-b-2 border-bg-border flex-shrink-0 px-4 pt-2">
              {(['findings', 'report'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveSection(tab)}
                  className={cn(
                    'px-4 py-2 font-display text-xl tracking-wider transition-colors relative',
                    activeSection === tab
                      ? 'text-text-primary'
                      : 'text-text-muted hover:text-text-secondary',
                  )}
                >
                  {tab === 'findings' ? 'AGENT FINDINGS' : 'REPORT SUMMARY'}
                  {activeSection === tab && (
                    <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-bg-border" />
                  )}
                </button>
              ))}
            </div>

            {/* Panel content */}
            <div className="flex-1 overflow-hidden p-3">
              {activeSection === 'findings' ? (
                <FindingsPanel
                  findings={allFindings}
                  onSelectFinding={handleFindingSelect}
                  activeTimestamp={currentTime}
                />
              ) : (
                <div className="overflow-y-auto h-full">
                  <ReportSummary report={report} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom: Timeline (always visible) */}
        <div className="border-t-2 border-bg-border p-3 flex-shrink-0 bg-bg-surface">
          <TimelinePanel
            annotations={report.timeline}
            duration={duration}
            currentTime={currentTime}
            onSeek={(t) => playerRef.current?.seekTo(t)}
            onSelectAnnotation={handleAnnotationSelect}
          />
        </div>
      </div>
    </div>
  );
}
