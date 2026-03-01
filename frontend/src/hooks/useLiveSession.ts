/**
 * useLiveSession — manages the full lifecycle of a Livestream Mode session.
 *
 * Supports three live modes:
 *   "live"         — legacy rehearsal mode (audio + camera, nudges to screen)
 *   "live_in_room" — earpiece coaching (earpiece_cue messages, audio-only UI)
 *   "live_remote"  — presenter overlay (teleprompter, objection prep, script suggestions)
 *
 * Responsibilities:
 *  - Request camera + microphone access (getUserMedia)
 *  - Open a WebSocket to /api/session/live
 *  - Record audio in 2-second chunks via MediaRecorder and send over WS
 *  - Capture periodic JPEG frame snapshots via canvas and send over WS
 *  - Parse all incoming WS messages and fan out to the appropriate state slice
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
  EarpieceCue,
  Finding,
  LiveFeedMessage,
  LiveNudge,
  LiveTranscriptSegment,
  ObjectionCard,
  ScriptSuggestion,
  SessionMode,
} from '@/types';
import type { AgentConfig, PersonaConfig, ReadinessReport } from '@/types/api';

// ---------------------------------------------------------------------------
// Mock mode flag — read from Vite env var; defaults to true (safe for dev)
// ---------------------------------------------------------------------------
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

// Prefix bytes for binary WS frames (must match backend/live_ws.py)
const MSG_AUDIO = 0x01;
const MSG_FRAME = 0x02;

// ---------------------------------------------------------------------------
// Mock data — shared
// ---------------------------------------------------------------------------

const MOCK_TRANSCRIPT_CHUNKS = [
  "Good morning, we are presenting PitchPilot, an on-device AI sales coach for InstaLILY sales reps.",
  "PitchPilot runs locally on your laptop because your sales playbook and pricing strategy cannot leave the device.",
  "Our system integrates seamlessly with your existing CRM and ERP workflows including SAP and Oracle.",
  "We guarantee ROI within 90 days for every InstaLILY customer.",
  "Our on-device model processes sales conversations in real time with no latency.",
  "We are the only company building domain-trained on-device sales coaching for distribution verticals.",
  "Our finetuned FunctionGemma model outperforms base Gemma on enterprise sales objection detection.",
  "InstaLILY sales reps using PitchPilot will close 40% more enterprise deals.",
];

const MOCK_FINDINGS: Omit<Finding, 'id'>[] = [
  {
    agent: 'coach', severity: 'info',
    title: "Strong opening — value proposition is clear",
    detail: "PitchPilot is immediately positioned as on-device AI coaching for InstaLILY reps. Privacy-first angle lands well.",
    cue_hint: "strong open",
    timestamp: 10, live: true,
  },
  {
    agent: 'compliance', severity: 'warning',
    title: "Integration claim lacks technical detail",
    detail: "'Seamless integration' with SAP and Oracle is vague. Ops managers will immediately ask for data mapping specifics, timeline, and cost.",
    suggestion: "Prepare ETL process details, 6-8 week pilot timeline, and a $15K–$30K cost range.",
    cue_hint: "integration detail needed",
    timestamp: 48, live: true,
  },
  {
    agent: 'persona', severity: 'critical',
    title: "Ops Manager: integration question incoming",
    detail: "An ops manager will challenge the SAP/Oracle claim — they need data mapping, transformation steps, timeline, and cost.",
    suggestion: "Lead with a phased integration strategy and name your ETL tooling.",
    cue_hint: "integration question likely",
    timestamp: 62, live: true,
  },
  {
    agent: 'persona', severity: 'critical',
    title: "Investor: ROI guarantee needs quantification",
    detail: "Guaranteeing ROI without defining it will stop an investor cold. They want numbers and case studies.",
    suggestion: "Define ROI as 15-20% increase in close rates and reference beta testing data.",
    cue_hint: "ROI question incoming",
    timestamp: 85, live: true,
  },
  {
    agent: 'persona', severity: 'critical',
    title: "CTO: on-device architecture question incoming",
    detail: "'Only company' with domain-trained on-device coaching is a bold claim — a CTO will probe the model architecture and privacy model immediately.",
    suggestion: "Cover FunctionGemma finetuning, federated learning, encryption at rest/transit, and opt-out controls.",
    cue_hint: "technical deep dive likely",
    timestamp: 130, live: true,
  },
];

// ---------------------------------------------------------------------------
// Mock data — live_remote specific
// ---------------------------------------------------------------------------

const MOCK_TELEPROMPTER_SEQUENCES: string[][] = [
  [
    "Open with the 'black box' problem — why rehearsals fail",
    "Introduce on-device privacy as the critical differentiator",
    "Bridge: 'That's the problem — let's see PitchPilot solve it live'",
  ],
  [
    "Walk through: upload → 3 agents analyze → readiness report",
    "Highlight the 90-second turnaround on a 5-min video",
    "Point to specific findings: compliance, coach, and persona tabs",
  ],
  [
    "Transition to business model — enterprise compliance is the wedge",
    "Mention fine-tuning: FunctionGemma 270M trained on our tool surface",
    "Close: 'Three Gemma models. Everything local. No data leaves the device.'",
  ],
];

const MOCK_OBJECTION_CARDS: Omit<ObjectionCard, 'id'>[] = [
  {
    question: "How is this different from asking ChatGPT to review my pitch?",
    suggested_answer: "Three key differences: (1) on-device privacy — no data leaves the machine, (2) multimodal — analyzes video, slides, and audio together, not just text, (3) specialized agents fine-tuned for pitch evaluation.",
    persona: "Skeptical Investor",
    difficulty: "critical",
  },
  {
    question: "What's the inference latency on a consumer machine?",
    suggested_answer: "M2 MacBook Pro: ~90 seconds for a 5-minute video. All local — no cloud round-trip. In live mode the first cue arrives in under 8 seconds.",
    persona: "Technical Reviewer",
    difficulty: "warning",
  },
  {
    question: "What's the all-in cost over three years, and can you provide a reference customer with measurable ROI?",
    suggested_answer: "Annual per-seat SaaS with no implementation fee. Design partners report 18% lift in first-call conversion and 40% reduction in manager coaching hours. I can connect you with two reference customers in enterprise SaaS.",
    persona: "Procurement Manager",
    difficulty: "critical",
  },
];

let _mockIdCounter = 0;
const mockId = () => `live-${++_mockIdCounter}`;

/**
 * Returns true if a cue at the given severity should be delivered at the
 * current sensitivity level.
 *
 *   high   → all cues (critical + warning + info)
 *   medium → critical + warning only
 *   low    → critical only
 */
function _cuePassesSensitivity(severity: string, level: CueSensitivity): boolean {
  if (level === 'high') return true;
  if (level === 'medium') return severity === 'critical' || severity === 'warning';
  return severity === 'critical';
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Controls which severity levels produce earpiece cues. */
export type CueSensitivity = 'high' | 'medium' | 'low';

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
  mode: SessionMode;
  sessionId: string | null;
  findings: Finding[];
  nudges: LiveNudge[];
  transcript: LiveTranscriptSegment[];
  report: ReadinessReport | null;
  error: string | null;
  elapsedSeconds: number;
  mediaStream: MediaStream | null;
  // live_in_room
  cues: EarpieceCue[];
  muted: boolean;
  sensitivity: CueSensitivity;
  toggleMute: () => void;
  setSensitivity: (s: CueSensitivity) => void;
  // live_remote
  teleprompterPoints: string[];
  objections: ObjectionCard[];
  scriptSuggestions: ScriptSuggestion[];
  startSession: (personas: PersonaConfig[], docFiles?: File[], sessionMode?: SessionMode, presentationMaterials?: File[], agents?: AgentConfig[]) => Promise<void>;
  endSession: () => void;
  dismissNudge: (id: string) => void;
  dismissScriptSuggestion: (id: string) => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useLiveSession(): UseLiveSessionReturn {
  const [state, setState] = useState<LiveSessionState>('idle');
  const [mode, setMode] = useState<SessionMode>('live');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [nudges, setNudges] = useState<LiveNudge[]>([]);
  const [transcript, setTranscript] = useState<LiveTranscriptSegment[]>([]);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  // live_in_room
  const [cues, setCues] = useState<EarpieceCue[]>([]);
  const [muted, setMuted] = useState(false);
  const [sensitivity, setSensitivity] = useState<CueSensitivity>('medium');
  // live_remote
  const [teleprompterPoints, setTeleprompterPoints] = useState<string[]>([]);
  const [objections, setObjections] = useState<ObjectionCard[]>([]);
  const [scriptSuggestions, setScriptSuggestions] = useState<ScriptSuggestion[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const frameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoElRef = useRef<HTMLVideoElement | null>(null);
  const sessionStartRef = useRef<number>(0);
  const sessionModeRef = useRef<SessionMode>('live');
  const mockIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mockIndexRef = useRef(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const mutedRef = useRef(muted);
  const sensitivityRef = useRef(sensitivity);

  // Keep refs in sync with state so the playback callback reads fresh values
  useEffect(() => { mutedRef.current = muted; }, [muted]);
  useEffect(() => { sensitivityRef.current = sensitivity; }, [sensitivity]);

  /**
   * Play a base64-encoded audio blob through the earpiece.
   * Supports WAV, AIFF, MP3, and Opus — browsers handle the decoding.
   * Returns immediately if muted or if audio_b64 is null.
   */
  const playEarpieceAudio = useCallback((audio_b64: string | null) => {
    if (!audio_b64 || mutedRef.current) return;

    try {
      const raw = atob(audio_b64);
      const buf = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);

      if (!audioCtxRef.current) {
        audioCtxRef.current = new AudioContext();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      ctx.decodeAudioData(buf.buffer.slice(0))
        .then((decoded) => {
          const src = ctx.createBufferSource();
          src.buffer = decoded;
          src.connect(ctx.destination);
          src.start(0);
        })
        .catch(() => {
          // Fallback: use an HTMLAudioElement with a data URI
          const blob = new Blob([buf], { type: 'audio/wav' });
          const url = URL.createObjectURL(blob);
          const el = new Audio(url);
          el.play().finally(() => URL.revokeObjectURL(url));
        });
    } catch {
      // Decoding failed — text-only fallback (no-op)
    }
  }, []);

  // Cleanup helper
  const cleanup = useCallback(() => {
    if (audioIntervalRef.current) clearInterval(audioIntervalRef.current);
    audioIntervalRef.current = null;

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

    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
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

  const startMockSession = useCallback(async (
    _personas: PersonaConfig[],
    sessionMode: SessionMode = 'live',
  ) => {
    setState('requesting_permissions');
    await new Promise((r) => setTimeout(r, 500));

    setState('connecting');
    await new Promise((r) => setTimeout(r, 400));

    const sid = `mock-live-${Date.now()}`;
    setSessionId(sid);
    setState('live');
    startTimer();

    mockIndexRef.current = 0;

    let transcriptIdx = 0;
    let findingIdx = 0;
    let teleprompterIdx = 0;
    let objectionIdx = 0;
    let lastFindingSec = 0;
    let lastTeleprompterSec = -20;
    let lastObjectionSec = -30;

    // Emit first teleprompter + objection immediately for remote mode
    if (sessionMode === 'live_remote') {
      setTeleprompterPoints(MOCK_TELEPROMPTER_SEQUENCES[0]);
      teleprompterIdx = 1;
      if (MOCK_OBJECTION_CARDS.length > 0) {
        setObjections([{ ...MOCK_OBJECTION_CARDS[0], id: mockId() }]);
        objectionIdx = 1;
        lastObjectionSec = 0;
      }
    }

    mockIntervalRef.current = setInterval(() => {
      const now = Math.floor((Date.now() - sessionStartRef.current) / 1000);

      // Transcript segment every 3 ticks
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

      // Finding every ~8 seconds (elapsed-based, not modular arithmetic)
      if (findingIdx < MOCK_FINDINGS.length && now - lastFindingSec >= 8) {
        lastFindingSec = now;
        const raw = MOCK_FINDINGS[findingIdx];
        findingIdx++;
        const finding: Finding = { ...raw, id: mockId(), timestamp: now };

        if (finding.agent === 'coach' && finding.severity !== 'critical') {
          // Coach warnings → nudge toast
          const nudgeId = finding.id;
          setNudges((prev) => [
            ...prev,
            { id: nudgeId, agent: finding.agent, message: finding.detail, suggestion: finding.suggestion, severity: finding.severity, elapsed: now },
          ]);
          setTimeout(() => {
            setNudges((prev) => prev.filter((n) => n.id !== nudgeId));
          }, 5000);
        } else {
          setFindings((prev) => [finding, ...prev]);
        }

        // Mode-specific extras derived from the finding
        if (sessionMode === 'live_remote' && finding.suggestion) {
          const suggId = mockId();
          const suggestion: ScriptSuggestion = {
            id: suggId,
            original: finding.title,
            alternative: finding.suggestion,
            reason: finding.detail.slice(0, 100),
            agent: finding.agent,
            elapsed: now,
          };
          setScriptSuggestions((prev) => [suggestion, ...prev]);
          // Auto-dismiss after 12 seconds
          setTimeout(() => {
            setScriptSuggestions((prev) => prev.filter((s) => s.id !== suggId));
          }, 12000);
        }

        if (sessionMode === 'live_in_room' && finding.cue_hint) {
          const cueId = mockId();
          const cue: EarpieceCue = {
            id: cueId,
            text: finding.cue_hint,
            audio_b64: null,
            priority: finding.severity,
            category: finding.agent,
            elapsed: now,
          };
          if (_cuePassesSensitivity(cue.priority, sensitivityRef.current)) {
            setCues((prev) => [cue, ...prev]);
            playEarpieceAudio(cue.audio_b64);
          }
        }
      }

      // Remote mode: teleprompter update every 20 seconds
      if (
        sessionMode === 'live_remote' &&
        now - lastTeleprompterSec >= 20 &&
        teleprompterIdx < MOCK_TELEPROMPTER_SEQUENCES.length
      ) {
        setTeleprompterPoints(MOCK_TELEPROMPTER_SEQUENCES[teleprompterIdx]);
        teleprompterIdx++;
        lastTeleprompterSec = now;
      }

      // Remote mode: objection prep card every 25 seconds
      if (
        sessionMode === 'live_remote' &&
        now - lastObjectionSec >= 25 &&
        objectionIdx < MOCK_OBJECTION_CARDS.length
      ) {
        const card = MOCK_OBJECTION_CARDS[objectionIdx];
        objectionIdx++;
        lastObjectionSec = now;
        setObjections((prev) => [...prev, { ...card, id: mockId() }]);
      }
    }, 3000);
  }, [startTimer, playEarpieceAudio]);

  const endMockSession = useCallback(async () => {
    if (mockIntervalRef.current) clearInterval(mockIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);

    setState('finalizing');
    await new Promise((r) => setTimeout(r, 2000));

    const mode = sessionModeRef.current;
    const {
      MOCK_REPORT,
      MOCK_LIVE_INROOM_REPORT,
      MOCK_LIVE_REMOTE_REPORT,
    } = await import('@/lib/mock-data');

    // Each live mode returns a mode-specific report so the review UI reflects
    // what actually happened during that session type.
    if (mode === 'live_in_room') {
      setReport(MOCK_LIVE_INROOM_REPORT as unknown as ReadinessReport);
    } else if (mode === 'live_remote') {
      setReport(MOCK_LIVE_REMOTE_REPORT as unknown as ReadinessReport);
    } else {
      setReport(MOCK_REPORT as unknown as ReadinessReport);
    }
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

  const startRealSession = useCallback(async (
    personas: PersonaConfig[],
    docFiles: File[] = [],
    sessionMode: SessionMode = 'live',
    presentationMaterials: File[] = [],
    agents: AgentConfig[] = [],
  ) => {
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

    let policyText = '';
    if (docFiles.length > 0) {
      try {
        policyText = await docFiles[0].text();
      } catch { /* ignore non-text files */ }
    }

    // Read text-extractable presentation materials (TXT/MD/DOCX); PDFs and
    // binary formats will fail .text() gracefully and be skipped.
    const presentationTextParts: string[] = [];
    for (const f of presentationMaterials) {
      try {
        const text = await f.text();
        if (text.trim()) presentationTextParts.push(`--- ${f.name} ---\n${text}`);
      } catch { /* binary format — skip */ }
    }
    const presentationText = presentationTextParts.join('\n\n');

    // Map frontend mode to backend WS init mode value
    const wsMode = sessionMode === 'live_remote' ? 'live_remote'
      : sessionMode === 'live_in_room' ? 'live_in_room'
      : 'live';

    const ws = new WebSocket(getLiveSessionWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'init',
        mode: wsMode,
        personas: personas.filter((p) => p.enabled).map((p) => p.label),
        enabled_agents: agents.filter((a) => a.enabled).map((a) => a.id),
        policy_text: policyText,
        presentation_text: presentationText,
        title: sessionMode === 'live_remote' ? 'Live Remote Session' : 'Live Rehearsal',
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
          setTimeout(() => setNudges((prev) => prev.filter((n) => n.id !== nudgeId)), 5000);
          break;
        }
        // live_in_room
        case 'earpiece_cue': {
          const cue: EarpieceCue = {
            id: mockId(),
            text: msg.text ?? '',
            audio_b64: msg.audio_b64 ?? null,
            priority: msg.priority ?? 'warning',
            category: msg.category ?? '',
            elapsed: msg.elapsed ?? 0,
          };
          // Severity gate: filter by sensitivity setting
          const pass = _cuePassesSensitivity(cue.priority, sensitivityRef.current);
          if (!pass) break;
          setCues((prev) => [cue, ...prev]);
          playEarpieceAudio(cue.audio_b64);
          break;
        }
        // live_remote
        case 'teleprompter': {
          if (msg.points) {
            setTeleprompterPoints(msg.points);
          }
          break;
        }
        case 'objection_prep': {
          if (msg.questions) {
            setObjections(msg.questions);
          }
          break;
        }
        case 'script_suggestion': {
          const suggestion: ScriptSuggestion = {
            id: mockId(),
            original: msg.original ?? '',
            alternative: msg.alternative ?? '',
            reason: msg.reason ?? '',
            agent: msg.agent ?? 'coach',
            elapsed: msg.elapsed ?? 0,
          };
          setScriptSuggestions((prev) => [suggestion, ...prev]);
          setTimeout(() => {
            setScriptSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id));
          }, 12000);
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
              setReport(r as unknown as ReadinessReport);
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

    function startAudioCapture(s: MediaStream) {
      const audioStream = new MediaStream(s.getAudioTracks());
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      // Each recorder.stop() fires ondataavailable with a *complete*, self-contained
      // WebM file (EBML header + Tracks + Clusters). Starting a fresh MediaRecorder
      // every 2 s avoids the continuation-segment problem where subsequent chunks
      // have no EBML header and can't be decoded independently by ffmpeg/whisper.
      const startNewRecorder = () => {
        const rec = new MediaRecorder(audioStream, { mimeType });
        mediaRecorderRef.current = rec;
        rec.ondataavailable = (e) => {
          if (e.data.size === 0) return;
          e.data.arrayBuffer().then((buf) => sendBinary(MSG_AUDIO, buf));
        };
        rec.start();
      };

      startNewRecorder();

      audioIntervalRef.current = setInterval(() => {
        const current = mediaRecorderRef.current;
        if (!current || current.state !== 'recording') return;
        // stop() triggers ondataavailable → send the complete chunk, then
        // onstop fires → start a fresh recorder for the next window.
        current.addEventListener('stop', startNewRecorder, { once: true });
        current.stop();
      }, 2000);
    }
  }, [startTimer, startFrameCapture, sendBinary, cleanup, sessionId, state, playEarpieceAudio]);

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  const startSession = useCallback(async (
    personas: PersonaConfig[],
    docFiles: File[] = [],
    sessionMode: SessionMode = 'live',
    presentationMaterials: File[] = [],
    agents: AgentConfig[] = [],
  ) => {
    setError(null);
    setFindings([]);
    setNudges([]);
    setTranscript([]);
    setReport(null);
    setElapsedSeconds(0);
    setCues([]);
    setMuted(false);
    setSensitivity('medium');
    setTeleprompterPoints([]);
    setObjections([]);
    setScriptSuggestions([]);
    setMode(sessionMode);
    sessionModeRef.current = sessionMode;

    if (USE_MOCK) {
      await startMockSession(personas, sessionMode);
    } else {
      await startRealSession(personas, docFiles, sessionMode, presentationMaterials, agents);
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

    if (audioIntervalRef.current) clearInterval(audioIntervalRef.current);
    audioIntervalRef.current = null;

    if (mediaRecorderRef.current?.state !== 'inactive') {
      try { mediaRecorderRef.current?.stop(); } catch { /* ignore */ }
    }
    if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
  }, [endMockSession]);

  const toggleMute = useCallback(() => setMuted((v) => !v), []);

  const dismissNudge = useCallback((id: string) => {
    setNudges((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const dismissScriptSuggestion = useCallback((id: string) => {
    setScriptSuggestions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setState('idle');
    setMode('live');
    setSessionId(null);
    setFindings([]);
    setNudges([]);
    setTranscript([]);
    setReport(null);
    setError(null);
    setElapsedSeconds(0);
    setMediaStream(null);
    setCues([]);
    setMuted(false);
    setSensitivity('medium');
    setTeleprompterPoints([]);
    setObjections([]);
    setScriptSuggestions([]);
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
    mode,
    sessionId,
    findings,
    nudges,
    transcript,
    report,
    error,
    elapsedSeconds,
    mediaStream,
    cues,
    muted,
    sensitivity,
    toggleMute,
    setSensitivity,
    teleprompterPoints,
    objections,
    scriptSuggestions,
    startSession,
    endSession,
    dismissNudge,
    dismissScriptSuggestion,
    reset,
  };
}
