import type { ReadinessReport, TimelineAnnotation, Finding } from '@/types/api';

// StatusResponse shape for mock polling (matches SessionStatusResponse in @/types/index.ts)
export const MOCK_STATUS_SEQUENCE = [
  { session_id: 'demo-001', status: 'processing', progress: 8,  progress_message: 'Extracting video frames at 1 fps…' },
  { session_id: 'demo-001', status: 'processing', progress: 22, progress_message: 'Transcribing audio via Gemma 3n…' },
  { session_id: 'demo-001', status: 'processing', progress: 38, progress_message: 'Running OCR on slide frames…' },
  { session_id: 'demo-001', status: 'processing', progress: 52, progress_message: 'Extracting claims from transcript…' },
  { session_id: 'demo-001', status: 'processing', progress: 65, progress_message: 'FunctionGemma routing claims to agents…' },
  { session_id: 'demo-001', status: 'processing', progress: 75, progress_message: 'Presentation Coach analyzing narrative flow…' },
  { session_id: 'demo-001', status: 'processing', progress: 84, progress_message: 'Compliance Reviewer cross-checking claims…' },
  { session_id: 'demo-001', status: 'processing', progress: 91, progress_message: 'Persona Simulator generating stakeholder questions…' },
  { session_id: 'demo-001', status: 'processing', progress: 97, progress_message: 'Aggregating readiness score…' },
  { session_id: 'demo-001', status: 'complete',   progress: 100, progress_message: 'Analysis complete.' },
];

// ---------------------------------------------------------------------------
// Mock findings for review session
// ---------------------------------------------------------------------------

const REVIEW_FINDINGS: Finding[] = [
  {
    id: 'f-001', agent: 'compliance', severity: 'critical',
    title: '"Fully private" conflicts with policy §4.1',
    detail: 'At 2:34 you stated the product is "fully private and never sends data to the cloud." Policy §4.1 requires disclosure of optional cloud fallback mode.',
    suggestion: 'Change to: "Private by default — all processing runs on-device. An optional cloud mode is available for users who opt in."',
    timestamp: 154, policy_reference: 'Enterprise Data Policy §4.1',
  },
  {
    id: 'f-002', agent: 'compliance', severity: 'critical',
    title: '"Fully automated" conflicts with policy §3.2',
    detail: 'At 4:11 you claimed the workflow is "fully automated." Policy §3.2 mandates that edge cases require manual human review.',
    suggestion: 'Replace with: "Automated for 95% of standard cases; edge cases are flagged for manual review per our policy."',
    timestamp: 251, policy_reference: 'Enterprise Data Policy §3.2',
  },
  {
    id: 'f-003', agent: 'coach', severity: 'warning',
    title: 'Abrupt demo-to-business-model transition at 3:42',
    detail: 'The transition from the live demo to the business model is jarring. There is no bridging sentence, causing the audience to mentally context-switch without framing.',
    suggestion: 'Add: "What you just saw is the core product. Here\'s how we monetize it." before advancing the slide.',
    timestamp: 222,
  },
  {
    id: 'f-004', agent: 'coach', severity: 'warning',
    title: 'Solution slide overloaded with technical jargon',
    detail: 'Slide 3 uses "multi-agent orchestration," "LoRA fine-tuning," and "tokenized function dispatch" without explanation. Non-technical audiences will disengage.',
    suggestion: 'Lead with the outcome ("analyzes your pitch in 90 seconds") before explaining the mechanism.',
    timestamp: 118,
  },
  {
    id: 'f-005', agent: 'coach', severity: 'info',
    title: 'Strong problem statement — preserve this opening',
    detail: 'Your first 45 seconds are excellent. The "pitch rehearsal is a black box" hook is memorable and clearly frames the gap.',
    timestamp: 12,
  },
  {
    id: 'f-006', agent: 'persona', severity: 'warning',
    title: 'Skeptical Investor: "Why not just use ChatGPT?"',
    detail: 'This question arose from generic AI differentiation framing on the traction slide. The on-device angle has not been emphasised strongly enough.',
    suggestion: 'Prepare: "ChatGPT requires sending your pitch to the cloud. PitchPilot runs on-device with specialized models for each evaluation task."',
    timestamp: 298, persona: 'skeptical_investor',
  },
  {
    id: 'f-007', agent: 'persona', severity: 'info',
    title: 'Technical Reviewer: On-device inference latency?',
    detail: 'Technical Reviewer wants specifics on inference latency for the 90-second claim.',
    suggestion: 'Have concrete benchmarks ready: "On an M2 MacBook Pro: 90s for a 5-minute video, 4.2s/frame OCR, real-time audio."',
    timestamp: 198, persona: 'technical_reviewer',
  },
  {
    id: 'f-008', agent: 'compliance', severity: 'warning',
    title: 'ROI claim lacks supporting data',
    detail: 'At 5:20 you claimed "3x close rate improvement" without citing a source or pilot data.',
    suggestion: 'Add source: cite pilot customer or qualify as "hypothesis to be validated in pilot."',
    timestamp: 320, policy_reference: 'See traction slide',
  },
];

export const MOCK_TIMELINE: TimelineAnnotation[] = [
  { id: 'tl-001', timestamp: 12,  category: 'coach',      label: 'Strong hook',                  finding_id: 'f-005', severity: 'info' },
  { id: 'tl-002', timestamp: 118, category: 'coach',      label: 'Jargon overload on slide 3',   finding_id: 'f-004', severity: 'warning' },
  { id: 'tl-003', timestamp: 154, category: 'compliance', label: '"Fully private" claim',         finding_id: 'f-001', severity: 'critical' },
  { id: 'tl-004', timestamp: 198, category: 'persona',    label: 'Latency question',             finding_id: 'f-007', severity: 'info' },
  { id: 'tl-005', timestamp: 222, category: 'coach',      label: 'Demo transition gap',          finding_id: 'f-003', severity: 'warning' },
  { id: 'tl-006', timestamp: 251, category: 'compliance', label: '"Fully automated" claim',      finding_id: 'f-002', severity: 'critical' },
  { id: 'tl-007', timestamp: 298, category: 'persona',    label: '"Why not ChatGPT?"',           finding_id: 'f-006', severity: 'warning' },
  { id: 'tl-008', timestamp: 320, category: 'compliance', label: 'Unsourced ROI claim',          finding_id: 'f-008', severity: 'warning' },
];

export const MOCK_REPORT: ReadinessReport = {
  session_id: 'demo-001',
  summary:
    'Your pitch has strong narrative momentum and clear problem framing. The main risks are an overreaching privacy claim on slide 4 and an abrupt transition from the demo to the business model. The skeptical investor persona surfaces the sharpest questions — prepare those answers before your next rehearsal.',
  created_at: new Date().toISOString(),
  claims: [],

  score: {
    overall: 72,
    dimensions: [
      { dimension: 'Clarity',        score: 78, rationale: 'Clear problem statement; solution slides are dense with jargon.' },
      { dimension: 'Compliance',     score: 61, rationale: 'Two claims directly conflict with policy doc. "Fully automated" and "fully private" need qualification.' },
      { dimension: 'Defensibility',  score: 74, rationale: 'Investor persona questions are answerable but require better data. Technical objections are solid.' },
      { dimension: 'Persuasiveness', score: 81, rationale: 'Strong open and close. Demo transition at 3:42 is rough — tighten the segue.' },
    ],
    priority_fixes: [
      'Qualify the "fully private" claim on slide 4: add "by default" or "when configured with on-device mode".',
      'Replace "fully automated" with "automated for standard cases, with optional manual review for edge cases" to align with policy §3.2.',
      'Add a one-sentence bridge between the live demo and the business model slide (currently jumps too abruptly at 3:42).',
      'Prepare a crisp ≤30-second answer to "How is this different from just using ChatGPT?"',
    ],
  },

  findings: REVIEW_FINDINGS,

  persona_questions: [
    {
      id: 'q-001', persona: 'Skeptical Investor', difficulty: 'critical',
      question: 'How is this meaningfully different from asking ChatGPT to review my pitch script?',
      timestamp: 298,
      follow_up: 'Three key differences: on-device privacy (no data leaves the machine), multimodal analysis (video + slides + audio, not just text), and specialized models fine-tuned for pitch evaluation rather than general conversation.',
    },
    {
      id: 'q-002', persona: 'Skeptical Investor', difficulty: 'warning',
      question: 'What is your go-to-market strategy and why will enterprise sales teams adopt this?',
      follow_up: 'Focus on compliance-sensitive industries (fintech, healthcare) where on-device is a requirement, not a feature.',
    },
    {
      id: 'q-003', persona: 'Technical Reviewer', difficulty: 'warning',
      question: 'What is the actual end-to-end latency on consumer hardware? Have you measured it?',
      timestamp: 198,
      follow_up: 'M2 MacBook Pro: 87s for a 5-min video. M1: ~2min. Windows with CUDA: ~45s.',
    },
    {
      id: 'q-004', persona: 'Compliance Officer', difficulty: 'critical',
      question: 'How do you ensure the AI\'s compliance assessments are not themselves a compliance liability?',
      follow_up: 'The tool surfaces potential issues for human review — it does not make compliance determinations. All outputs are framed as "suggested review items."',
    },
    {
      id: 'q-005', persona: 'Technical Reviewer', difficulty: 'info',
      question: 'Why FunctionGemma for routing instead of a simpler classifier?',
      follow_up: 'FunctionGemma was designed specifically for function dispatch with structured output. A classifier would require separate handling of argument extraction.',
    },
  ],
};

// ---------------------------------------------------------------------------
// Live in-room session mock
// ---------------------------------------------------------------------------

const LIVE_INROOM_FINDINGS: Finding[] = [
  {
    id: 'lf-001', agent: 'coach', severity: 'info',
    title: 'Strong opening hook captured live',
    detail: 'The opening anecdote about a failed product demo was vivid and relatable. It established stakes immediately.',
    timestamp: 12, live: true,
  },
  {
    id: 'lf-002', agent: 'compliance', severity: 'critical',
    title: "'Fully automated' conflicts with policy §3.2",
    detail: "Policy §3.2 requires human review for high-stakes model outputs. Claiming 'fully automated' directly contradicts this.",
    suggestion: "Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
    timestamp: 34, live: true, cue_hint: 'compliance risk', policy_reference: 'Enterprise Data Policy §3.2',
  },
  {
    id: 'lf-003', agent: 'coach', severity: 'warning',
    title: 'Pacing fast through uptime metric',
    detail: 'The 99.9% uptime claim was delivered quickly without a pause. Sophisticated audiences need a moment to register numeric claims.',
    suggestion: 'Add a 1–2 second pause after stating uptime figures to let them land.',
    timestamp: 70, live: true, cue_hint: 'slow down',
  },
  {
    id: 'lf-004', agent: 'compliance', severity: 'warning',
    title: "'Nothing leaves your network' needs qualification",
    detail: 'The blanket on-device privacy claim may be technically false for customers who enable the optional cloud-sync feature.',
    suggestion: "Add 'by default' and mention the opt-in cloud sync explicitly.",
    timestamp: 112, live: true, cue_hint: 'mention privacy',
  },
  {
    id: 'lf-005', agent: 'coach', severity: 'critical',
    title: 'Speed metric lacks benchmark context',
    detail: "'3× faster' is compelling but the baseline is never stated. Sophisticated audiences dismiss unanchored comparisons.",
    suggestion: 'Name the competitor and link to a reproducible benchmark.',
    timestamp: 155, live: true, cue_hint: 'name the benchmark',
  },
  {
    id: 'lf-006', agent: 'persona', severity: 'warning',
    title: 'Skeptical Investor: ROI question anticipated',
    detail: 'Based on claims heard, a skeptical investor will ask about ROI and differentiation from ChatGPT. On-device angle not yet emphasised.',
    suggestion: 'Lead with the on-device / privacy differentiator and repeat it at close.',
    timestamp: 198, persona: 'skeptical_investor', live: true, cue_hint: 'ROI question likely',
  },
  {
    id: 'lf-007', agent: 'compliance', severity: 'info',
    title: '99.9% uptime SLA needs footnote',
    detail: 'Standard enterprise contract is 99.5% SLA. The 99.9% claim is achievable under premium tier but should be qualified.',
    suggestion: "Say 'up to 99.9% on the premium tier' and add a footnote.",
    timestamp: 72, live: true,
  },
  {
    id: 'lf-008', agent: 'coach', severity: 'warning',
    title: 'Differentiation from ChatGPT still unclear at close',
    detail: 'Four minutes in and the on-device differentiation has still not been stated crisply.',
    suggestion: "Closing line: 'Unlike cloud-based AI, everything runs on your device. No data leaves the room.'",
    timestamp: 285, live: true, cue_hint: 'clarify differentiation',
  },
  {
    id: 'lf-009', agent: 'persona', severity: 'warning',
    title: 'Compliance Officer: data retention policy not mentioned',
    detail: 'No mention of how long rehearsal recordings are retained locally.',
    suggestion: 'Add one sentence on local-only storage and auto-deletion policy.',
    timestamp: 240, persona: 'compliance_officer', live: true,
  },
];

export const MOCK_LIVE_INROOM_REPORT: ReadinessReport = {
  session_id: 'live-inroom-mock',
  session_mode: 'live_in_room',
  session_duration_seconds: 322,
  live_cues_count: 6,
  live_session_summary:
    "5:22 live in-room session. 6 earpiece cues delivered in real time. Two critical issues surfaced: the 'fully automated' compliance conflict and the unanchored 3× speed claim. The on-device differentiator was underemphasised — repeat it earlier and at close.",
  summary:
    'Overall readiness is 74/100. The pitch has a strong hook and credible technical specificity, but two compliance conflicts need resolution before the next session. The privacy and automation claims are the highest-risk items.',
  created_at: new Date().toISOString(),
  claims: [],

  score: {
    overall: 74,
    dimensions: [
      { dimension: 'Clarity',        score: 76, rationale: 'Structure and flow were solid live. Jargon overload and abrupt transitions are addressable.' },
      { dimension: 'Compliance',     score: 63, rationale: "Two critical policy conflicts detected live. 'Fully automated' and privacy claims need rewording." },
      { dimension: 'Defensibility',  score: 69, rationale: 'Speed and uptime claims need benchmark citations. ROI and ChatGPT differentiation gaps flagged.' },
      { dimension: 'Persuasiveness', score: 80, rationale: 'Opening hook and on-device framing are strong. Close needs a crisper differentiator statement.' },
    ],
    priority_fixes: [
      "Fix the 'fully automated' claim — it directly contradicts Enterprise Data Policy §3.2.",
      "Anchor the '3× faster' metric to a named competitor and public benchmark.",
      "Qualify the privacy claim: add 'by default' to cover the opt-in cloud sync.",
      "Add a bridge sentence between the demo and the business-model slide.",
    ],
  },

  findings: LIVE_INROOM_FINDINGS,

  persona_questions: [
    {
      id: 'lq-001', persona: 'Skeptical Investor', difficulty: 'critical', timestamp: 198,
      question: 'How is this meaningfully different from asking ChatGPT to review my pitch?',
      follow_up: 'Three differences: on-device privacy (no data leaves), multimodal analysis (video + slides + audio), and specialized Gemma models fine-tuned for pitch evaluation.',
    },
    {
      id: 'lq-002', persona: 'Skeptical Investor', difficulty: 'warning', timestamp: 155,
      question: "What does '3× faster' mean exactly — 3× vs. which competitor, on which benchmark?",
    },
    {
      id: 'lq-003', persona: 'Compliance Officer', difficulty: 'critical', timestamp: 112,
      question: "You said 'no data leaves the device' — does that apply even when the optional cloud sync is enabled?",
      follow_up: "Our default mode is fully on-device. Cloud sync is opt-in and clearly labeled.",
    },
    {
      id: 'lq-004', persona: 'Compliance Officer', difficulty: 'warning', timestamp: 240,
      question: 'How long are session recordings retained, and is there an auto-delete policy?',
    },
    {
      id: 'lq-005', persona: 'Technical Reviewer', difficulty: 'warning', timestamp: 70,
      question: 'What is the end-to-end latency from speaking a claim to receiving the earpiece cue?',
      follow_up: 'Typically 5–8 seconds on Apple Silicon: 2s audio chunk + 1–2s transcription + 0.5s claims + 1–2s agent + 0.3s TTS.',
    },
  ],
};

// ---------------------------------------------------------------------------
// Live remote session mock
// ---------------------------------------------------------------------------

const LIVE_REMOTE_FINDINGS: Finding[] = [
  {
    id: 'rf-001', agent: 'coach', severity: 'info',
    title: 'Opening hook strong — preserve for all audiences',
    detail: 'The opening 45 seconds established clear stakes and framed the problem memorably. Screen share was smooth from the start.',
    timestamp: 15, live: true,
  },
  {
    id: 'rf-002', agent: 'compliance', severity: 'critical',
    title: "'Fully automated' conflicts with policy §3.2 (slide 2)",
    detail: "Slide 2 and transcript both claim 'fully automated — no manual review.' Policy §3.2 mandates human review above a 0.95 confidence threshold.",
    suggestion: "Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
    timestamp: 45, live: true, cue_hint: 'compliance risk', policy_reference: 'Enterprise Data Policy §3.2',
  },
  {
    id: 'rf-003', agent: 'coach', severity: 'warning',
    title: 'Slide 3 overloaded with technical jargon',
    detail: "Slide 3 uses 'multi-agent orchestration', 'LoRA fine-tuning', and 'tokenised function dispatch' in the same bullet list.",
    suggestion: "Lead with the outcome ('analyzes your pitch in 90 seconds') before explaining the mechanism.",
    timestamp: 130, live: true, cue_hint: 'simplify slide',
  },
  {
    id: 'rf-004', agent: 'compliance', severity: 'warning',
    title: "'Nothing leaves your network' needs qualification (slide 4)",
    detail: 'Privacy claim on slide 4 conflicts with the optional cloud-sync icon on the architecture slide.',
    suggestion: "Add 'by default' and note the opt-in cloud sync.",
    timestamp: 200, live: true, cue_hint: 'mention privacy',
  },
  {
    id: 'rf-005', agent: 'persona', severity: 'info',
    title: 'Technical Reviewer: model specificity is credible',
    detail: 'The Technical Reviewer persona found mention of Gemma 3n, FunctionGemma, and LoRA fine-tuning reassuring and technically credible.',
    timestamp: 270, persona: 'technical_reviewer', live: true,
  },
  {
    id: 'rf-006', agent: 'coach', severity: 'critical',
    title: 'Speed metric lacks benchmark context (slide 6)',
    detail: "'3× faster' is compelling but the baseline is unstated. Technical reviewers on the call will immediately ask '3× vs. what?'",
    suggestion: 'Name the competitor and link to a reproducible benchmark.',
    timestamp: 255, live: true, cue_hint: 'name benchmark',
  },
  {
    id: 'rf-007', agent: 'persona', severity: 'warning',
    title: 'Skeptical Investor: ChatGPT differentiation question incoming',
    detail: 'The presentation has not yet explained why on-device matters vs. a compliance-aware GPT-4o wrapper.',
    suggestion: "Prepare: 'ChatGPT requires sending your pitch to the cloud and has no sales-specific fine-tuning.'",
    timestamp: 300, persona: 'skeptical_investor', live: true, cue_hint: 'ChatGPT pushback likely',
  },
  {
    id: 'rf-008', agent: 'coach', severity: 'warning',
    title: 'Abrupt transition slide 6 → 7',
    detail: 'The jump from the live demo to the business model slide felt unanchored. No bridging sentence to orient the remote audience.',
    suggestion: "Add: 'What you just saw is the core product. Here's how we monetize it.'",
    timestamp: 370, live: true, cue_hint: 'add bridge',
  },
  {
    id: 'rf-009', agent: 'compliance', severity: 'warning',
    title: '99.9% uptime SLA not reflected in standard contract (slide 4)',
    detail: 'Standard tier is 99.5%. Promising 99.9% on-screen without qualification creates potential contractual liability.',
    suggestion: "Add 'premium tier only' or 'up to 99.9%' footnote on slide 4.",
    timestamp: 405, live: true, cue_hint: 'add footnote',
  },
  {
    id: 'rf-010', agent: 'persona', severity: 'warning',
    title: 'Compliance Officer: data retention policy missing',
    detail: 'Eight minutes in and no mention of rehearsal recording retention.',
    suggestion: 'Add one sentence on local-only storage and auto-deletion policy.',
    timestamp: 440, persona: 'compliance_officer', live: true, cue_hint: 'mention retention',
  },
  {
    id: 'rf-011', agent: 'compliance', severity: 'info',
    title: 'Deployment time claim should cite conditions',
    detail: "'Under one hour' is plausible for single-user SaaS but enterprise on-device rollout typically requires IT approval cycles.",
    suggestion: "Add 'for standard single-user deployment' to the one-hour claim.",
    timestamp: 330, live: true,
  },
];

export const MOCK_LIVE_REMOTE_REPORT: ReadinessReport = {
  session_id: 'live-remote-mock',
  session_mode: 'live_remote',
  session_duration_seconds: 495,
  live_cues_count: 8,
  live_session_summary:
    "8:15 live remote session (Zoom screen share, 8 slides detected). 8 overlay cue cards delivered during the presentation. Two critical issues surfaced: the 'fully automated' compliance conflict and the unanchored 3× speed claim.",
  summary:
    'Overall readiness is 70/100. Strong opening and credible technical specificity, but two critical compliance conflicts and several qualifier-level issues need resolution.',
  created_at: new Date().toISOString(),
  claims: [],

  score: {
    overall: 70,
    dimensions: [
      { dimension: 'Clarity',        score: 72, rationale: 'Screen share was clear. Slide 3 jargon and the transition gap at slide 6→7 are the main clarity issues.' },
      { dimension: 'Compliance',     score: 58, rationale: 'Three compliance warnings detected from slides and transcript. Automation and privacy claims are highest risk.' },
      { dimension: 'Defensibility',  score: 70, rationale: "ChatGPT differentiation question anticipated but not answered in the deck. Benchmark citations missing." },
      { dimension: 'Persuasiveness', score: 79, rationale: 'Strong opening hook and model specificity. Close needs a crisper on-device differentiator.' },
    ],
    priority_fixes: [
      "Fix the 'fully automated' claim on slide 2 — it directly contradicts Enterprise Data Policy §3.2.",
      "Anchor the '3× faster' metric to a named competitor and public benchmark.",
      "Qualify the privacy claim on slide 4: add 'by default' to cover the opt-in cloud sync.",
      "Add a bridge sentence between the demo slide (6) and the business-model slide (7).",
      "Add a data-retention footnote to the architecture slide to pre-empt the compliance officer question.",
    ],
  },

  findings: LIVE_REMOTE_FINDINGS,

  persona_questions: [
    {
      id: 'rq-001', persona: 'Skeptical Investor', difficulty: 'critical', timestamp: 300,
      question: 'How is this different from a compliance-aware wrapper around GPT-4o?',
      follow_up: 'Three key differences: on-device privacy, multimodal analysis (slides + audio + video), and specialized Gemma models fine-tuned for pitch evaluation.',
    },
    {
      id: 'rq-002', persona: 'Skeptical Investor', difficulty: 'warning', timestamp: 255,
      question: "What does '3× faster' mean — 3× vs. which competitor, on which benchmark?",
    },
    {
      id: 'rq-003', persona: 'Compliance Officer', difficulty: 'critical', timestamp: 200,
      question: "The slide says 'nothing leaves the device' but there's a cloud-sync icon — which is accurate?",
      follow_up: "Our default mode is fully on-device. Cloud sync is opt-in and clearly labeled.",
    },
    {
      id: 'rq-004', persona: 'Compliance Officer', difficulty: 'warning', timestamp: 440,
      question: 'How long are session recordings retained, and is there an auditable deletion log?',
    },
    {
      id: 'rq-005', persona: 'Technical Reviewer', difficulty: 'warning', timestamp: 130,
      question: 'What is the end-to-end latency from a slide change to an overlay cue appearing?',
      follow_up: 'OCR runs every 5 seconds on slide frames; overlay cards typically arrive within 8–12 seconds of a slide change.',
    },
  ],
};
