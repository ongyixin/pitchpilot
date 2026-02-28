import { useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';
import { MOCK_STATUS_SEQUENCE, MOCK_REPORT } from '@/lib/mock-data';
import type { StatusResponse, ReadinessReport, PersonaConfig } from '@/types/api';

export type AppView = 'setup' | 'analyzing' | 'results';

const USE_MOCK = true; // flip to false once backend is wired

export function useSession() {
  const [view, setView] = useState<AppView>('setup');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [report, setReport] = useState<ReadinessReport | null>(null);
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
      setStatus(step);
      mockStepRef.current++;
      if (step.status === 'complete') {
        stopPolling();
        setReport(MOCK_REPORT);
        setTimeout(() => setView('results'), 600);
      } else if (step.status === 'error') {
        stopPolling();
        setError(step.error ?? 'Analysis failed.');
      }
    }, 900);
  }, [stopPolling]);

  const startRealPolling = useCallback(
    (id: string) => {
      pollingRef.current = setInterval(async () => {
        try {
          const s = await api.getStatus(id);
          setStatus(s);
          if (s.status === 'complete') {
            stopPolling();
            const r = await api.getReport(id);
            setReport(r);
            setTimeout(() => setView('results'), 600);
          } else if (s.status === 'error') {
            stopPolling();
            setError(s.error ?? 'Analysis failed.');
          }
        } catch (err) {
          stopPolling();
          setError(err instanceof Error ? err.message : 'Polling failed.');
        }
      }, 2000);
    },
    [stopPolling],
  );

  const startAnalysis = useCallback(
    async (video: File, docs: File[], personas: PersonaConfig[]) => {
      setError(null);
      setView('analyzing');

      const enabledPersonas = personas.filter((p) => p.enabled).map((p) => p.id);

      if (USE_MOCK) {
        setSessionId('demo-001');
        startMockPolling();
        return;
      }

      try {
        const { session_id } = await api.startSession(video, docs, enabledPersonas);
        setSessionId(session_id);
        startRealPolling(session_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start session.');
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
    setError(null);
    mockStepRef.current = 0;
  }, [stopPolling]);

  return { view, sessionId, status, report, error, startAnalysis, reset };
}
