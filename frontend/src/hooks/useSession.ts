import { useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';
import { MOCK_STATUS_SEQUENCE, MOCK_REPORT, MOCK_TIMELINE } from '@/lib/mock-data';
import type { SessionStatusResponse, ReadinessReport, TimelineAnnotation } from '@/types';
import type { AgentConfig, PersonaConfig } from '@/types/api';

export type AppView = 'setup' | 'analyzing' | 'results';

// Read from Vite env var; defaults to true (safe for development without Ollama)
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export function useSession() {
  const [view, setView] = useState<AppView>('setup');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatusResponse | null>(null);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [timeline, setTimeline] = useState<TimelineAnnotation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mockStepRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startMockPolling = useCallback(() => {
    mockStepRef.current = 0;
    pollingRef.current = setInterval(() => {
      const step = MOCK_STATUS_SEQUENCE[mockStepRef.current];
      if (!step) return;
      setStatus(step as unknown as SessionStatusResponse);
      mockStepRef.current++;
      if (step.status === 'complete') {
        stopPolling();
        setReport(MOCK_REPORT as unknown as ReadinessReport);
        setTimeline((MOCK_TIMELINE ?? []) as unknown as TimelineAnnotation[]);
        setTimeout(() => setView('results'), 600);
      } else if (step.status === 'error' || step.status === 'failed') {
        stopPolling();
        setError((step as unknown as Record<string, string>).error ?? 'Analysis failed.');
      }
    }, 900);
  }, [stopPolling]);

  const startRealPolling = useCallback(
    (id: string) => {
      let consecutiveErrors = 0;
      pollingRef.current = setInterval(async () => {
        try {
          const s = await api.getStatus(id);
          setStatus(s);
          consecutiveErrors = 0;
          if (s.status === 'complete') {
            stopPolling();
            const [r, t] = await Promise.all([
              api.getReport(id),
              api.getTimeline(id).catch(() => ({ session_id: id, annotations: [] })),
            ]);
            setReport(r);
            setTimeline(t.annotations);
            setTimeout(() => setView('results'), 600);
          } else if (s.status === 'failed') {
            stopPolling();
            setError(s.error_message ?? 'Analysis failed.');
          }
        } catch (err) {
          // Retry up to 3 consecutive network errors before giving up
          consecutiveErrors++;
          if (consecutiveErrors >= 3) {
            stopPolling();
            setError(err instanceof Error ? err.message : 'Polling failed — is the backend running?');
          }
        }
      }, 2000);
    },
    [stopPolling],
  );

  const startAnalysis = useCallback(
    async (video: File, docs: File[], personas: PersonaConfig[], presentationMaterials: File[] = [], agents: AgentConfig[] = []) => {
      setError(null);
      setView('analyzing');

      const enabledPersonas = personas.filter((p) => p.enabled).map((p) => p.id);
      const enabledAgents = agents.filter((a) => a.enabled).map((a) => a.id);

      if (USE_MOCK) {
        setSessionId('demo-001');
        startMockPolling();
        return;
      }

      try {
        const { session_id } = await api.startSession(video, docs, enabledPersonas, presentationMaterials, enabledAgents);
        setSessionId(session_id);
        startRealPolling(session_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start session.');
        setView('setup');
      }
    },
    [startMockPolling, startRealPolling],
  );

  const startDemo = useCallback(
    async (personas: PersonaConfig[]) => {
      setError(null);
      setView('analyzing');

      const enabledPersonas = personas.filter((p) => p.enabled).map((p) => p.id);

      if (USE_MOCK) {
        setSessionId('demo-001');
        startMockPolling();
        return;
      }

      try {
        const { session_id } = await api.startDemoSession(enabledPersonas);
        setSessionId(session_id);
        startRealPolling(session_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start demo session.');
        setView('setup');
      }
    },
    [startMockPolling, startRealPolling],
  );

  const reset = useCallback(() => {
    stopPolling();
    setView('setup');
    setSessionId(null);
    setStatus(null);
    setReport(null);
    setTimeline([]);
    setError(null);
    mockStepRef.current = 0;
  }, [stopPolling]);

  return { view, sessionId, status, report, timeline, error, startAnalysis, startDemo, reset };
}
