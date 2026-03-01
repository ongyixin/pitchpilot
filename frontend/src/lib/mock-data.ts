import type { ReadinessReport, TimelineAnnotation, Finding } from '@/types/api';

// StatusResponse shape for mock polling (matches SessionStatusResponse in @/types/index.ts)
export const MOCK_STATUS_SEQUENCE = [
  { session_id: 'demo-001', status: 'processing', progress: 15, progress_message: 'Extracting video frames and transcribing audio…' },
  { session_id: 'demo-001', status: 'processing', progress: 35, progress_message: 'Running OCR on slide frames…' },
  { session_id: 'demo-001', status: 'processing', progress: 55, progress_message: 'Extracting claims from transcript…' },
  { session_id: 'demo-001', status: 'processing', progress: 70, progress_message: 'FunctionGemma routing claims to agents…' },
  { session_id: 'demo-001', status: 'processing', progress: 85, progress_message: 'Agents analyzing: Coach, Compliance, Persona…' },
  { session_id: 'demo-001', status: 'processing', progress: 95, progress_message: 'Aggregating readiness score…' },
  { session_id: 'demo-001', status: 'complete',   progress: 100, progress_message: 'Analysis complete.' },
];

// ---------------------------------------------------------------------------
// Mock findings for review session
// ---------------------------------------------------------------------------

const REVIEW_FINDINGS: Finding[] = [
  {
    id: 'f-001', agent: 'compliance', severity: 'critical',
    title: '"Fully private" conflicts with policy §4.1',
    detail: 'At 0:22 you stated the product is "fully private and never sends data to the cloud." Policy §4.1 requires disclosure of optional cloud fallback mode.',
    suggestion: 'Change to: "Private by default — all processing runs on-device. An optional cloud mode is available for users who opt in."',
    timestamp: 22, policy_reference: 'Enterprise Data Policy §4.1',
  },
  {
    id: 'f-002', agent: 'compliance', severity: 'critical',
    title: '"Fully automated" conflicts with policy §3.2',
    detail: 'At 0:36 you claimed the workflow is "fully automated." Policy §3.2 mandates that edge cases require manual human review.',
    suggestion: 'Replace with: "Automated for 95% of standard cases; edge cases are flagged for manual review per our policy."',
    timestamp: 36, policy_reference: 'Enterprise Data Policy §3.2',
  },
  {
    id: 'f-003', agent: 'coach', severity: 'warning',
    title: 'Abrupt demo-to-business-model transition at 0:32',
    detail: 'The transition from the live demo to the business model is jarring. There is no bridging sentence, causing the audience to mentally context-switch without framing.',
    suggestion: 'Add: "What you just saw is the core product. Here\'s how we monetize it." before advancing the slide.',
    timestamp: 32,
  },
  {
    id: 'f-004', agent: 'coach', severity: 'warning',
    title: 'Solution slide overloaded with technical jargon',
    detail: 'Slide 3 uses "multi-agent orchestration," "LoRA fine-tuning," and "tokenized function dispatch" without explanation. Non-technical audiences will disengage.',
    suggestion: 'Lead with the outcome ("analyzes your pitch in 90 seconds") before explaining the mechanism.',
    timestamp: 17,
  },
  {
    id: 'f-005', agent: 'coach', severity: 'info',
    title: 'Strong problem statement — preserve this opening',
    detail: 'Your first 5 seconds are excellent. The "pitch rehearsal is a black box" hook is memorable and clearly frames the gap.',
    timestamp: 2,
  },
  {
    id: 'f-006', agent: 'persona', severity: 'warning',
    title: 'Skeptical Investor: "Why not just use ChatGPT?"',
    detail: 'This question arose from generic AI differentiation framing on the traction slide. The on-device angle has not been emphasised strongly enough.',
    suggestion: 'Prepare: "ChatGPT requires sending your pitch to the cloud. PitchPilot runs on-device with specialized models for each evaluation task."',
    timestamp: 43, persona: 'skeptical_investor',
  },
  {
    id: 'f-007', agent: 'persona', severity: 'info',
    title: 'Technical Reviewer: On-device inference latency?',
    detail: 'Technical Reviewer wants specifics on inference latency for the 90-second claim.',
    suggestion: 'Have concrete benchmarks ready: "On an M2 MacBook Pro: 90s for a 5-minute video, 4.2s/frame OCR, real-time audio."',
    timestamp: 29, persona: 'technical_reviewer',
  },
  {
    id: 'f-008', agent: 'compliance', severity: 'warning',
    title: 'ROI claim lacks supporting data',
    detail: 'At 0:46 you claimed "3x close rate improvement" without citing a source or pilot data.',
    suggestion: 'Add source: cite pilot customer or qualify as "hypothesis to be validated in pilot."',
    timestamp: 46, policy_reference: 'See traction slide',
  },
];

export const MOCK_TIMELINE: TimelineAnnotation[] = [
  { id: 'tl-001', timestamp: 2,  category: 'coach',      label: 'Strong hook',                  finding_id: 'f-005', severity: 'info' },
  { id: 'tl-002', timestamp: 17, category: 'coach',      label: 'Jargon overload on slide 3',   finding_id: 'f-004', severity: 'warning' },
  { id: 'tl-003', timestamp: 22, category: 'compliance', label: '"Fully private" claim',         finding_id: 'f-001', severity: 'critical' },
  { id: 'tl-004', timestamp: 29, category: 'persona',    label: 'Latency question',             finding_id: 'f-007', severity: 'info' },
  { id: 'tl-005', timestamp: 32, category: 'coach',      label: 'Demo transition gap',          finding_id: 'f-003', severity: 'warning' },
  { id: 'tl-006', timestamp: 36, category: 'compliance', label: '"Fully automated" claim',      finding_id: 'f-002', severity: 'critical' },
  { id: 'tl-007', timestamp: 43, category: 'persona',    label: '"Why not ChatGPT?"',           finding_id: 'f-006', severity: 'warning' },
  { id: 'tl-008', timestamp: 46, category: 'compliance', label: 'Unsourced ROI claim',          finding_id: 'f-008', severity: 'warning' },
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
      timestamp: 43,
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
      timestamp: 29,
      follow_up: 'M2 MacBook Pro: 87s for a 5-min video. M1: ~2min. Windows with CUDA: ~45s.',
    },
    {
      id: 'q-004', persona: 'Procurement Manager', difficulty: 'critical',
      question: "What's the all-in cost over three years, and do you have a reference customer with measurable ROI?",
      follow_up: 'Annual per-seat SaaS with no implementation fee. Design partners report 18% lift in first-call conversion and 40% fewer manager coaching hours. Happy to connect you with two reference customers.',
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
    title: 'Clear value proposition established',
    detail: 'The opening statement clearly establishes PitchPilot as an on-device AI sales coach for InstaLILY sales reps. The privacy angle is immediately clear.',
    timestamp: 4, live: true,
  },
  {
    id: 'lf-002', agent: 'compliance', severity: 'warning',
    title: 'Integration claim lacks technical detail',
    detail: "The claim about 'seamless integration' with SAP and Oracle is vague. Ops managers will immediately ask for specifics about data mapping, transformation, timeline, and cost.",
    suggestion: 'Prepare detailed answers about ETL processes, data mapping, and integration timelines before making this claim.',
    timestamp: 11, live: true, cue_hint: 'integration detail needed',
  },
  {
    id: 'lf-003', agent: 'persona', severity: 'critical',
    title: 'Ops Manager: integration question incoming',
    detail: 'An ops manager will challenge the SAP/Oracle integration claim. They need specifics on data mapping, transformation processes, timeline, and cost.',
    suggestion: 'Be ready with: phased integration strategy, ETL tool details, 6-8 week pilot timeline, $15K-$30K cost estimate.',
    timestamp: 15, persona: 'ops_manager', live: true, cue_hint: 'integration question likely',
  },
  {
    id: 'lf-004', agent: 'persona', severity: 'critical',
    title: 'Investor: ROI guarantee needs quantification',
    detail: "An investor will challenge the ROI guarantee. They need to know what 'ROI' means quantitatively and see case studies demonstrating consistent achievement.",
    suggestion: 'Prepare: define ROI as 15-20% increase in close rates, reference beta testing data, offer to share case studies post-demo.',
    timestamp: 20, persona: 'investor', live: true, cue_hint: 'ROI question incoming',
  },
  {
    id: 'lf-005', agent: 'coach', severity: 'info',
    title: 'Real-time processing claim is strong',
    detail: "The claim about 'no latency' real-time processing is compelling and differentiates PitchPilot from batch-processing alternatives.",
    timestamp: 23, live: true,
  },
  {
    id: 'lf-006', agent: 'persona', severity: 'critical',
    title: 'CTO: technical architecture question incoming',
    detail: "The 'only company' claim will prompt a CTO to immediately probe the on-device ML architecture and how continuous sales data collection is handled from a privacy standpoint.",
    suggestion: 'Prepare: FunctionGemma architecture details, federated learning approach, encryption (in transit and at rest), data anonymization policy, opt-out controls.',
    timestamp: 31, persona: 'cto', live: true, cue_hint: 'technical deep dive likely',
  },
  {
    id: 'lf-007', agent: 'coach', severity: 'warning',
    title: '40% deal closure claim needs context',
    detail: "The '40% more enterprise deals' claim is bold but lacks context about baseline metrics, deal size, sales cycle duration, and customer acquisition costs.",
    suggestion: "Add context: 'Based on simulations and beta testing with InstaLILY's typical sales cycle and deal size.'",
    timestamp: 47, live: true,
  },
];

export const MOCK_LIVE_INROOM_REPORT: ReadinessReport = {
  session_id: 'live-inroom-mock',
  session_mode: 'live_in_room',
  session_duration_seconds: 48,
  live_cues_count: 3,
  live_session_summary:
    "0:48 live in-room session. 3 earpiece cues delivered in real time. Three interruptions surfaced from ops_manager, investor, and CTO personas. Integration vagueness and unquantified ROI are the highest-risk items going into the real demo.",
  summary:
    "## Readiness Score: 6/10\n\n## \u2705 What\u2019s Working\n*   **Clear Value Proposition:** The core benefit \u2013 increased deal closure rates \u2013 \"InstaLILY sales reps will close 40% more enterprise deals\" \u2013 is immediately understandable and impactful.\n*   **Unique Differentiation:** The emphasis on \"on-device AI sales coaching\" and \u201cdomain-trained\u201d sets PitchPilot apart from generic AI solutions and highlights a key technical advantage.\n*   **Specific ROI Claim:** Guaranteeing ROI within 90 days, paired with a concrete percentage, provides a tangible target for the customer.\n\n\n## \u26a0\ufe0f Weak Points\n*   **Data Integration Vagueness:** The pitch glosses over the complexities of SAP and Oracle integration, which is a significant hurdle for large enterprises. \u201cSeamless integration\u201d lacks detail and appears to overpromise.\n*   **Quantified ROI Ambiguity:** \u201cGuaranteeing ROI\u201d and the 40% deal closure rate feels speculative without deeper context around InstaLILY\u2019s typical sales cycle, average deal size, and customer acquisition costs.\n*   **Technical Detail Shortfall:** The mention of FunctionGemma and its performance improvement is impressive but requires further explanation to establish credibility, especially regarding the privacy concerns.\n\n\n## \u2753 Objections You Must Prepare For\n*   **[OPS_MANAGER]:** \u201cThat\u2019s a bold claim \u2013 can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what\u2019s the estimated timeline and cost for that integration?\u201d\n*   **[INVESTOR]:** \u201cGuaranteeing ROI is a bold claim \u2013 can you quantify what \u2018ROI\u2019 actually means for a typical InstaLILY customer and demonstrate how you\u2019ve achieved this consistently across at least three separate case studies?\u201d\n*   **[CTO]:** That\u2019s a bold claim. Can you detail the specific on-device machine learning model architecture you\u2019re utilizing, and how you\u2019ve addressed potential privacy concerns related to continuous sales data collection?\n\n\n## \ud83c\udfaf Top 3 Things To Fix Before The Real Demo\n1.  **Develop a Detailed Integration Case Study:** Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.\n2.  **Quantify InstaLILY\u2019s ROI:**  Replace the blanket \u201c40%\u201d claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.\n3.  **Prepare a Privacy FAQ:** Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures.",
  created_at: new Date().toISOString(),
  claims: [
    { id: 'c-001', text: 'Good morning, we are presenting PitchPilot, an on-device AI sales coach for InstaLILY sales reps.', claim_type: 'feature', timestamp: 2, source: 'transcript', confidence: 0.98 },
    { id: 'c-002', text: 'PitchPilot runs locally on your laptop because your sales playbook and pricing strategy cannot leave the device.', claim_type: 'privacy', timestamp: 6, source: 'transcript', confidence: 0.95 },
    { id: 'c-003', text: 'Our system integrates seamlessly with your existing CRM and ERP workflows including SAP and Oracle.', claim_type: 'feature', timestamp: 11, source: 'transcript', confidence: 0.88 },
    { id: 'c-004', text: 'We guarantee ROI within 90 days for every InstaLILY customer.', claim_type: 'metric', timestamp: 17, source: 'transcript', confidence: 0.85 },
    { id: 'c-005', text: 'Our on-device model processes sales conversations in real time with no latency.', claim_type: 'feature', timestamp: 23, source: 'transcript', confidence: 0.90 },
    { id: 'c-006', text: 'We are the only company building domain-trained on-device sales coaching for distribution verticals.', claim_type: 'comparison', timestamp: 28, source: 'transcript', confidence: 0.82 },
    { id: 'c-007', text: 'Our finetuned FunctionGemma model outperforms base Gemma on enterprise sales objection detection.', claim_type: 'feature', timestamp: 37, source: 'transcript', confidence: 0.91 },
    { id: 'c-008', text: 'InstaLILY sales reps using PitchPilot will close 40% more enterprise deals.', claim_type: 'metric', timestamp: 47, source: 'transcript', confidence: 0.87 },
  ],

  score: {
    overall: 72,
    dimensions: [
      { dimension: 'Clarity',        score: 75, rationale: 'Structure and flow are solid but integration and ROI claims need more detail.' },
      { dimension: 'Compliance',     score: 70, rationale: 'Privacy and on-device claims are strong but need technical clarification for CTO-level audiences.' },
      { dimension: 'Defensibility',  score: 65, rationale: 'ROI guarantee and 40% deal closure claims need quantified context and case study support.' },
      { dimension: 'Persuasiveness', score: 78, rationale: 'Clear value proposition and unique differentiation are strong, but integration vagueness weakens credibility.' },
    ],
    priority_fixes: [
      'Develop a Detailed Integration Case Study: Create a concise, one-page document outlining the proposed SAP/Oracle integration process, including data mapping, transformation steps, and timeline.',
      "Quantify InstaLILY's ROI: Replace the blanket \"40%\" claim with a more targeted ROI projection based on typical InstaLILY sales metrics. Provide a range and clearly define the assumptions.",
      'Prepare a Privacy FAQ: Draft a short FAQ addressing potential privacy concerns regarding data collection and model usage, demonstrating transparency and proactive measures.',
    ],
  },

  findings: LIVE_INROOM_FINDINGS,

  persona_questions: [
    {
      id: 'lq-001', persona: 'ops_manager', difficulty: 'critical', timestamp: 15,
      question: "\u201cThat\u2019s a bold claim \u2013 can you specifically detail the data mapping and transformation processes required to ensure accurate, real-time synchronization between this system and *both* SAP and Oracle, and what\u2019s the estimated timeline and cost for that integration?\u201d",
      follow_up: "Absolutely. We recognize that data integration is critical. Our team is already developing a phased integration strategy, starting with prioritized data fields \u2013 specifically order history, customer contacts, and pricing. We use a robust ETL process utilizing Fivetran to map and transform data. We estimate a 6-8 week initial integration for a pilot group, with a cost of $15,000\u2013$30,000 for development and configuration.",
    },
    {
      id: 'lq-002', persona: 'investor', difficulty: 'critical', timestamp: 20,
      question: "\u201cGuaranteeing ROI is a bold claim \u2013 can you quantify what \u2018ROI\u2019 actually means for a typical InstaLILY customer and demonstrate how you\u2019ve achieved this consistently across at least three separate case studies?\u201d",
      follow_up: "You're right to challenge that. For a typical InstaLILY customer, ROI translates to an average of a 15-20% increase in close rates, based on our simulations and early beta testing. We're currently compiling three detailed case studies with pilot customers that demonstrate this.",
    },
    {
      id: 'lq-003', persona: 'cto', difficulty: 'critical', timestamp: 31,
      question: "That\u2019s a bold claim. Can you detail the specific on-device machine learning model architecture you\u2019re utilizing, and how you\u2019ve addressed potential privacy concerns related to continuous sales data collection?",
      follow_up: "Our model is based on a FunctionGemma architecture, significantly finetuned for enterprise sales objection detection. We employ a federated learning approach where model updates are generated locally on each rep's laptop. All data is encrypted both in transit and at rest, and we operate under a strict data anonymization policy.",
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
    detail: 'The opening seconds established clear stakes and framed the problem memorably. Screen share was smooth from the start.',
    timestamp: 2, live: true,
  },
  {
    id: 'rf-002', agent: 'compliance', severity: 'critical',
    title: "'Fully automated' conflicts with policy §3.2 (slide 2)",
    detail: "Slide 2 and transcript both claim 'fully automated — no manual review.' Policy §3.2 mandates human review above a 0.95 confidence threshold.",
    suggestion: "Rephrase to: 'Automated with optional human-in-the-loop review for high-stakes decisions.'",
    timestamp: 5, live: true, cue_hint: 'compliance risk', policy_reference: 'Enterprise Data Policy §3.2',
  },
  {
    id: 'rf-003', agent: 'coach', severity: 'warning',
    title: 'Slide 3 overloaded with technical jargon',
    detail: "Slide 3 uses 'multi-agent orchestration', 'LoRA fine-tuning', and 'tokenised function dispatch' in the same bullet list.",
    suggestion: "Lead with the outcome ('analyzes your pitch in 90 seconds') before explaining the mechanism.",
    timestamp: 14, live: true, cue_hint: 'simplify slide',
  },
  {
    id: 'rf-004', agent: 'compliance', severity: 'warning',
    title: "'Nothing leaves your network' needs qualification (slide 4)",
    detail: 'Privacy claim on slide 4 conflicts with the optional cloud-sync icon on the architecture slide.',
    suggestion: "Add 'by default' and note the opt-in cloud sync.",
    timestamp: 22, live: true, cue_hint: 'mention privacy',
  },
  {
    id: 'rf-005', agent: 'persona', severity: 'info',
    title: 'Technical Reviewer: model specificity is credible',
    detail: 'The Technical Reviewer persona found mention of Gemma 3n, FunctionGemma, and LoRA fine-tuning reassuring and technically credible.',
    timestamp: 29, persona: 'technical_reviewer', live: true,
  },
  {
    id: 'rf-006', agent: 'coach', severity: 'critical',
    title: 'Speed metric lacks benchmark context (slide 6)',
    detail: "'3× faster' is compelling but the baseline is unstated. Technical reviewers on the call will immediately ask '3× vs. what?'",
    suggestion: 'Name the competitor and link to a reproducible benchmark.',
    timestamp: 28, live: true, cue_hint: 'name benchmark',
  },
  {
    id: 'rf-007', agent: 'persona', severity: 'warning',
    title: 'Skeptical Investor: ChatGPT differentiation question incoming',
    detail: 'The presentation has not yet explained why on-device matters vs. a compliance-aware GPT-4o wrapper.',
    suggestion: "Prepare: 'ChatGPT requires sending your pitch to the cloud and has no sales-specific fine-tuning.'",
    timestamp: 33, persona: 'skeptical_investor', live: true, cue_hint: 'ChatGPT pushback likely',
  },
  {
    id: 'rf-008', agent: 'coach', severity: 'warning',
    title: 'Abrupt transition slide 6 → 7',
    detail: 'The jump from the live demo to the business model slide felt unanchored. No bridging sentence to orient the remote audience.',
    suggestion: "Add: 'What you just saw is the core product. Here's how we monetize it.'",
    timestamp: 40, live: true, cue_hint: 'add bridge',
  },
  {
    id: 'rf-009', agent: 'compliance', severity: 'warning',
    title: '99.9% uptime SLA not reflected in standard contract (slide 4)',
    detail: 'Standard tier is 99.5%. Promising 99.9% on-screen without qualification creates potential contractual liability.',
    suggestion: "Add 'premium tier only' or 'up to 99.9%' footnote on slide 4.",
    timestamp: 44, live: true, cue_hint: 'add footnote',
  },
  {
    id: 'rf-010', agent: 'persona', severity: 'warning',
    title: 'Procurement Manager: TCO and integration path not addressed',
    detail: 'Nearing the end and no mention of three-year cost or CRM integrations. Procurement will block sign-off without this.',
    suggestion: 'Add a slide covering per-seat pricing, implementation timeline, and Salesforce/Gong integrations.',
    timestamp: 47, persona: 'procurement_manager', live: true, cue_hint: 'address TCO',
  },
  {
    id: 'rf-011', agent: 'compliance', severity: 'info',
    title: 'Deployment time claim should cite conditions',
    detail: "'Under one hour' is plausible for single-user SaaS but enterprise on-device rollout typically requires IT approval cycles.",
    suggestion: "Add 'for standard single-user deployment' to the one-hour claim.",
    timestamp: 36, live: true,
  },
];

export const MOCK_LIVE_REMOTE_REPORT: ReadinessReport = {
  session_id: 'live-remote-mock',
  session_mode: 'live_remote',
  session_duration_seconds: 48,
  live_cues_count: 8,
  live_session_summary:
    "0:48 live remote session (Zoom screen share, 8 slides detected). 8 overlay cue cards delivered during the presentation. Two critical issues surfaced: the 'fully automated' compliance conflict and the unanchored 3× speed claim.",
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
      id: 'rq-001', persona: 'Skeptical Investor', difficulty: 'critical', timestamp: 33,
      question: 'How is this different from a compliance-aware wrapper around GPT-4o?',
      follow_up: 'Three key differences: on-device privacy, multimodal analysis (slides + audio + video), and specialized Gemma models fine-tuned for pitch evaluation.',
    },
    {
      id: 'rq-002', persona: 'Skeptical Investor', difficulty: 'warning', timestamp: 28,
      question: "What does '3× faster' mean — 3× vs. which competitor, on which benchmark?",
    },
    {
      id: 'rq-003', persona: 'Procurement Manager', difficulty: 'critical', timestamp: 22,
      question: "What are the contract terms — minimum commitment, auto-renewal, and data portability on exit?",
      follow_up: "Annual commitment, 30-day cancellation notice. Full JSON data export available at any time. No lock-in.",
    },
    {
      id: 'rq-004', persona: 'Procurement Manager', difficulty: 'warning', timestamp: 47,
      question: 'Can you provide a reference customer in our industry with a quantified ROI?',
    },
    {
      id: 'rq-005', persona: 'Technical Reviewer', difficulty: 'warning', timestamp: 14,
      question: 'What is the end-to-end latency from a slide change to an overlay cue appearing?',
      follow_up: 'OCR runs every 5 seconds on slide frames; overlay cards typically arrive within 8–12 seconds of a slide change.',
    },
  ],
};
