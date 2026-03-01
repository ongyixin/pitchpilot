import { useEffect, useState } from 'react';
import { Zap, Radio, Shield, TrendingUp, User, Lock, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  onLaunch: () => void;
  onDemo: () => void;
  onGoLive?: () => void;
}

const TICKER_ITEMS = [
  'PRESENTATION COACH',
  'COMPLIANCE REVIEW',
  'PERSONA SIMULATION',
  'ON-DEVICE INFERENCE',
  'GEMMA 3N · FUNCTIONGEMMA · GEMMA 3 4B',
  'TIMELINE ANNOTATIONS',
  'READINESS SCORING',
  'NO DATA LEAVES YOUR MACHINE',
  'REAL-TIME LIVE MODE',
  'POLICY DOCUMENT ANALYSIS',
  'APPLE SILICON OPTIMIZED',
  'ZERO CLOUD CALLS',
];

const AGENTS = [
  {
    num: '01',
    label: 'PRESENTATION COACH',
    icon: TrendingUp,
    textClass: 'text-accent-amber',
    borderClass: 'border-accent-amber',
    badgeBg: 'bg-accent-amber',
    badge: 'COACH',
    desc: 'Evaluates narrative flow, structural clarity, and delivery confidence. Identifies jargon overload, abrupt transitions, and unsupported claims with timestamped precision.',
    finding: '"Abrupt transition at 1:42 — no narrative bridge between market-size claim and product demo."',
  },
  {
    num: '02',
    label: 'COMPLIANCE REVIEWER',
    icon: Shield,
    textClass: 'text-accent-red',
    borderClass: 'border-accent-red',
    badgeBg: 'bg-accent-red',
    badge: 'COMPLIANCE',
    desc: 'Cross-checks every claim against your uploaded policy documents. Surfaces regulatory exposure and prohibited phrasing before it surfaces in a boardroom.',
    finding: '"\'Fully automated\' at 2:18 contradicts Enterprise Data Policy §3.2 — human oversight is required."',
  },
  {
    num: '03',
    label: 'PERSONA SIMULATOR',
    icon: User,
    textClass: 'text-accent-purple',
    borderClass: 'border-accent-purple',
    badgeBg: 'bg-accent-purple',
    badge: 'PERSONA',
    desc: 'Generates adversarial questions from real stakeholder archetypes — the skeptical investor, the technical reviewer, the compliance officer.',
    finding: '"How is this meaningfully different from a GPT wrapper? What is the moat when OpenAI ships this natively?"',
  },
];

const PIPELINE_STEPS = [
  {
    num: '01',
    step: 'FRAME EXTRACTION',
    tech: 'OpenCV · Gemma 3n',
    desc: 'Keyframes sampled at 1 fps, slide OCR run on each visual',
  },
  {
    num: '02',
    step: 'TRANSCRIPTION',
    tech: 'Gemma 3n · Audio',
    desc: 'Speech-to-text with timestamps, aligned to slide context',
  },
  {
    num: '03',
    step: 'CLAIM EXTRACTION',
    tech: 'Gemma 3n · NLP',
    desc: 'Product, compliance, and comparison claims identified from merged transcript',
  },
  {
    num: '04',
    step: 'AGENT ROUTING',
    tech: 'FunctionGemma 270M',
    desc: 'Fine-tuned LoRA dispatches each claim to one or more specialist agents',
  },
  {
    num: '05',
    step: 'READINESS SCORE',
    tech: 'Gemma 3 4B',
    desc: 'Findings aggregated into a scored readiness report with priority fixes',
  },
];

export function LandingPage({ onLaunch, onDemo, onGoLive }: Props) {
  const [tick, setTick] = useState(0);
  const [flippedCards, setFlippedCards] = useState<Set<number>>(new Set());
  const [openFindings, setOpenFindings] = useState<Set<number>>(new Set());

  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 700);
    return () => clearInterval(t);
  }, []);

  const toggleCard = (i: number) => {
    setFlippedCards((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const toggleFinding = (i: number) => {
    setOpenFindings((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-bg-base flex flex-col">

      {/* ── Edition strip ── */}
      <div className="border-b border-bg-border px-6 py-1.5 flex items-center justify-between bg-bg-surface">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-text-muted uppercase tracking-[0.18em]">Vol. I · No. 1</span>
          <span className="font-mono text-xs text-text-muted opacity-30">|</span>
          <span className="font-mono text-xs text-text-muted uppercase tracking-[0.18em]">Demo Readiness Analysis System</span>
          <span className="font-mono text-xs text-text-muted opacity-30">|</span>
          <span className="font-mono text-xs text-text-muted uppercase tracking-[0.18em] hidden sm:inline">Three On-Device AI Agents</span>
        </div>
        <span className="font-mono text-xs text-text-muted hidden sm:inline">Saturday, Feb. 28, 2026</span>
      </div>

      {/* ── Masthead / Hero ── */}
      <header className="border-b-4 border-bg-border">
        <div className="px-6 lg:px-12">

          {/* PITCHPILOT heading */}
          <div className="pt-6 pb-4 border-b-2 border-bg-border flex items-end justify-between gap-6">
            <div className="flex items-end gap-2">
              <h1
                className="font-display text-text-primary tracking-wider leading-[0.82] select-none"
                style={{ fontSize: 'clamp(5rem, 16vw, 13rem)' }}
              >
                P<span className="italic">ITCH</span><br />PILOT
              </h1>
              {/* Blinking cursor */}
              <span
                className={cn(
                  'font-display text-accent-red leading-none mb-2 transition-opacity duration-75',
                  tick % 2 === 0 ? 'opacity-100' : 'opacity-0',
                )}
                style={{ fontSize: 'clamp(2.5rem, 7vw, 6rem)' }}
              >
                ▐
              </span>
            </div>
            <button
              onClick={onLaunch}
              className="shrink-0 mb-2 px-10 py-6 font-display text-4xl lg:text-5xl tracking-widest bg-bg-border text-bg-base border-2 border-bg-border shadow-brutal-lg brutal-hover whitespace-nowrap"
            >
              LAUNCH APP →
            </button>
          </div>

          {/* Deck */}
          <div className="py-5">
            <p 
              className="font-mono text-text-primary font-bold leading-tight mb-2"
              style={{ fontSize: 'clamp(1rem, 3.5vw, 2.5rem)' }}
            >
              Scratch that verbal ITCH.
            </p>
            <p className="font-mono text-sm text-text-secondary leading-relaxed whitespace-nowrap">
              Three on-device agents evaluate clarity, compliance, and defensibility before you walk into the room.
            </p>
          </div>
        </div>
      </header>

      {/* ── Scrolling ticker ── */}
      <div className="border-b-2 border-bg-border overflow-hidden bg-bg-surface flex items-stretch h-11">
        <div className="shrink-0 flex items-center px-4 border-r-2 border-bg-border bg-accent-red">
          <span className="font-display text-sm tracking-widest text-bg-base whitespace-nowrap">
            FEATURES
          </span>
        </div>
        <div className="flex-1 overflow-hidden flex items-center">
          <div className="flex gap-0 animate-ticker whitespace-nowrap">
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
              <span
                key={i}
                className="font-mono text-base text-text-secondary inline-flex items-center gap-3 px-6"
              >
                <span className="text-accent-red text-sm">◆</span>
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── Three agents ── */}
      <section className="border-b-4 border-bg-border">
        <div className="px-6 lg:px-12">
          <div className="py-2.5 border-b-2 border-bg-border flex items-center justify-between">
            <span className="font-display text-base tracking-widest text-text-muted">
              THE THREE AGENTS
            </span>
            <span className="font-mono text-xs text-text-muted uppercase tracking-wider hidden sm:inline">
              All running on-device
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 divide-y-2 md:divide-y-0 md:divide-x-2 divide-bg-border">
            {AGENTS.map((agent, i) => (
              <div key={agent.num} className="p-5 lg:p-6 space-y-4">
                {/* Agent header */}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn('font-mono text-sm font-bold tabular-nums', agent.textClass)}>
                        {agent.num}
                      </span>
                      <agent.icon size={13} className={cn(agent.textClass, 'shrink-0')} />
                    </div>
                    <h3 className="font-display text-xl lg:text-2xl tracking-wider text-text-primary leading-tight">
                      {agent.label}
                    </h3>
                  </div>
                  <span
                    className={cn(
                      'font-mono text-xs font-bold uppercase tracking-wider px-1.5 py-0.5 shrink-0 mt-0.5 text-bg-base',
                      agent.badgeBg,
                    )}
                  >
                    {agent.badge}
                  </span>
                </div>

                {/* Description */}
                <div className={cn('border-l-2 pl-3', agent.borderClass)}>
                  <p className="font-mono text-base text-text-secondary leading-relaxed">
                    {agent.desc}
                  </p>
                </div>

                {/* Sample finding — dropdown */}
                <div className="bg-bg-surface border-2 border-bg-border">
                  <button
                    onClick={() => toggleFinding(i)}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left"
                  >
                    <span className="font-mono text-xs text-text-muted uppercase tracking-wider">
                      Sample Finding
                    </span>
                    <ChevronDown
                      size={13}
                      className={cn(
                        'shrink-0 text-text-muted transition-transform duration-200',
                        openFindings.has(i) && 'rotate-180',
                      )}
                    />
                  </button>
                  {openFindings.has(i) && (
                    <div className="px-3 pb-3 border-t-2 border-bg-border pt-2.5">
                      <p className={cn('font-mono text-sm italic leading-relaxed', agent.textClass)}>
                        {agent.finding}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Privacy / on-device callout (inverted) ── */}
      <section className="border-b-4 border-bg-border bg-bg-border text-bg-base">
        <div className="px-6 lg:px-12 py-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8">
          <div className="flex items-start gap-5">
            <Lock
              size={28}
              className="shrink-0 text-bg-surface mt-0.5"
              strokeWidth={1.5}
            />
            <div>
              <h2
                className="font-display tracking-wider leading-tight mb-3"
                style={{ fontSize: 'clamp(1.4rem, 3.5vw, 2.8rem)' }}
              >
                YOUR PITCH NEVER<br />LEAVES YOUR MACHINE.
              </h2>
              <p className="font-mono text-base text-bg-elevated leading-relaxed max-w-4xl">
                Pitches contain confidential roadmaps, customer names, and financial projections.
                PitchPilot runs Gemma 3n, FunctionGemma, and Gemma 3 entirely on-device via Ollama.{' '}
                <span className="text-bg-base font-bold whitespace-nowrap">
                  Zero telemetry. Zero cloud calls. Zero leaks.
                </span>
              </p>
            </div>
          </div>

          {/* Model stack */}
          <div className="shrink-0 lg:border-l-2 border-bg-surface lg:pl-8 space-y-3">
            <p className="font-mono text-sm text-bg-elevated uppercase tracking-[0.2em] mb-3">
              Model Stack
            </p>
            {[
              { name: 'GEMMA 3N E4B', role: 'Multimodal · OCR · Transcription' },
              { name: 'FUNCTIONGEMMA 270M', role: 'Agent routing · LoRA fine-tuned' },
              { name: 'GEMMA 3 4B', role: 'Coach · Compliance · Persona' },
            ].map((m) => (
              <div key={m.name}>
                <div className="font-display text-lg tracking-wider leading-tight">{m.name}</div>
                <div className="font-mono text-sm text-bg-elevated">{m.role}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pipeline / how it works ── */}
      <section className="border-b-4 border-bg-border">
        <div className="px-6 lg:px-12">
          <div className="py-2.5 border-b-2 border-bg-border flex items-center justify-between">
            <span className="font-display text-base tracking-widest text-text-muted">
              ANALYSIS PIPELINE · HOW IT WORKS
            </span>
            <span className="font-mono text-xs text-text-muted hidden sm:inline">
              Click a card to reveal details
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 py-4">
            {PIPELINE_STEPS.map((item, i) => (
              <div
                key={item.num}
                className="h-[172px]"
                style={{ perspective: '1000px' }}
              >
                <div
                  className={cn('flip-card-inner h-full cursor-pointer', flippedCards.has(i) && 'is-flipped')}
                  onClick={() => toggleCard(i)}
                >
                  {/* Front face */}
                  <div className="flip-card-face border-2 border-bg-border bg-bg-surface shadow-brutal p-4 flex flex-col justify-between">
                    <div className="flex items-start justify-between">
                      <span className="font-mono text-xs text-text-muted tabular-nums">{item.num}</span>
                      <span className="font-mono text-[10px] text-text-muted opacity-40 uppercase tracking-widest">flip</span>
                    </div>
                    <div>
                      <h4 className="font-display text-2xl lg:text-3xl tracking-wider text-text-primary leading-tight mb-2">
                        {item.step}
                      </h4>
                      <p className="font-mono text-xs text-accent-amber uppercase tracking-wider">
                        {item.tech}
                      </p>
                    </div>
                  </div>

                  {/* Back face */}
                  <div className="flip-card-face flip-card-back border-2 border-bg-border bg-bg-border p-4 flex flex-col justify-between">
                    <span className="font-mono text-xs text-bg-elevated tabular-nums">{item.num}</span>
                    <p className="font-mono text-sm text-bg-base leading-relaxed">
                      {item.desc}
                    </p>
                    <span className="font-mono text-[10px] text-bg-elevated opacity-60 uppercase tracking-widest">
                      ← flip back
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section>
        <div className="px-6 lg:px-12 py-14 lg:py-20 flex flex-col items-center gap-7 text-center">
          <p
            className="font-display tracking-wider text-text-primary leading-tight"
            style={{ fontSize: 'clamp(1.8rem, 5vw, 4rem)' }}
          >
            STRESS-TEST YOUR PITCH<br />BEFORE THE ROOM DOES.
          </p>
          <p className="font-mono text-sm text-text-secondary max-w-lg leading-relaxed">
            Upload a recording and get a scored readiness report in under 3 minutes on Apple Silicon.
            Or go live — agents flag issues as you speak.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={onLaunch}
              className="px-10 py-4 font-display text-2xl lg:text-3xl tracking-widest bg-bg-border text-bg-base border-2 border-bg-border shadow-brutal-lg brutal-hover"
            >
              LAUNCH APP →
            </button>
            <button
              onClick={onGoLive ?? onLaunch}
              className="px-8 py-4 font-display text-2xl lg:text-3xl tracking-widest border-2 border-accent-red text-accent-red hover:bg-accent-red hover:text-bg-base transition-colors shadow-brutal-red brutal-hover flex items-center justify-center gap-3"
            >
              <Radio size={20} strokeWidth={1.5} />
              GO LIVE
            </button>
            <button
              onClick={onDemo}
              className="px-8 py-4 font-mono text-sm uppercase tracking-widest border-2 border-bg-border bg-bg-surface text-text-secondary hover:bg-bg-elevated transition-colors flex items-center justify-center gap-2"
            >
              <Zap size={14} />
              DEMO ONLY
            </button>
          </div>
          <p className="font-mono text-sm text-text-muted">
            No account. No cloud. No upload limits.
          </p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t-4 border-bg-border px-6 lg:px-12 py-4 bg-bg-surface">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="font-display text-3xl tracking-wider text-text-primary">P<span className="italic">ITCH</span><span className="ml-4">PILOT</span></span>
            <span className="font-mono text-xs text-text-muted border border-bg-border px-1.5 py-0.5 uppercase tracking-wider">
              On-Device
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
            <span className="font-mono text-xs text-text-muted">
              Gemma 3n · FunctionGemma 270M · Gemma 3 4B
            </span>
            <span className="font-mono text-xs text-text-muted hidden sm:inline">
              All models run locally via Ollama
            </span>
            <span className="font-mono text-xs text-text-muted hidden md:inline">
              Built for Apple Silicon
            </span>
          </div>
        </div>
      </footer>

    </div>
  );
}
