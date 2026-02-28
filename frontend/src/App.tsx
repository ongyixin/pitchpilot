import { useState } from 'react';
import { useSession } from '@/hooks/useSession';
import { useLiveSession } from '@/hooks/useLiveSession';
import { LandingPage } from '@/pages/LandingPage';
import { SetupPage } from '@/pages/SetupPage';
import { AnalyzingPage } from '@/pages/AnalyzingPage';
import { ResultsPage } from '@/pages/ResultsPage';
import { LiveSessionPage } from '@/pages/LiveSessionPage';
import type { PersonaConfig } from '@/types/api';
import type { SessionMode } from '@/types';

const DEMO_PERSONAS: PersonaConfig[] = [
  {
    id: 'skeptical_investor',
    label: 'Skeptical Investor',
    description: 'Stress-tests ROI, moat, and differentiation claims',
    icon: 'TrendingUp',
    enabled: true,
  },
  {
    id: 'technical_reviewer',
    label: 'Technical Reviewer',
    description: 'Probes architecture choices, performance, and scalability',
    icon: 'User',
    enabled: true,
  },
];

export default function App() {
  const { view, sessionId, status, report, error, startAnalysis, reset } = useSession();
  const liveSession = useLiveSession();
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [appMode, setAppMode] = useState<SessionMode>('upload');
  const [showLanding, setShowLanding] = useState(true);

  const handleStart = (video: File, docs: File[], personas: PersonaConfig[], mode: SessionMode = 'upload') => {
    setAppMode(mode);
    if (mode === 'live') {
      setVideoFile(null);
      liveSession.startSession(personas, docs);
    } else {
      setVideoFile(video);
      startAnalysis(video, docs, personas);
    }
  };

  const handleReset = () => {
    if (appMode === 'live') {
      liveSession.reset();
    }
    reset();
    setAppMode('upload');
    setShowLanding(true);
  };

  const handleLaunch = () => setShowLanding(false);

  const handleLandingDemo = () => {
    setShowLanding(false);
    const demoFile = new File([''], 'demo_pitch.mp4', { type: 'video/mp4' });
    setVideoFile(demoFile);
    startAnalysis(demoFile, [], DEMO_PERSONAS);
  };

  // ── Landing page ──
  if (showLanding) {
    return <LandingPage onLaunch={handleLaunch} onDemo={handleLandingDemo} />;
  }

  // ── Error state ──
  const activeError = appMode === 'live' ? liveSession.error : error;
  if (activeError && appMode !== 'live') {
    return (
      <div className="min-h-screen bg-bg-base flex items-center justify-center">
        <div className="text-center space-y-4 border-2 border-accent-red p-8 shadow-brutal-red">
          <p className="font-mono text-accent-red text-sm font-bold uppercase">Analysis failed</p>
          <p className="text-text-muted text-xs">{activeError}</p>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-bg-surface border-2 border-bg-border text-sm text-text-secondary hover:text-text-primary font-mono uppercase tracking-wider transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Live mode routing ──
  if (appMode === 'live') {
    const liveState = liveSession.state;

    if (liveState === 'idle' || liveState === 'requesting_permissions' || liveState === 'connecting') {
      // Still starting — show a brief connecting overlay
      return (
        <div className="min-h-screen bg-bg-base flex items-center justify-center">
          <div className="flex flex-col items-center gap-4 border-2 border-bg-border p-10 shadow-brutal">
            <div className="w-3 h-3 bg-accent-red animate-pulse" />
            <p className="font-mono text-xs text-text-secondary uppercase tracking-widest">
              {liveState === 'requesting_permissions'
                ? 'Requesting camera & microphone…'
                : 'Connecting to live session…'}
            </p>
          </div>
        </div>
      );
    }

    if (liveState === 'error') {
      return (
        <div className="min-h-screen bg-bg-base flex items-center justify-center">
          <div className="text-center space-y-4 border-2 border-accent-red p-8 shadow-brutal-red">
            <p className="font-mono text-accent-red text-sm font-bold uppercase">Session failed</p>
            <p className="text-text-muted text-xs">{liveSession.error}</p>
            <button
              onClick={handleReset}
              className="px-4 py-2 bg-bg-surface border-2 border-bg-border text-sm text-text-secondary hover:text-text-primary font-mono uppercase tracking-wider transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    if ((liveState === 'live' || liveState === 'finalizing') && liveSession.state !== 'complete') {
      return (
        <LiveSessionPage
          {...liveSession}
          onSessionComplete={() => {
            // Transition happens inside LiveSessionPage via the useEffect
          }}
        />
      );
    }

    if (liveState === 'complete' && liveSession.report) {
      return (
        <ResultsPage
          report={liveSession.report}
          sessionId={liveSession.sessionId ?? 'live-session'}
          videoFile={undefined}
          onReset={handleReset}
        />
      );
    }
  }

  // ── Upload mode routing ──
  if (view === 'setup') {
    return <SetupPage onStart={handleStart} />;
  }

  if (view === 'analyzing') {
    return <AnalyzingPage status={status} sessionId={sessionId} />;
  }

  if (view === 'results' && report) {
    return (
      <ResultsPage
        report={report}
        sessionId={sessionId ?? 'unknown'}
        videoFile={videoFile ?? undefined}
        onReset={handleReset}
      />
    );
  }

  return <SetupPage onStart={handleStart} />;
}
