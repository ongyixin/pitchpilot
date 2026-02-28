/**
 * Demo fixture data in the src/types/index.ts ReadinessReport shape.
 *
 * Used when the user clicks "Load demo" on the setup screen.
 * Mirrors the data returned by POST /api/session/demo on the backend.
 */

import type {
  ReadinessReport,
  TimelineAnnotation,
  Finding,
  PersonaQuestion,
  Claim,
  ReadinessScore,
  DimensionScore,
} from '@/types';

// ---------------------------------------------------------------------------
// Claims
// ---------------------------------------------------------------------------

const CLAIMS: Claim[] = [
  {
    id: 'c-001',
    text: 'Our platform is fully automated — no manual review required.',
    claim_type: 'feature',
    timestamp: 34.5,
    source: 'transcript',
    confidence: 0.93,
  },
  {
    id: 'c-002',
    text: 'We achieve 99.9 % uptime across all enterprise tiers.',
    claim_type: 'metric',
    timestamp: 72.0,
    source: 'slide',
    slide_number: 4,
    confidence: 0.88,
  },
  {
    id: 'c-003',
    text: 'All customer data is stored exclusively on-device — nothing leaves your network.',
    claim_type: 'privacy',
    timestamp: 112.0,
    source: 'both',
    slide_number: 6,
    confidence: 0.91,
  },
  {
    id: 'c-004',
    text: 'We outperform every competitor by 3× on inference speed.',
    claim_type: 'comparison',
    timestamp: 155.0,
    source: 'transcript',
    confidence: 0.80,
  },
];

// ---------------------------------------------------------------------------
// Findings
// ---------------------------------------------------------------------------

const FINDINGS: Finding[] = [
  // Coach
  {
    id: 'f-001',
    agent: 'coach',
    severity: 'info',
    title: 'Strong opening hook',
    detail:
      'The opening anecdote about a failed product demo was vivid and relatable. It established stakes immediately.',
    timestamp: 5.0,
  },
  {
    id: 'f-002',
    agent: 'coach',
    severity: 'warning',
    title: 'Abrupt transition after problem statement',
    detail:
      'The transition from the problem slide to the demo felt rushed. There was no bridge sentence to orient the audience before the product walkthrough began.',
    suggestion:
      "Add a one-sentence recap: 'That's the problem — here's how PitchPilot solves it.'",
    timestamp: 28.0,
  },
  {
    id: 'f-003',
    agent: 'coach',
    severity: 'warning',
    title: 'Solution slide overloaded with jargon',
    detail:
      "Slide 3 uses 'multi-agent orchestration', 'LoRA fine-tuning', and 'tokenised function dispatch' without explanation. Non-technical audiences disengage.",
    suggestion:
      "Lead with the outcome ('analyzes your pitch in 90 seconds') before explaining the mechanism.",
    timestamp: 118.0,
  },
  {
    id: 'f-004',
    agent: 'coach',
    severity: 'critical',
    title: 'Speed metric lacks benchmark context',
    detail:
      "'3× faster' is a compelling claim but the baseline is never stated. Sophisticated audiences will dismiss unanchored comparisons.",
    suggestion:
      "Name the competitor and link to a reproducible benchmark. E.g. 'vs. GPT-4o on the MLPerf inference suite'.",
    timestamp: 155.0,
    claim_id: 'c-004',
  },
  // Compliance
  {
    id: 'f-005',
    agent: 'compliance',
    severity: 'critical',
    title: "'Fully automated' conflicts with policy §3.2",
    detail:
      'Your enterprise data-handling policy (section 3.2) requires human review for model outputs above a confidence threshold of 0.95. Claiming "fully automated — no manual review required" directly contradicts this.',
    suggestion:
      "Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
    timestamp: 34.5,
    claim_id: 'c-001',
    policy_reference: 'Enterprise Data Policy §3.2 — Human Oversight Requirement',
  },
  {
    id: 'f-006',
    agent: 'compliance',
    severity: 'warning',
    title: "99.9 % uptime SLA not reflected in current contract",
    detail:
      'The standard enterprise contract offers 99.5 % SLA. Promising 99.9 % during a pitch creates a potential contractual liability.',
    suggestion:
      "Either reference the premium-tier SLA or say 'up to 99.9 %' with a footnote.",
    timestamp: 72.0,
    claim_id: 'c-002',
    policy_reference: 'SLA Addendum v2 — Enterprise Standard Tier',
  },
  {
    id: 'f-007',
    agent: 'compliance',
    severity: 'warning',
    title: "'Nothing leaves your network' needs qualification",
    detail:
      'Architecture slide 8 shows an optional cloud-sync feature. The blanket privacy claim may be technically false for customers who enable it.',
    suggestion: "Add 'by default' and mention the opt-in cloud sync explicitly.",
    timestamp: 112.0,
    claim_id: 'c-003',
    policy_reference: 'Privacy Disclosure Policy §1.1 — Accurate Representation',
  },
  // Persona
  {
    id: 'f-008',
    agent: 'persona',
    severity: 'warning',
    title: 'Skeptical Investor: differentiation is unclear',
    detail:
      'After hearing the pitch, a skeptical investor would immediately ask how this differs from a well-prompted ChatGPT plus screen recording. The on-device angle is the key differentiator but it was mentioned only once, in passing.',
    suggestion: 'Lead with the on-device / privacy differentiator earlier and repeat it at close.',
    timestamp: 90.0,
    persona: 'Skeptical Investor',
  },
  {
    id: 'f-009',
    agent: 'persona',
    severity: 'info',
    title: 'Technical Reviewer: model card details appreciated',
    detail:
      'The Technical Reviewer persona found the mention of specific model names (Gemma 3n, FunctionGemma) credible and reassuring.',
    timestamp: 130.0,
    persona: 'Technical Reviewer',
  },
  {
    id: 'f-010',
    agent: 'persona',
    severity: 'warning',
    title: 'Compliance Officer: data retention policy missing',
    detail:
      'No mention of how long rehearsal recordings are retained locally. A Compliance Officer would flag this immediately in regulated industries.',
    suggestion:
      'Add one slide or bullet on local-only storage, auto-deletion policy, and no cloud upload.',
    timestamp: 175.0,
    persona: 'Compliance Officer',
  },
];

// ---------------------------------------------------------------------------
// Persona questions
// ---------------------------------------------------------------------------

const PERSONA_QUESTIONS: PersonaQuestion[] = [
  {
    id: 'q-001',
    persona: 'Skeptical Investor',
    question: 'How is this different from asking ChatGPT to review my slide deck?',
    follow_up:
      "And if the answer is 'on-device', why can't a compliance-aware wrapper around GPT-4o do the same thing?",
    timestamp: 90.0,
    difficulty: 'critical',
  },
  {
    id: 'q-002',
    persona: 'Skeptical Investor',
    question: "What does '3× faster' mean, and is there a published benchmark?",
    timestamp: 155.0,
    difficulty: 'warning',
  },
  {
    id: 'q-003',
    persona: 'Compliance Officer',
    question:
      "Your slides say 'no data leaves the device' but slide 8 shows a cloud sync icon — can you clarify?",
    timestamp: 112.0,
    difficulty: 'critical',
  },
  {
    id: 'q-004',
    persona: 'Compliance Officer',
    question:
      'Has your automated decision pipeline been reviewed against GDPR Article 22 (automated decision-making)?',
    difficulty: 'warning',
  },
  {
    id: 'q-005',
    persona: 'Technical Reviewer',
    question:
      'What happens when Gemma 3n hallucinates during OCR — is there a confidence threshold before a finding is surfaced?',
    timestamp: 50.0,
    difficulty: 'warning',
  },
];

// ---------------------------------------------------------------------------
// Readiness score
// ---------------------------------------------------------------------------

const DIMENSIONS: DimensionScore[] = [
  {
    dimension: 'Clarity',
    score: 78,
    rationale: 'Structure and flow are solid but two transitions need bridging.',
  },
  {
    dimension: 'Compliance',
    score: 61,
    rationale: 'Two critical policy conflicts found; addressable with rewording.',
  },
  {
    dimension: 'Defensibility',
    score: 68,
    rationale: 'Speed and uptime claims need benchmark citations.',
  },
  {
    dimension: 'Persuasiveness',
    score: 82,
    rationale: 'Opening hook and model specificity are strong trust signals.',
  },
];

const READINESS_SCORE: ReadinessScore = {
  overall: 72,
  dimensions: DIMENSIONS,
  priority_fixes: [
    "Fix the 'fully automated' claim — it directly contradicts Enterprise Data Policy §3.2.",
    "Anchor the '3× faster' metric to a named competitor and public benchmark.",
    "Qualify the privacy claim: add 'by default' to cover the opt-in cloud sync.",
    'Add a bridge sentence between the problem slide and the demo.',
  ],
};

// ---------------------------------------------------------------------------
// Timeline annotations
// ---------------------------------------------------------------------------

const TIMELINE: TimelineAnnotation[] = [
  { id: 't-001', finding_id: 'f-001', category: 'coach',      timestamp: 5.0,   label: 'Strong hook',                  severity: 'info' },
  { id: 't-002', finding_id: 'f-002', category: 'coach',      timestamp: 28.0,  label: 'Abrupt transition',            severity: 'warning' },
  { id: 't-003', finding_id: 'f-005', category: 'compliance', timestamp: 34.5,  label: '"Fully automated" policy hit', severity: 'critical' },
  { id: 't-004', finding_id: 'f-006', category: 'compliance', timestamp: 72.0,  label: '99.9% SLA liability',          severity: 'warning' },
  { id: 't-005', finding_id: 'f-008', category: 'persona',    timestamp: 90.0,  label: 'Investor: differentiation?',   severity: 'warning' },
  { id: 't-006', finding_id: 'f-007', category: 'compliance', timestamp: 112.0, label: 'Privacy claim too broad',      severity: 'warning' },
  { id: 't-007', finding_id: 'f-003', category: 'coach',      timestamp: 118.0, label: 'Jargon overload on slide 3',   severity: 'warning' },
  { id: 't-008', finding_id: 'f-009', category: 'persona',    timestamp: 130.0, label: 'Tech reviewer: credible',      severity: 'info' },
  { id: 't-009', finding_id: 'f-004', category: 'coach',      timestamp: 155.0, label: '3× speed — no benchmark',     severity: 'critical' },
  { id: 't-010', finding_id: 'f-010', category: 'persona',    timestamp: 175.0, label: 'Data retention policy gap',    severity: 'warning' },
];

// ---------------------------------------------------------------------------
// Full report
// ---------------------------------------------------------------------------

export const DEMO_REPORT: ReadinessReport = {
  session_id: 'demo-session-0000',
  score: READINESS_SCORE,
  findings: FINDINGS,
  persona_questions: PERSONA_QUESTIONS,
  claims: CLAIMS,
  summary:
    'Overall readiness is 72/100. The pitch has a strong hook and credible technical specificity, ' +
    'but two compliance conflicts need resolution before presenting to an enterprise buyer. ' +
    'The privacy and automation claims are the highest-risk items. ' +
    'Prepare for the ChatGPT differentiation question — it will come from every audience.',
  created_at: new Date().toISOString(),
};

export const DEMO_TIMELINE: TimelineAnnotation[] = TIMELINE;
