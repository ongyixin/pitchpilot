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
    text: 'Good morning, we are presenting PitchPilot, an on-device AI sales coach for InstaLILY sales reps.',
    claim_type: 'feature',
    timestamp: 2.0,
    source: 'transcript',
    confidence: 0.98,
  },
  {
    id: 'c-002',
    text: 'PitchPilot runs locally on your laptop because your sales playbook and pricing strategy cannot leave the device.',
    claim_type: 'privacy',
    timestamp: 6.0,
    source: 'transcript',
    confidence: 0.95,
  },
  {
    id: 'c-003',
    text: 'Our system integrates seamlessly with your existing CRM and ERP workflows including SAP and Oracle.',
    claim_type: 'feature',
    timestamp: 12.0,
    source: 'transcript',
    confidence: 0.88,
  },
  {
    id: 'c-004',
    text: 'We guarantee ROI within 90 days for every InstaLILY customer.',
    claim_type: 'metric',
    timestamp: 17.0,
    source: 'transcript',
    confidence: 0.85,
  },
  {
    id: 'c-005',
    text: 'Our on-device model processes sales conversations in real time with no latency.',
    claim_type: 'feature',
    timestamp: 23.0,
    source: 'transcript',
    confidence: 0.90,
  },
  {
    id: 'c-006',
    text: 'We are the only company building domain-trained on-device sales coaching for distribution verticals.',
    claim_type: 'comparison',
    timestamp: 29.0,
    source: 'transcript',
    confidence: 0.82,
  },
  {
    id: 'c-007',
    text: 'Our finetuned FunctionGemma model outperforms base Gemma on enterprise sales objection detection.',
    claim_type: 'feature',
    timestamp: 38.0,
    source: 'transcript',
    confidence: 0.91,
  },
  {
    id: 'c-008',
    text: 'InstaLILY sales reps using PitchPilot will close 40% more enterprise deals.',
    claim_type: 'metric',
    timestamp: 47.0,
    source: 'transcript',
    confidence: 0.87,
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
    title: 'Clear value proposition established',
    detail:
      'The opening statement clearly establishes PitchPilot as an on-device AI sales coach for InstaLILY sales reps. The privacy angle is immediately clear.',
    timestamp: 4.0,
    claim_id: 'c-001',
    live: true,
  },
  {
    id: 'f-002',
    agent: 'compliance',
    severity: 'warning',
    title: 'Integration claim lacks technical detail',
    detail:
      "The claim about 'seamless integration' with SAP and Oracle is vague. Ops managers will immediately ask for specifics about data mapping, transformation, timeline, and cost.",
    suggestion:
      'Prepare detailed answers about ETL processes, data mapping, and integration timelines before making this claim.',
    timestamp: 12.0,
    claim_id: 'c-003',
    live: true,
    cue_hint: 'integration detail needed',
  },
  {
    id: 'f-003',
    agent: 'persona',
    severity: 'critical',
    title: 'Ops Manager: integration question incoming',
    detail:
      "An ops manager will challenge the SAP/Oracle integration claim. They need specifics on data mapping, transformation processes, timeline, and cost.",
    suggestion:
      'Be ready with: phased integration strategy, ETL tool details, 6-8 week pilot timeline, $15K-$30K cost estimate.',
    timestamp: 15.0,
    persona: 'ops_manager',
    live: true,
    cue_hint: 'integration question likely',
  },
  {
    id: 'f-004',
    agent: 'persona',
    severity: 'critical',
    title: 'Investor: ROI guarantee needs quantification',
    detail:
      "An investor will challenge the ROI guarantee. They need to know what 'ROI' means quantitatively and see case studies demonstrating consistent achievement.",
    suggestion:
      'Prepare: define ROI as 15-20% increase in close rates, reference beta testing data, offer to share case studies post-demo.',
    timestamp: 20.0,
    persona: 'investor',
    live: true,
    cue_hint: 'ROI question incoming',
  },
  {
    id: 'f-005',
    agent: 'coach',
    severity: 'info',
    title: 'Real-time processing claim is strong',
    detail:
      "The claim about 'no latency' real-time processing is compelling and differentiates PitchPilot from batch-processing alternatives.",
    timestamp: 23.0,
    claim_id: 'c-005',
    live: true,
  },
  {
    id: 'f-006',
    agent: 'persona',
    severity: 'critical',
    title: 'CTO: technical architecture question incoming',
    detail:
      "The 'only company' claim will prompt a CTO to immediately probe the on-device ML architecture and how continuous sales data collection is handled from a privacy standpoint.",
    suggestion:
      'Prepare: FunctionGemma architecture details, federated learning approach, encryption (in transit and at rest), data anonymization policy, opt-out controls.',
    timestamp: 31.0,
    claim_id: 'c-006',
    persona: 'cto',
    live: true,
    cue_hint: 'technical deep dive likely',
  },
  {
    id: 'f-007',
    agent: 'coach',
    severity: 'warning',
    title: '40% deal closure claim needs context',
    detail:
      "The '40% more enterprise deals' claim is bold but lacks context about baseline metrics, deal size, sales cycle duration, and customer acquisition costs.",
    suggestion:
      "Add context: 'Based on simulations and beta testing with InstaLILY's typical sales cycle and deal size.'",
    timestamp: 47.0,
    claim_id: 'c-008',
    live: true,
  },
];

// ---------------------------------------------------------------------------
// Persona questions
// ---------------------------------------------------------------------------

const PERSONA_QUESTIONS: PersonaQuestion[] = [
  {
    id: 'q-001',
    persona: 'ops_manager',
    question:
      "\u201cThat\u2019s a bold claim \u2013 can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what\u2019s the estimated timeline and cost for that integration?\u201d",
    timestamp: 15.0,
    difficulty: 'critical',
  },
  {
    id: 'q-002',
    persona: 'investor',
    question:
      "\u201cGuaranteeing ROI is a bold claim \u2013 can you quantify what \u2018ROI\u2019 actually means for a typical InstaLILY customer and demonstrate how you\u2019ve achieved this consistently across at least three separate case studies?\u201d",
    timestamp: 20.0,
    difficulty: 'critical',
  },
  {
    id: 'q-003',
    persona: 'cto',
    question:
      "That\u2019s a bold claim. Can you detail the specific on-device machine learning model architecture you\u2019re utilizing, and how you\u2019ve addressed potential privacy concerns related to continuous sales data collection?",
    timestamp: 31.0,
    difficulty: 'critical',
  },
];

// ---------------------------------------------------------------------------
// Readiness score
// ---------------------------------------------------------------------------

const DIMENSIONS: DimensionScore[] = [
  {
    dimension: 'Clarity',
    score: 75,
    rationale: 'Structure and flow are solid but integration and ROI claims need more detail.',
  },
  {
    dimension: 'Compliance',
    score: 70,
    rationale: 'Privacy and on-device claims are strong but need technical clarification for CTO-level audiences.',
  },
  {
    dimension: 'Defensibility',
    score: 65,
    rationale: 'ROI guarantee and 40% deal closure claims need quantified context and case study support.',
  },
  {
    dimension: 'Persuasiveness',
    score: 78,
    rationale: 'Clear value proposition and unique differentiation are strong, but integration vagueness weakens credibility.',
  },
];

const READINESS_SCORE: ReadinessScore = {
  overall: 72,
  dimensions: DIMENSIONS,
  priority_fixes: [
    'Develop a Detailed Integration Case Study: Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.',
    'Quantify InstaLILY\'s ROI: Replace the blanket "40%" claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.',
    'Prepare a Privacy FAQ: Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures.',
  ],
};

// ---------------------------------------------------------------------------
// Timeline annotations
// ---------------------------------------------------------------------------

const TIMELINE: TimelineAnnotation[] = [
  { id: 't-001', finding_id: 'f-001', category: 'coach',      timestamp: 4.0,  label: 'Clear value proposition',      severity: 'info' },
  { id: 't-002', finding_id: 'f-002', category: 'compliance', timestamp: 12.0, label: 'Integration detail needed',    severity: 'warning' },
  { id: 't-003', finding_id: 'f-003', category: 'persona',    timestamp: 15.0, label: 'Ops Manager: integration Q',   severity: 'critical' },
  { id: 't-004', finding_id: 'f-004', category: 'persona',    timestamp: 20.0, label: 'Investor: ROI question',       severity: 'critical' },
  { id: 't-005', finding_id: 'f-005', category: 'coach',      timestamp: 23.0, label: 'Real-time claim strong',       severity: 'info' },
  { id: 't-006', finding_id: 'f-006', category: 'persona',    timestamp: 31.0, label: 'CTO: architecture question',   severity: 'critical' },
  { id: 't-007', finding_id: 'f-007', category: 'coach',      timestamp: 47.0, label: '40% claim needs context',      severity: 'warning' },
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
    '## Readiness Score: 6/10\n\n' +
    '## ✅ What\'s Working\n' +
    '*   **Clear Value Proposition:** The core benefit – increased deal closure rates – "InstaLILY sales reps will close 40% more enterprise deals" – is immediately understandable and impactful.\n' +
    '*   **Unique Differentiation:** The emphasis on "on-device AI sales coaching" and "domain-trained" sets PitchPilot apart from generic AI solutions and highlights a key technical advantage.\n' +
    '*   **Specific ROI Claim:** Guaranteeing ROI within 90 days, paired with a concrete percentage, provides a tangible target for the customer.\n\n\n' +
    '## ⚠️ Weak Points\n' +
    '*   **Data Integration Vagueness:** The pitch glosses over the complexities of SAP and Oracle integration, which is a significant hurdle for large enterprises. "Seamless integration" lacks detail and appears to overpromise.\n' +
    '*   **Quantified ROI Ambiguity:** "Guaranteeing ROI" and the 40% deal closure rate feels speculative without deeper context around InstaLILY\'s typical sales cycle, average deal size, and customer acquisition costs.\n' +
    '*   **Technical Detail Shortfall:** The mention of FunctionGemma and its performance improvement is impressive but requires further explanation to establish credibility, especially regarding the privacy concerns.\n\n\n' +
    '## ❓ Objections You Must Prepare For\n' +
    '*   **[OPS_MANAGER]: "That\'s a bold claim – can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what\'s the estimated timeline and cost for that integration?"**\n' +
    '    *   **Suggested Answer:** "Absolutely. We recognize that data integration is critical. Our team is already developing a phased integration strategy, starting with prioritized data fields – specifically order history, customer contacts, and pricing. We use a robust ETL process utilizing [Name a specific ETL tool, e.g., Fivetran] to map and transform data.  We estimate a 6-8 week initial integration for a pilot group, with a cost of [State a realistic estimated cost range, e.g., $15,000 - $30,000] for development and configuration.  We can provide a detailed technical specification document post-demo if that\'s helpful."\n\n' +
    '*   **[INVESTOR]: "Guaranteeing ROI is a bold claim – can you quantify what \'ROI\' actually means for a typical InstaLILY customer and demonstrate how you\'ve achieved this consistently across at least three separate case studies?"**\n' +
    '    *   **Suggested Answer:** "You\'re right to challenge that. For a typical InstaLILY customer, ROI translates to an average of a 15-20% increase in close rates, based on our simulations and early beta testing. We\'re currently compiling three detailed case studies with pilot customers that demonstrate this – we\'ll share the full documentation after the demo, including projected revenue increases and cost savings. We can also discuss a tailored ROI projection based on your specific sales data."\n\n' +
    '*   **[CTO]: That\'s a bold claim. Can you detail the specific on-device machine learning model architecture you\'re utilizing, and how you\'ve addressed potential privacy concerns related to continuous sales data collection?**\n' +
    '    *   **Suggested Answer:** "Our model is based on a FunctionGemma architecture, but it\'s been significantly finetuned for enterprise sales objection detection. We employ a federated learning approach where the model updates are generated locally on each rep\'s laptop, minimizing data transfer. All data is encrypted both in transit and at rest, and we operate under a strict data anonymization policy. Reps retain full control over their data and can opt-out at any time. We can provide a more technical deep dive during a follow-up session."\n\n\n\n' +
    '## 🎯 Top 3 Things To Fix Before The Real Demo\n' +
    '1.  **Develop a Detailed Integration Case Study:** Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.\n' +
    '2.  **Quantify InstaLILY\'s ROI:**  Replace the blanket "40%" claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.\n' +
    '3.  **Prepare a Privacy FAQ:** Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures.',
  created_at: new Date().toISOString(),
  session_mode: 'live_in_room',
  session_duration_seconds: 48,
  live_cues_count: 3,
};

export const DEMO_TIMELINE: TimelineAnnotation[] = TIMELINE;
