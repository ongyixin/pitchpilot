import { useState } from 'react';
import { useSession } from '@/hooks/useSession';
import { useLiveSession } from '@/hooks/useLiveSession';
import { LandingPage } from '@/pages/LandingPage';
import { SetupPage } from '@/pages/SetupPage';
import { AnalyzingPage } from '@/pages/AnalyzingPage';
import { ResultsPage } from '@/pages/ResultsPage';
import { LiveSessionPage } from '@/pages/LiveSessionPage';
import { InRoomModePage } from '@/pages/InRoomModePage';
import { RemoteModePage } from '@/pages/RemoteModePage';
import type { AgentConfig, PersonaConfig } from '@/types/api';
import type { SessionMode } from '@/types';
import { isLiveMode } from '@/types';

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
  const { view, sessionId, status, report, timeline, error, startAnalysis, startDemo, reset } = useSession();
  const liveSession = useLiveSession();
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [appMode, setAppMode] = useState<SessionMode>('upload');
  const [showLanding, setShowLanding] = useState(true);
  const [initialSetupMode, setInitialSetupMode] = useState<'review' | 'live_in_room' | 'live_remote'>('review');

  const handleStart = (video: File, docs: File[], personas: PersonaConfig[], mode: SessionMode = 'review', presentationMaterials: File[] = [], agents: AgentConfig[] = []) => {
    setAppMode(mode);
    if (isLiveMode(mode)) {
      setVideoFile(null);
      liveSession.startSession(personas, docs, mode, presentationMaterials, agents);
    } else {
      setVideoFile(video);
      startAnalysis(video, docs, personas, presentationMaterials, agents);
    }
  };

  const handleReset = () => {
    if (isLiveMode(appMode)) {
      liveSession.reset();
    }
    reset();
    setAppMode('review');
    setInitialSetupMode('review');
    setShowLanding(true);
  };

  const handleBackToSetup = () => {
    if (isLiveMode(appMode)) {
      liveSession.reset();
    }
    reset();
    setAppMode('review');
    setInitialSetupMode('review');
    setShowLanding(false); // Go to SetupPage, not LandingPage
  };

  const handleLaunch = () => {
    setInitialSetupMode('review');
    setShowLanding(false);
  };

  const handleGoLive = () => {
    setInitialSetupMode('live_in_room');
    setShowLanding(false);
  };

  const handleLandingDemo = () => {
    setShowLanding(false);
    startDemo(DEMO_PERSONAS);
  };

  // ── Landing page ──
  if (showLanding) {
    return <LandingPage onLaunch={handleLaunch} onDemo={handleLandingDemo} onGoLive={handleGoLive} />;
  }

  // ── Error state ──
  const activeError = isLiveMode(appMode) ? liveSession.error : error;
  if (activeError && !isLiveMode(appMode)) {
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

  // ── Live mode routing (all live_* modes) ──
  if (isLiveMode(appMode)) {
    const liveState = liveSession.state;

    // Starting / connecting
    if (liveState === 'idle' || liveState === 'requesting_permissions' || liveState === 'connecting') {
      const isInRoom = appMode === 'live_in_room';
      return (
        <div
          className="min-h-screen flex items-center justify-center"
          style={isInRoom ? { background: '#050508' } : undefined}
        >
          <div
            className={isInRoom ? 'flex flex-col items-center gap-4 p-10' : 'flex flex-col items-center gap-4 border-2 border-bg-border p-10 shadow-brutal bg-bg-base'}
          >
            <div
              className="w-3 h-3 rounded-full animate-pulse"
              style={isInRoom ? { background: '#ef4444' } : undefined}
            />
            <p
              className="font-mono text-xs uppercase tracking-widest"
              style={isInRoom ? { color: '#555' } : undefined}
            >
              {liveState === 'requesting_permissions'
                ? (appMode === 'live_in_room' ? 'Requesting microphone…' : 'Requesting camera & microphone…')
                : 'Connecting to live session…'}
            </p>
          </div>
        </div>
      );
    }

    // Error
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

    // Active session — route to the mode-specific page
    if (liveState === 'live' || liveState === 'finalizing') {
      if (appMode === 'live_in_room') {
        return (
          <InRoomModePage
            {...liveSession}
            onSessionComplete={() => { /* handled via useEffect inside InRoomModePage */ }}
            onHome={handleBackToSetup}
          />
        );
      }
      if (appMode === 'live_remote') {
        return (
          <RemoteModePage
            {...liveSession}
            onSessionComplete={() => { /* handled via useEffect inside RemoteModePage */ }}
            onHome={handleBackToSetup}
          />
        );
      }
      // Legacy 'live' mode → existing LiveSessionPage
      return (
        <LiveSessionPage
          {...liveSession}
          onSessionComplete={() => { /* handled via useEffect inside LiveSessionPage */ }}
          onHome={handleBackToSetup}
        />
      );
    }

    // Session complete → results
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

  const handleHome = () => {
    reset();
    setAppMode('review');
    setInitialSetupMode('review');
    setShowLanding(true);
  };

  // ── Review / upload mode routing ──
  if (view === 'setup') {
    return <SetupPage onStart={handleStart} onStartDemo={startDemo} onHome={handleHome} initialMode={initialSetupMode} />;
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
        timeline={timeline}
        onReset={handleReset}
      />
    );
  }

  return <SetupPage onStart={handleStart} onStartDemo={startDemo} onHome={handleHome} initialMode={initialSetupMode} />;
}
