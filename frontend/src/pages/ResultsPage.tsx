import { useRef, useState, useCallback, useEffect, useMemo } from 'react';
import { RotateCcw, Download, Radio, Monitor, FileJson, FileSpreadsheet, FileText, ChevronDown } from 'lucide-react';
import { exportReportJSON, exportReportCSV, exportReportPDF } from '@/lib/export-utils';
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
  videoSrc?: string;
  timeline?: TimelineAnnotation[];
  onReset: () => void;
}

// ---------------------------------------------------------------------------
// Live session info panel (shown instead of VideoPlayer for live sessions)
// ---------------------------------------------------------------------------

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

const MODE_LABEL: Record<string, string> = {
  live_in_room: 'LIVE IN-ROOM',
  live_remote:  'LIVE REMOTE',
  live:         'LIVE SESSION',
};

const MODE_ICON: Record<string, typeof Radio> = {
  live_in_room: Radio,
  live_remote:  Monitor,
  live:         Radio,
};

interface LiveSessionInfoProps {
  sessionMode: string;
  durationSeconds?: number;
  cuesCount?: number;
  liveSummary?: string;
}

function LiveSessionInfoPanel({ sessionMode, durationSeconds, cuesCount, liveSummary }: LiveSessionInfoProps) {
  const label = MODE_LABEL[sessionMode] ?? 'LIVE SESSION';
  const Icon = MODE_ICON[sessionMode] ?? Radio;
  const cueLabel = sessionMode === 'live_remote' ? 'overlay cards' : 'earpiece cues';

  return (
    <div className="flex flex-col gap-3 p-4 border-2 border-bg-border bg-bg-surface">
      {/* Mode badge */}
      <div className="flex items-center gap-2">
        <Icon size={13} className="text-accent-red flex-shrink-0" />
        <span className="font-mono text-xs font-bold uppercase tracking-widest text-accent-red">
          {label}
        </span>
        <span className="font-mono text-xs text-text-muted ml-auto">completed</span>
      </div>

      {/* Stats row */}
      <div className="flex gap-4">
        {durationSeconds != null && (
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-xs text-text-muted uppercase tracking-widest" style={{ fontSize: '0.6rem' }}>Duration</span>
            <span className="font-display text-2xl leading-none text-text-primary">{formatDuration(durationSeconds)}</span>
          </div>
        )}
        {cuesCount != null && (
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-xs text-text-muted uppercase tracking-widest" style={{ fontSize: '0.6rem' }}>{cueLabel}</span>
            <span className="font-display text-2xl leading-none text-text-primary">{cuesCount}</span>
          </div>
        )}
      </div>

      {liveSummary && (
        <p className="font-mono text-xs text-text-muted leading-relaxed border-t border-bg-border pt-3">
          {liveSummary}
        </p>
      )}
    </div>
  );
}

function computeGrade(overall: number): string {
  if (overall >= 90) return 'A';
  if (overall >= 80) return 'B';
  if (overall >= 70) return 'C';
  if (overall >= 60) return 'D';
  return 'F';
}

// ---------------------------------------------------------------------------
// Main ResultsPage
// ---------------------------------------------------------------------------

export function ResultsPage({ report, sessionId, videoFile, videoSrc: videoSrcProp, timeline = [], onReset }: Props) {
  const playerRef = useRef<VideoPlayerHandle>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeSection, setActiveSection] = useState<'findings' | 'report'>('findings');
  const [activeFindingId, setActiveFindingId] = useState<string | undefined>();

  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showExportMenu) return;
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportMenu]);

  const handleExportJSON = useCallback(() => {
    exportReportJSON(report, sessionId);
    setShowExportMenu(false);
  }, [report, sessionId]);

  const handleExportCSV = useCallback(() => {
    exportReportCSV(report, sessionId);
    setShowExportMenu(false);
  }, [report, sessionId]);

  const handleExportPDF = useCallback(() => {
    exportReportPDF(report, sessionId);
    setShowExportMenu(false);
  }, [report, sessionId]);

  const videoSrc = useMemo(
    () => videoSrcProp ?? (videoFile ? URL.createObjectURL(videoFile) : undefined),
    [videoSrcProp, videoFile],
  );
  const isLiveSession = report.session_mode != null && report.session_mode.startsWith('live');

  const overall = report.score.overall;
  const grade = computeGrade(overall);

  const maxTimestamp = timeline.reduce((m, a) => Math.max(m, a.timestamp), 0);
  const duration = maxTimestamp > 0 ? maxTimestamp + 40 : 360;

  const scoreColor =
    overall >= 80 ? 'text-text-primary' :
    overall >= 60 ? 'text-accent-amber' : 'text-accent-red';

  const handleFindingSelect = useCallback((finding: Finding) => {
    if (finding.timestamp !== undefined) {
      playerRef.current?.seekTo(finding.timestamp);
    }
  }, []);

  const handleAnnotationSelect = useCallback((ann: TimelineAnnotation) => {
    playerRef.current?.seekTo(ann.timestamp);
    const finding = report.findings.find((f) => f.id === ann.finding_id);
    if (finding) {
      setActiveSection('findings');
      setActiveFindingId(finding.id);
    }
  }, [report]);

  return (
    <div className="h-screen bg-bg-base flex flex-col overflow-hidden">
      {/* Masthead top bar */}
      <header className="border-b-4 border-bg-border px-6 pt-3 pb-2 flex-shrink-0">
        <div className="flex items-end justify-between gap-4">
          <div className="flex items-end gap-4">
            <h1 className="font-display text-5xl leading-none tracking-wider text-text-primary">
              P<span className="italic">ITCH</span><span style={{ marginLeft: '0.1em' }}>PILOT</span>
            </h1>
            <span className="font-mono text-xs text-text-muted pb-1">
              SESSION&nbsp;
              <span className="text-text-secondary">{sessionId}</span>
            </span>
            {isLiveSession && (
              <span className="flex items-center gap-1.5 px-2 py-0.5 border border-accent-red bg-bg-surface mb-1">
                <Radio size={9} className="text-accent-red" />
                <span className="font-mono text-xs text-accent-red uppercase tracking-widest">
                  {MODE_LABEL[report.session_mode!] ?? 'LIVE'}
                </span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 pb-1">
            {/* Score pill */}
            <div className="border-2 border-bg-border px-3 py-1 flex items-center gap-2 bg-bg-surface">
              <span className="font-mono text-xs text-text-muted uppercase tracking-widest">Score</span>
              <span className={cn('font-display text-2xl leading-none', scoreColor)}>
                {overall}
              </span>
              <span className="font-mono text-xs text-text-muted">/100</span>
              <span className={cn(
                'font-display text-xl leading-none border-l-2 border-bg-border pl-2 ml-1',
                scoreColor,
              )}>
                {grade}
              </span>
            </div>

            {/* Export dropdown */}
            <div ref={exportMenuRef} className="relative">
              <button
                onClick={() => setShowExportMenu((v) => !v)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 font-mono text-xs border-2 transition-colors uppercase tracking-wider',
                  showExportMenu
                    ? 'bg-bg-elevated text-text-primary border-bg-border'
                    : 'text-text-secondary border-bg-border hover:bg-bg-elevated',
                )}
              >
                <Download size={11} />
                Export
                <ChevronDown size={9} className={cn('transition-transform', showExportMenu && 'rotate-180')} />
              </button>

              {showExportMenu && (
                <div className="absolute right-0 top-full mt-1 z-50 w-44 border-2 border-bg-border bg-bg-surface shadow-lg">
                  <button
                    onClick={handleExportJSON}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 font-mono text-xs text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors text-left uppercase tracking-wider border-b border-bg-border"
                  >
                    <FileJson size={11} />
                    JSON
                    <span className="ml-auto text-text-muted normal-case tracking-normal" style={{ fontSize: '0.6rem' }}>Full report</span>
                  </button>
                  <button
                    onClick={handleExportCSV}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 font-mono text-xs text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors text-left uppercase tracking-wider border-b border-bg-border"
                  >
                    <FileSpreadsheet size={11} />
                    CSV
                    <span className="ml-auto text-text-muted normal-case tracking-normal" style={{ fontSize: '0.6rem' }}>Findings</span>
                  </button>
                  <button
                    onClick={handleExportPDF}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 font-mono text-xs text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors text-left uppercase tracking-wider"
                  >
                    <FileText size={11} />
                    PDF
                    <span className="ml-auto text-text-muted normal-case tracking-normal" style={{ fontSize: '0.6rem' }}>Print view</span>
                  </button>
                </div>
              )}
            </div>

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
          {/* Left: Video (review mode) / Live Session Info (live mode) + Score stacked */}
          <div className="w-[420px] flex-shrink-0 border-r-2 border-bg-border flex flex-col gap-0 overflow-y-auto">
            <div className="p-3 border-b-2 border-bg-border">
              {isLiveSession ? (
                <LiveSessionInfoPanel
                  sessionMode={report.session_mode!}
                  durationSeconds={report.session_duration_seconds}
                  cuesCount={report.live_cues_count}
                  liveSummary={report.live_session_summary}
                />
              ) : (
                <VideoPlayer
                  ref={playerRef}
                  src={videoSrc}
                  onTimeUpdate={setCurrentTime}
                />
              )}
            </div>
            <div className="p-3">
              <ReadinessScore report={report} />
            </div>
          </div>

          {/* Right: Findings / Report tabs */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Tab bar */}
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
                  findings={report.findings}
                  onSelectFinding={handleFindingSelect}
                  activeTimestamp={currentTime}
                  activeFindingId={activeFindingId}
                />
              ) : (
                <div className="overflow-y-auto h-full">
                  <ReportSummary report={report} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom: Timeline */}
        <div className="border-t-2 border-bg-border p-3 flex-shrink-0 bg-bg-surface">
          <TimelinePanel
            annotations={timeline}
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
