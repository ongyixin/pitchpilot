/**
 * useLiveSession — manages the full lifecycle of a Livestream Mode session.
 *
 * Responsibilities:
 *  - Request camera + microphone access (getUserMedia)
 *  - Open a WebSocket to /api/session/live
 *  - Record audio in 2-second chunks via MediaRecorder and send over WS
 *  - Capture periodic JPEG frame snapshots via canvas and send over WS
 *  - Parse incoming WS messages (findings, nudges, transcript updates)
 *  - Handle session finalization and fetch the completed report
 *  - Provide a mock mode (USE_MOCK=true) that simulates all of the above
 */

import {
  useState,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { api, getLiveSessionWsUrl } from '@/lib/api';
import type {
  Finding,
  LiveFeedMessage,
  LiveNudge,
  LiveTranscriptSegment,
  ReadinessReport,
} from '@/types';
import type { PersonaConfig } from '@/types/api';

// ---------------------------------------------------------------------------
// Mock mode flag — matches useSession.ts convention
// ---------------------------------------------------------------------------
const USE_MOCK = true;

// Prefix bytes for binary WS frames (must match backend/live_ws.py)
const MSG_AUDIO = 0x01;
const MSG_FRAME = 0x02;

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_TRANSCRIPT_CHUNKS = [
  "Our platform is fully automated — no manual review required.",
  "We achieve 99.9% uptime across all enterprise tiers.",
  "All customer data is stored on-device — nothing leaves your network.",
  "We outperform every competitor by 3× on inference speed.",
  "The integration can be deployed in under an hour.",
];

const MOCK_FINDINGS: Omit<Finding, 'id'>[] = [
  {
    agent: 'compliance', severity: 'critical',
    title: "'Fully automated' conflicts with policy §3.2",
    detail: "Your enterprise policy requires human review for model outputs above a confidence threshold.",
    suggestion: "Rephrase to: 'Automated with optional human-in-the-loop review.'",
    timestamp: 8, live: true,
  },
  {
    agent: 'coach', severity: 'warning',
    title: "Pacing is fast — slow down for key metrics",
    detail: "The 99.9% uptime claim was delivered quickly. Pause after key numbers to let them land.",
    suggestion: "Add a 1-second pause after stating uptime figures.",
    timestamp: 22, live: true,
  },
  {
    agent: 'compliance', severity: 'warning',
    title: "'Nothing leaves your network' needs qualification",
    detail: "The blanket privacy claim may be false for customers who enable optional cloud sync.",
    suggestion: "Add 'by default' and mention the opt-in cloud sync explicitly.",
    timestamp: 35, live: true,
  },
  {
    agent: 'coach', severity: 'critical',
    title: "Speed metric lacks benchmark context",
    detail: "'3× faster' is compelling but the baseline is never stated.",
    suggestion: "Name the competitor and link to a reproducible benchmark.",
    timestamp: 48, live: true,
  },
  {
    agent: 'persona', severity: 'warning',
    title: "Skeptical Investor: differentiation is unclear",
    detail: "A skeptical investor would immediately ask how this differs from a well-prompted ChatGPT.",
    suggestion: "Lead with the on-device / privacy differentiator earlier.",
    timestamp: 60, live: true,
  },
];

let _mockIdCounter = 0;
const mockId = () => `live-${++_mockIdCounter}`;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LiveSessionState =
  | 'idle'
  | 'requesting_permissions'
  | 'connecting'
  | 'live'
  | 'finalizing'
  | 'complete'
  | 'error';

export interface UseLiveSessionReturn {
  state: LiveSessionState;
  sessionId: string | null;
  findings: Finding[];
  nudges: LiveNudge[];
  transcript: LiveTranscriptSegment[];
  report: ReadinessReport | null;
  error: string | null;
  elapsedSeconds: number;
  mediaStream: MediaStream | null;
  startSession: (personas: PersonaConfig[], docFiles?: File[]) => Promise<void>;
  endSession: () => void;
  dismissNudge: (id: string) => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useLiveSession(): UseLiveSessionReturn {
  const [state, setState] = useState<LiveSessionState>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [nudges, setNudges] = useState<LiveNudge[]>([]);
  const [transcript, setTranscript] = useState<LiveTranscriptSegment[]>([]);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const frameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoElRef = useRef<HTMLVideoElement | null>(null);
  const sessionStartRef = useRef<number>(0);
  const mockIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mockIndexRef = useRef(0);

  // Cleanup helper
  const cleanup = useCallback(() => {
    if (mediaRecorderRef.current?.state !== 'inactive') {
      try { mediaRecorderRef.current?.stop(); } catch { /* ignore */ }
    }
    mediaRecorderRef.current = null;

    if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    if (mockIntervalRef.current) clearInterval(mockIntervalRef.current);
    frameIntervalRef.current = null;
    timerIntervalRef.current = null;
    mockIntervalRef.current = null;

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
    }
  }, [mediaStream]);

  // Elapsed timer
  const startTimer = useCallback(() => {
    sessionStartRef.current = Date.now();
    timerIntervalRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - sessionStartRef.current) / 1000));
    }, 1000);
  }, []);

  // -------------------------------------------------------------------------
  // Mock mode
  // -------------------------------------------------------------------------

  const startMockSession = useCallback(async (_personas: PersonaConfig[]) => {
    setState('requesting_permissions');
    await new Promise((r) => setTimeout(r, 500));

    setState('connecting');
    await new Promise((r) => setTimeout(r, 400));

    const sid = `mock-live-${Date.now()}`;
    setSessionId(sid);
    setState('live');
    startTimer();

    // Simulate a fake MediaStream (null — page will show placeholder)
    mockIndexRef.current = 0;

    // Drip transcript + findings every few seconds
    let transcriptIdx = 0;
    let findingIdx = 0;

    mockIntervalRef.current = setInterval(() => {
      const now = Math.floor((Date.now() - sessionStartRef.current) / 1000);

      // New transcript segment every 3 seconds
      if (transcriptIdx < MOCK_TRANSCRIPT_CHUNKS.length) {
        setTranscript((prev) => [
          ...prev,
          {
            text: MOCK_TRANSCRIPT_CHUNKS[transcriptIdx],
            start_time: now,
            end_time: now + 2,
          },
        ]);
        transcriptIdx++;
      }

      // New finding every 8 seconds
      if (findingIdx < MOCK_FINDINGS.length && now > 0 && now % 8 === 0) {
        const raw = MOCK_FINDINGS[findingIdx];
        findingIdx++;
        const finding: Finding = { ...raw, id: mockId(), timestamp: now };

        if (finding.agent === 'coach' && finding.severity !== 'critical') {
          // Emit as nudge
          setNudges((prev) => [
            ...prev,
            { id: finding.id, agent: finding.agent, message: finding.detail, suggestion: finding.suggestion, severity: finding.severity, elapsed: now },
          ]);
          // Auto-dismiss nudge after 5 s
          setTimeout(() => {
            setNudges((prev) => prev.filter((n) => n.id !== finding.id));
          }, 5000);
        } else {
          setFindings((prev) => [finding, ...prev]);
        }
      }
    }, 3000);
  }, [startTimer]);

  const endMockSession = useCallback(async () => {
    if (mockIntervalRef.current) clearInterval(mockIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);

    setState('finalizing');
    await new Promise((r) => setTimeout(r, 2000));

    // Build a mock report from accumulated findings
    const { MOCK_REPORT } = await import('@/lib/mock-data');
    setReport(MOCK_REPORT);
    setState('complete');
  }, []);

  // -------------------------------------------------------------------------
  // Real WebSocket mode
  // -------------------------------------------------------------------------

  const sendBinary = useCallback((tag: number, data: ArrayBuffer) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const buf = new Uint8Array(1 + data.byteLength);
    buf[0] = tag;
    buf.set(new Uint8Array(data), 1);
    ws.send(buf.buffer);
  }, []);

  const startFrameCapture = useCallback((stream: MediaStream) => {
    // Create an off-screen video element to draw frames from
    const video = document.createElement('video');
    video.srcObject = stream;
    video.muted = true;
    video.play().catch(() => { /* ignore */ });
    videoElRef.current = video;

    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 360;
    canvasRef.current = canvas;

    let frameIndex = 0;
    frameIntervalRef.current = setInterval(() => {
      const ctx = canvas.getContext('2d');
      if (!ctx || !video.readyState) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (!blob) return;
        blob.arrayBuffer().then((buf) => {
          sendBinary(MSG_FRAME, buf);
          frameIndex++;
        });
      }, 'image/jpeg', 0.6);
    }, 5000);
  }, [sendBinary]);

  const startRealSession = useCallback(async (personas: PersonaConfig[], docFiles: File[] = []) => {
    setState('requesting_permissions');

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch (err) {
      setError(`Camera/microphone access denied: ${err instanceof Error ? err.message : err}`);
      setState('error');
      return;
    }
    setMediaStream(stream);

    setState('connecting');

    // Read policy text from first doc file if provided
    let policyText = '';
    if (docFiles.length > 0) {
      try {
        policyText = await docFiles[0].text();
      } catch { /* ignore non-text files */ }
    }

    const ws = new WebSocket(getLiveSessionWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'init',
        personas: personas.filter((p) => p.enabled).map((p) => p.label),
        policy_text: policyText,
        title: 'Live Rehearsal',
      }));
    };

    ws.onerror = () => {
      setError('WebSocket connection failed. Is the backend running?');
      setState('error');
      cleanup();
    };

    ws.onclose = (e) => {
      if (state === 'live' || state === 'connecting') {
        setError(`Connection closed unexpectedly (${e.code})`);
        setState('error');
      }
    };

    ws.onmessage = async (event) => {
      if (typeof event.data !== 'string') return;
      const msg: LiveFeedMessage = JSON.parse(event.data);

      switch (msg.type) {
        case 'session_created': {
          if (msg.session_id) setSessionId(msg.session_id);
          setState('live');
          startTimer();
          startFrameCapture(stream);
          startAudioCapture(stream);
          break;
        }
        case 'transcript_update': {
          if (msg.segments) {
            setTranscript((prev) => [...prev, ...msg.segments!]);
          }
          break;
        }
        case 'finding': {
          if (msg.finding) {
            setFindings((prev) => [msg.finding!, ...prev]);
          }
          break;
        }
        case 'nudge': {
          const nudgeId = mockId();
          const nudge: LiveNudge = {
            id: nudgeId,
            agent: msg.agent ?? 'coach',
            message: msg.message ?? '',
            suggestion: msg.suggestion,
            severity: msg.severity ?? 'info',
            elapsed: msg.elapsed ?? 0,
          };
          setNudges((prev) => [...prev, nudge]);
          // Auto-dismiss after 5 seconds
          setTimeout(() => setNudges((prev) => prev.filter((n) => n.id !== nudgeId)), 5000);
          break;
        }
        case 'session_complete': {
          setState('finalizing');
          if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
          if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
          try {
            const sid = msg.session_id ?? sessionId;
            if (sid) {
              const r = await api.getReport(sid);
              setReport(r);
            }
          } catch (err) {
            setError(`Could not fetch report: ${err instanceof Error ? err.message : err}`);
          }
          setState('complete');
          break;
        }
        case 'error': {
          setError(msg.message ?? 'Unknown error from server');
          setState('error');
          break;
        }
      }
    };

    // Start audio capture — defined inline to close over `stream` and `ws`
    function startAudioCapture(s: MediaStream) {
      // Use audio-only stream for the recorder to avoid duplicating the video track
      const audioStream = new MediaStream(s.getAudioTracks());
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const recorder = new MediaRecorder(audioStream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          e.data.arrayBuffer().then((buf) => sendBinary(MSG_AUDIO, buf));
        }
      };

      recorder.start(2000); // 2-second timeslice
    }
  }, [startTimer, startFrameCapture, sendBinary, cleanup, sessionId, state]);

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  const startSession = useCallback(async (personas: PersonaConfig[], docFiles: File[] = []) => {
    setError(null);
    setFindings([]);
    setNudges([]);
    setTranscript([]);
    setReport(null);
    setElapsedSeconds(0);

    if (USE_MOCK) {
      await startMockSession(personas);
    } else {
      await startRealSession(personas, docFiles);
    }
  }, [startMockSession, startRealSession]);

  const endSession = useCallback(() => {
    if (USE_MOCK) {
      endMockSession();
      return;
    }

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'end_session' }));
      setState('finalizing');
    }

    // Stop audio recorder
    if (mediaRecorderRef.current?.state !== 'inactive') {
      try { mediaRecorderRef.current?.stop(); } catch { /* ignore */ }
    }
    if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
  }, [endMockSession]);

  const dismissNudge = useCallback((id: string) => {
    setNudges((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setState('idle');
    setSessionId(null);
    setFindings([]);
    setNudges([]);
    setTranscript([]);
    setReport(null);
    setError(null);
    setElapsedSeconds(0);
    setMediaStream(null);
    mockIndexRef.current = 0;
  }, [cleanup]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    state,
    sessionId,
    findings,
    nudges,
    transcript,
    report,
    error,
    elapsedSeconds,
    mediaStream,
    startSession,
    endSession,
    dismissNudge,
    reset,
  };
}
