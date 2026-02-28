import { useState, useRef, useCallback } from 'react';
import { Upload, FileVideo, FileText, X, TrendingUp, User, Shield, Zap, Radio, Headphones, Monitor, Layers } from 'lucide-react';
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

// ---------------------------------------------------------------------------
// Mode selector config
// ---------------------------------------------------------------------------

type PickMode = 'review' | 'live_in_room' | 'live_remote';

interface Props {
  onStart: (video: File, docs: File[], personas: PersonaConfig[], mode?: SessionMode, presentationMaterials?: File[]) => void;
  onStartDemo: (personas: PersonaConfig[]) => void;
  onHome?: () => void;
  initialMode?: PickMode;
}

const MODES: {
  id: PickMode;
  label: string;
  sublabel: string;
  icon: typeof Radio;
  description: string;
}[] = [
  {
    id: 'review',
    label: 'Review',
    sublabel: 'Post-Hoc Analysis',
    icon: Upload,
    description: 'Upload a recorded rehearsal — agents analyse the full video and return a readiness report.',
  },
  {
    id: 'live_in_room',
    label: 'Live In-Room',
    sublabel: 'Earpiece Coaching',
    icon: Headphones,
    description: 'Face-to-face pitch. Agents listen live and deliver discreet 4-6 word cues via earpiece.',
  },
  {
    id: 'live_remote',
    label: 'Live Remote',
    sublabel: 'Presenter Overlay',
    icon: Monitor,
    description: 'Virtual demo over Zoom / Meet. Agents surface teleprompter points and objection prep in a private overlay.',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SetupPage({ onStart, onStartDemo, onHome, initialMode }: Props) {
  const [selectedMode, setSelectedMode] = useState<PickMode>(initialMode ?? 'review');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [docFiles, setDocFiles] = useState<File[]>([]);
  const [presentationFiles, setPresentationFiles] = useState<File[]>([]);
  const [personas, setPersonas] = useState<PersonaConfig[]>(DEFAULT_PERSONAS);
  const [videoDrag, setVideoDrag] = useState(false);
  const [docDrag, setDocDrag] = useState(false);
  const [presentationDrag, setPresentationDrag] = useState(false);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const presentationInputRef = useRef<HTMLInputElement>(null);

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

  const isPresentationFile = (f: File) =>
    f.type === 'application/pdf' ||
    f.name.endsWith('.pptx') ||
    f.name.endsWith('.ppt') ||
    f.name.endsWith('.key') ||
    f.name.endsWith('.txt') ||
    f.name.endsWith('.md') ||
    f.name.endsWith('.docx') ||
    f.name.endsWith('.doc');

  const handlePresentationDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setPresentationDrag(false);
    const files = Array.from(e.dataTransfer.files).filter(isPresentationFile);
    setPresentationFiles((prev) => [...prev, ...files]);
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
            <h1
              className={cn(
                "font-display text-8xl leading-none text-text-primary tracking-wider",
                onHome && "cursor-pointer hover:opacity-70 transition-opacity"
              )}
              onClick={onHome}
            >
              P<span className="italic">ITCH</span><span className="ml-4">PILOT</span>
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
          <p className="font-mono text-base text-text-secondary leading-relaxed">
            Upload a rehearsal recording or go live — three on-device AI agents will evaluate
            clarity, compliance, and audience defensibility.
          </p>
        </div>

        <div className="w-full max-w-2xl space-y-8">

          {/* ── MODE SELECTOR ── */}
          <section className="animate-fade-up" style={{ animationDelay: '40ms' }}>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-display text-2xl text-text-primary tracking-wider">PRESENTATION MODE</span>
            </div>
            <div className="border-b-2 border-bg-border mb-3" />
            <div className="grid grid-cols-3 gap-3">
              {MODES.map((m) => {
                const Icon = m.icon;
                const active = selectedMode === m.id;
                return (
                  <div key={m.id} className="relative group">
                    <button
                      onClick={() => setSelectedMode(m.id)}
                      className={cn(
                        'w-full text-left p-3 border-2 border-bg-border transition-all duration-100',
                        active
                          ? 'bg-bg-border text-bg-base shadow-brutal translate-x-[-2px] translate-y-[-2px]'
                          : 'bg-bg-surface hover:bg-bg-elevated',
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <Icon size={14} className={active ? 'text-bg-base' : 'text-text-muted'} />
                        <span className={cn(
                          'font-display text-2xl tracking-wider uppercase',
                          active ? 'text-bg-base' : 'text-text-secondary',
                        )}>
                          {m.label}
                        </span>
                      </div>
                      <p className={cn(
                        'font-mono text-sm leading-snug',
                        active ? 'text-bg-elevated' : 'text-text-muted',
                      )}>
                        {m.sublabel}
                      </p>
                    </button>
                    {/* Hover tooltip */}
                    <div className="pointer-events-none absolute bottom-full left-0 mb-2 w-48 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                      <div className="border-2 border-bg-border bg-bg-base px-2.5 py-2 shadow-brutal">
                        <p className="font-mono text-sm leading-snug text-text-secondary">
                          {m.description}
                        </p>
                      </div>
                      <div className="w-2 h-2 border-r-2 border-b-2 border-bg-border bg-bg-base rotate-45 ml-3 -mt-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* ── REHEARSAL VIDEO (review mode only) ── */}
          {selectedMode === 'review' && <section
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
          </section>}

          {/* ── PRESENTATION MATERIALS ── */}
          <section
            className="animate-fade-up"
            style={{ animationDelay: '90ms' }}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="font-display text-2xl text-text-primary tracking-wider">PRESENTATION MATERIALS</span>
              <span className="font-mono text-xs text-text-muted border border-text-muted px-1.5 py-0.5">
                OPTIONAL
              </span>
            </div>
            <div className="border-b-2 border-bg-border mb-3" />

            {presentationFiles.length > 0 && (
              <div className="space-y-1.5 mb-3">
                {presentationFiles.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2 bg-bg-surface border-2 border-bg-border">
                    <Layers size={12} className="text-accent-amber flex-shrink-0" />
                    <span className="font-mono text-xs text-text-secondary truncate flex-1">{f.name}</span>
                    <span className="font-mono text-xs text-text-muted">{formatFileSize(f.size)}</span>
                    <button
                      onClick={() => setPresentationFiles((prev) => prev.filter((_, idx) => idx !== i))}
                      className="text-text-muted hover:text-accent-red transition-colors ml-1"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div
              onDragOver={(e) => { e.preventDefault(); setPresentationDrag(true); }}
              onDragLeave={() => setPresentationDrag(false)}
              onDrop={handlePresentationDrop}
              onClick={() => presentationInputRef.current?.click()}
              className={cn(
                'border-2 border-dashed px-4 py-5 flex items-center gap-3 cursor-pointer transition-colors duration-100',
                presentationDrag
                  ? 'border-bg-border bg-bg-elevated'
                  : 'border-bg-border bg-bg-surface hover:bg-bg-elevated',
              )}
            >
              <Layers size={14} className="text-accent-amber flex-shrink-0" />
              <p className="font-mono text-sm text-text-muted leading-relaxed">
                {presentationDrag
                  ? 'DROP FILES HERE'
                  : 'Drop slides, script, or speaker notes — agents use these to pre-load context and sharpen cues'}
              </p>
              <input
                ref={presentationInputRef}
                type="file"
                multiple
                accept=".pdf,.pptx,.ppt,.key,.docx,.doc,.txt,.md"
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []).filter(isPresentationFile);
                  setPresentationFiles((prev) => [...prev, ...files]);
                }}
              />
            </div>
            <p className="font-mono text-xs text-text-muted mt-1.5 leading-relaxed">
              PDF · PPTX · KEY · DOCX · TXT · MD
            </p>
            {selectedMode !== 'review' && (
              <p className="font-mono text-xs text-accent-amber mt-1 leading-relaxed">
                Agents can pre-generate objection prep before you go live
              </p>
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
              <p className="font-mono text-sm text-text-muted leading-relaxed">
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
                  <div key={persona.id} className="relative group">
                    <button
                      onClick={() => togglePersona(persona.id)}
                      className={cn(
                        'w-full text-left pl-5 pr-3 py-3 border-2 border-bg-border transition-all duration-100',
                        persona.enabled
                          ? 'bg-bg-border text-bg-base shadow-brutal translate-x-[-2px] translate-y-[-2px]'
                          : 'bg-bg-surface hover:bg-bg-elevated',
                      )}
                    >
                      <div className="flex items-center gap-4">
                        <Icon
                          size={28}
                          className={persona.enabled ? 'text-bg-base' : 'text-text-muted'}
                        />
                        <span className={cn(
                          'font-display text-2xl tracking-wider uppercase text-justify',
                          persona.enabled ? 'text-bg-base' : 'text-text-secondary',
                        )}>
                          {persona.label}
                        </span>
                      </div>
                    </button>
                    {/* Hover tooltip */}
                    <div className="pointer-events-none absolute bottom-full left-0 mb-2 w-48 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                      <div className="border-2 border-bg-border bg-bg-base px-2.5 py-2 shadow-brutal">
                        <p className="font-mono text-sm leading-snug text-text-secondary">
                          {persona.description}
                        </p>
                      </div>
                      <div className="w-2 h-2 border-r-2 border-b-2 border-bg-border bg-bg-base rotate-45 ml-3 -mt-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* ── LAUNCH ── */}
          <div
            className="animate-fade-up pt-2 space-y-3"
            style={{ animationDelay: '240ms' }}
          >
            {/* Primary CTA — adapts to selected mode */}
            {selectedMode === 'review' ? (
              <>
                <button
                  onClick={() => videoFile && onStart(videoFile, docFiles, personas, 'review', presentationFiles)}
                  disabled={!canStart}
                  className={cn(
                    'w-full py-4 font-display text-3xl tracking-wider flex items-center justify-center gap-3 border-2 border-bg-border transition-all duration-100',
                    canStart
                      ? 'bg-bg-border text-bg-base shadow-brutal brutal-hover'
                      : 'bg-bg-surface text-text-muted cursor-not-allowed',
                  )}
                >
                  <Upload size={20} strokeWidth={2} />
                  START ANALYSIS →
                </button>
                <p className="text-center font-mono text-xs text-text-muted">
                  Upload a recording — full pipeline runs, returns readiness report
                </p>
              </>
            ) : selectedMode === 'live_in_room' ? (
              <>
                <button
                  onClick={() => {
                    const placeholder = new File([''], 'live_in_room.mp4', { type: 'video/mp4' });
                    onStart(placeholder, docFiles, personas, 'live_in_room', presentationFiles);
                  }}
                  disabled={!canStartLive}
                  className={cn(
                    'w-full py-4 font-display text-3xl tracking-wider flex items-center justify-center gap-3 border-2 transition-all duration-100',
                    canStartLive
                      ? 'border-accent-red bg-bg-surface text-accent-red hover:bg-accent-red hover:text-bg-base shadow-brutal-red brutal-hover'
                      : 'border-bg-border bg-bg-surface text-text-muted cursor-not-allowed',
                  )}
                >
                  <Headphones size={20} strokeWidth={2} />
                  START EARPIECE SESSION →
                </button>
                <p className="text-center font-mono text-xs text-text-muted">
                  Agents listen live and deliver discreet 4-6 word cues via earpiece
                </p>
              </>
            ) : (
              <>
                <button
                  onClick={() => {
                    const placeholder = new File([''], 'live_remote.mp4', { type: 'video/mp4' });
                    onStart(placeholder, docFiles, personas, 'live_remote', presentationFiles);
                  }}
                  disabled={!canStartLive}
                  className={cn(
                    'w-full py-4 font-display text-3xl tracking-wider flex items-center justify-center gap-3 border-2 transition-all duration-100',
                    canStartLive
                      ? 'border-accent-blue bg-bg-surface text-accent-blue hover:bg-accent-blue hover:text-bg-base shadow-brutal brutal-hover'
                      : 'border-bg-border bg-bg-surface text-text-muted cursor-not-allowed',
                  )}
                >
                  <Monitor size={20} strokeWidth={2} />
                  START REMOTE OVERLAY →
                </button>
                <p className="text-center font-mono text-xs text-text-muted">
                  Teleprompter + objection prep overlay — private to presenter
                </p>
              </>
            )}

            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-bg-border opacity-40" />
              <span className="font-mono text-xs text-text-muted">or</span>
              <div className="flex-1 h-px bg-bg-border opacity-40" />
            </div>

            <button
              onClick={() => onStartDemo(personas)}
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
