import { useState, useRef, useCallback } from 'react';
import { Upload, FileVideo, FileText, X, TrendingUp, User, Shield, Zap, Radio } from 'lucide-react';
import { cn, formatFileSize } from '@/lib/utils';
import type { PersonaConfig } from '@/types/api';
import type { SessionMode } from '@/types';

const DEFAULT_PERSONAS: PersonaConfig[] = [
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
  {
    id: 'compliance_officer',
    label: 'Compliance Officer',
    description: 'Flags regulatory risk and policy conflicts',
    icon: 'Shield',
    enabled: false,
  },
];

const PERSONA_ICONS = {
  TrendingUp: TrendingUp,
  User: User,
  Shield: Shield,
};

interface Props {
  onStart: (video: File, docs: File[], personas: PersonaConfig[], mode?: SessionMode) => void;
}

export function SetupPage({ onStart }: Props) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [docFiles, setDocFiles] = useState<File[]>([]);
  const [personas, setPersonas] = useState<PersonaConfig[]>(DEFAULT_PERSONAS);
  const [videoDrag, setVideoDrag] = useState(false);
  const [docDrag, setDocDrag] = useState(false);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  const handleVideoDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setVideoDrag(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) setVideoFile(file);
  }, []);

  const handleDocDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDocDrag(false);
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => f.type === 'application/pdf' || f.name.endsWith('.txt') || f.name.endsWith('.md'),
    );
    setDocFiles((prev) => [...prev, ...files]);
  }, []);

  const togglePersona = (id: string) => {
    setPersonas((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p)),
    );
  };

  const canStart = !!videoFile && personas.some((p) => p.enabled);
  const canStartLive = personas.some((p) => p.enabled);

  return (
    <div className="min-h-screen bg-bg-base flex flex-col">
      {/* Newspaper Masthead */}
      <header className="border-b-4 border-bg-border px-8 pt-6 pb-4">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-end justify-between gap-4">
            <h1 className="font-display text-8xl leading-none text-text-primary tracking-wider">
              PITCHPILOT
            </h1>
            <div className="text-right pb-2 shrink-0">
              <p className="font-mono text-xs text-text-muted uppercase tracking-widest leading-relaxed">
                Demo Readiness<br />Analysis System
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t-2 border-bg-border flex items-center justify-between">
            <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
              Three On-Device AI Agents
            </span>
            <span className="font-mono text-xs text-text-muted">
              Gemma&nbsp;3n · FunctionGemma · Gemma&nbsp;3&nbsp;4B
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col items-center px-6 py-10">
        <div className="w-full max-w-2xl mb-8 animate-fade-up">
          <div className="flex items-baseline gap-4 mb-2">
            <span className="font-display text-5xl text-text-primary">NEW ANALYSIS SESSION</span>
          </div>
          <p className="font-mono text-sm text-text-secondary leading-relaxed">
            Upload a rehearsal recording or go live — three on-device AI agents will evaluate
            clarity, compliance, and audience defensibility.
          </p>
        </div>

        <div className="w-full max-w-2xl space-y-8">

          {/* ── REHEARSAL VIDEO ── */}
          <section
            className="animate-fade-up"
            style={{ animationDelay: '60ms' }}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="font-display text-2xl text-text-primary tracking-wider">REHEARSAL VIDEO</span>
              <span className="font-mono text-xs text-accent-red font-bold border border-accent-red px-1.5 py-0.5">
                REQUIRED
              </span>
            </div>
            <div className="border-b-2 border-bg-border mb-3" />

            {videoFile ? (
              <div className="flex items-center gap-3 px-4 py-3 bg-bg-surface border-2 border-bg-border shadow-brutal">
                <FileVideo size={16} className="text-text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-sm text-text-primary truncate font-bold">{videoFile.name}</p>
                  <p className="font-mono text-xs text-text-muted">{formatFileSize(videoFile.size)}</p>
                </div>
                <button
                  onClick={() => setVideoFile(null)}
                  className="font-mono text-xs text-text-muted hover:text-accent-red border border-current px-2 py-1 transition-colors"
                >
                  REMOVE
                </button>
              </div>
            ) : (
              <div
                onDragOver={(e) => { e.preventDefault(); setVideoDrag(true); }}
                onDragLeave={() => setVideoDrag(false)}
                onDrop={handleVideoDrop}
                onClick={() => videoInputRef.current?.click()}
                className={cn(
                  'border-4 border-dashed px-6 py-14 flex flex-col items-center gap-3 cursor-pointer transition-colors duration-100',
                  videoDrag
                    ? 'border-bg-border bg-bg-elevated'
                    : 'border-bg-border bg-bg-surface hover:bg-bg-elevated',
                )}
              >
                <Upload size={28} className="text-text-secondary" strokeWidth={1.5} />
                <div className="text-center">
                  <p className="font-display text-3xl text-text-primary">
                    {videoDrag ? 'DROP TO UPLOAD' : 'DROP VIDEO OR CLICK TO BROWSE'}
                  </p>
                  <p className="font-mono text-xs text-text-muted mt-1.5 uppercase tracking-widest">
                    MP4 · MOV · WebM — up to 500 MB
                  </p>
                </div>
                <input
                  ref={videoInputRef}
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setVideoFile(f);
                  }}
                />
              </div>
            )}
          </section>

          {/* ── POLICY DOCS ── */}
          <section
            className="animate-fade-up"
            style={{ animationDelay: '120ms' }}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="font-display text-2xl text-text-primary tracking-wider">POLICY DOCS</span>
              <span className="font-mono text-xs text-text-muted border border-text-muted px-1.5 py-0.5">
                OPTIONAL
              </span>
            </div>
            <div className="border-b-2 border-bg-border mb-3" />

            {docFiles.length > 0 && (
              <div className="space-y-1.5 mb-3">
                {docFiles.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2 bg-bg-surface border-2 border-bg-border">
                    <FileText size={12} className="text-accent-blue flex-shrink-0" />
                    <span className="font-mono text-xs text-text-secondary truncate flex-1">{f.name}</span>
                    <span className="font-mono text-xs text-text-muted">{formatFileSize(f.size)}</span>
                    <button
                      onClick={() => setDocFiles((prev) => prev.filter((_, idx) => idx !== i))}
                      className="text-text-muted hover:text-accent-red transition-colors ml-1"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div
              onDragOver={(e) => { e.preventDefault(); setDocDrag(true); }}
              onDragLeave={() => setDocDrag(false)}
              onDrop={handleDocDrop}
              onClick={() => docInputRef.current?.click()}
              className={cn(
                'border-2 border-dashed px-4 py-5 flex items-center gap-3 cursor-pointer transition-colors duration-100',
                docDrag
                  ? 'border-bg-border bg-bg-elevated'
                  : 'border-bg-border bg-bg-surface hover:bg-bg-elevated',
              )}
            >
              <Upload size={14} className="text-text-muted flex-shrink-0" />
              <p className="font-mono text-xs text-text-muted leading-relaxed">
                {docDrag
                  ? 'DROP FILES HERE'
                  : 'Drop PDFs, TXT, or MD — the Compliance agent cross-checks claims against these documents'}
              </p>
              <input
                ref={docInputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.md"
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  setDocFiles((prev) => [...prev, ...files]);
                }}
              />
            </div>
          </section>

          {/* ── AUDIENCE PERSONAS ── */}
          <section
            className="animate-fade-up"
            style={{ animationDelay: '180ms' }}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="font-display text-2xl text-text-primary tracking-wider">AUDIENCE PERSONAS</span>
            </div>
            <div className="border-b-2 border-bg-border mb-3" />

            <div className="grid grid-cols-3 gap-3">
              {personas.map((persona) => {
                const Icon = PERSONA_ICONS[persona.icon as keyof typeof PERSONA_ICONS] ?? User;
                return (
                  <button
                    key={persona.id}
                    onClick={() => togglePersona(persona.id)}
                    className={cn(
                      'text-left p-3 border-2 border-bg-border transition-all duration-100',
                      persona.enabled
                        ? 'bg-bg-border text-bg-base shadow-brutal translate-x-[-2px] translate-y-[-2px]'
                        : 'bg-bg-surface hover:bg-bg-elevated',
                    )}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon
                        size={11}
                        className={persona.enabled ? 'text-bg-base' : 'text-text-muted'}
                      />
                      <span className={cn(
                        'font-mono text-xs font-bold uppercase tracking-wider',
                        persona.enabled ? 'text-bg-base' : 'text-text-secondary',
                      )}>
                        {persona.label}
                      </span>
                    </div>
                    <p className={cn(
                      'font-mono text-xs leading-snug',
                      persona.enabled ? 'text-bg-elevated' : 'text-text-muted',
                    )}>
                      {persona.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>

          {/* ── LAUNCH ── */}
          <div
            className="animate-fade-up pt-2 space-y-3"
            style={{ animationDelay: '240ms' }}
          >
            {/* Upload mode CTA */}
            <button
              onClick={() => videoFile && onStart(videoFile, docFiles, personas, 'upload')}
              disabled={!canStart}
              className={cn(
                'w-full py-4 font-display text-3xl tracking-wider flex items-center justify-center gap-3 border-2 border-bg-border transition-all duration-100',
                canStart
                  ? 'bg-bg-border text-bg-base shadow-brutal brutal-hover'
                  : 'bg-bg-surface text-text-muted cursor-not-allowed',
              )}
            >
              START ANALYSIS →
            </button>

            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-bg-border opacity-40" />
              <span className="font-mono text-xs text-text-muted">or skip the upload</span>
              <div className="flex-1 h-px bg-bg-border opacity-40" />
            </div>

            {/* Live session CTA */}
            <button
              onClick={() => {
                const placeholder = new File([''], 'live_session.mp4', { type: 'video/mp4' });
                onStart(placeholder, docFiles, personas, 'live');
              }}
              disabled={!canStartLive}
              className={cn(
                'w-full py-4 font-display text-3xl tracking-wider flex items-center justify-center gap-3 border-2 transition-all duration-100',
                canStartLive
                  ? 'border-accent-red bg-bg-surface text-accent-red hover:bg-accent-red hover:text-bg-base shadow-brutal-red brutal-hover'
                  : 'border-bg-border bg-bg-surface text-text-muted cursor-not-allowed',
              )}
            >
              <Radio size={20} strokeWidth={2} />
              GO LIVE →
            </button>
            <p className="text-center font-mono text-xs text-text-muted">
              Real-time analysis — agents listen and flag issues as you present
            </p>

            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-bg-border opacity-40" />
              <span className="font-mono text-xs text-text-muted">or</span>
              <div className="flex-1 h-px bg-bg-border opacity-40" />
            </div>

            <button
              onClick={() => {
                const demoFile = new File([''], 'demo_pitch.mp4', { type: 'video/mp4' });
                onStart(demoFile, [], personas, 'upload');
              }}
              className="w-full py-3 font-mono text-xs uppercase tracking-widest flex items-center justify-center gap-2 border-2 border-bg-border bg-bg-surface text-text-secondary hover:bg-bg-elevated transition-colors duration-100"
            >
              <Zap size={12} />
              LOAD DEMO SESSION
            </button>

            <p className="text-center font-mono text-xs text-text-muted">
              Demo runs a pre-built analysis — no upload needed
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
