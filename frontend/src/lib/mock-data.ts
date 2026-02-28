import type { ReadinessReport, StatusResponse } from '@/types/api';

export const MOCK_STATUS_SEQUENCE: StatusResponse[] = [
  { session_id: 'demo-001', status: 'extracting_frames', progress: 8, current_step: 'Extracting video frames at 1 fps...' },
  { session_id: 'demo-001', status: 'transcribing', progress: 22, current_step: 'Transcribing audio via Gemma 3n...' },
  { session_id: 'demo-001', status: 'extracting_claims', progress: 38, current_step: 'Running OCR on slide frames...' },
  { session_id: 'demo-001', status: 'extracting_claims', progress: 52, current_step: 'Extracting claims from transcript...' },
  { session_id: 'demo-001', status: 'running_agents', progress: 65, current_step: 'FunctionGemma routing claims to agents...' },
  { session_id: 'demo-001', status: 'running_agents', progress: 75, current_step: 'Presentation Coach analyzing narrative flow...' },
  { session_id: 'demo-001', status: 'running_agents', progress: 84, current_step: 'Compliance Reviewer cross-checking claims...' },
  { session_id: 'demo-001', status: 'running_agents', progress: 91, current_step: 'Persona Simulator generating stakeholder questions...' },
  { session_id: 'demo-001', status: 'scoring', progress: 97, current_step: 'Aggregating readiness score...' },
  { session_id: 'demo-001', status: 'complete', progress: 100, current_step: 'Analysis complete.' },
];

export const MOCK_REPORT: ReadinessReport = {
  session_id: 'demo-001',
  overall_score: 72,
  grade: 'B',
  summary:
    'Your pitch has strong narrative momentum and clear problem framing. The main risks are an overreaching privacy claim on slide 4 and an abrupt transition from the demo to the business model. The skeptical investor persona surfaces the sharpest questions — prepare those answers before your next rehearsal.',
  agents_run: ['coach', 'compliance', 'persona'],

  dimensions: {
    clarity: {
      name: 'Clarity',
      score: 78,
      weight: 0.25,
      issues_count: 3,
      critical_count: 0,
      summary: 'Clear problem statement; solution slides are dense with jargon.',
    },
    compliance: {
      name: 'Compliance',
      score: 61,
      weight: 0.25,
      issues_count: 4,
      critical_count: 2,
      summary: 'Two claims directly conflict with policy doc. "Fully automated" and "fully private" need qualification.',
    },
    defensibility: {
      name: 'Defensibility',
      score: 74,
      weight: 0.25,
      issues_count: 2,
      critical_count: 0,
      summary: 'Investor persona questions are answerable but require better data. Technical objections are solid.',
    },
    persuasiveness: {
      name: 'Persuasiveness',
      score: 81,
      weight: 0.25,
      issues_count: 1,
      critical_count: 0,
      summary: 'Strong open and close. Demo transition at 3:42 is rough — tighten the segue.',
    },
  },

  priority_fixes: [
    'Qualify the "fully private" claim on slide 4: add "by default" or "when configured with on-device mode".',
    'Replace "fully automated" with "automated for standard cases, with optional manual review for edge cases" to align with policy §3.2.',
    'Add a one-sentence bridge between the live demo and the business model slide (currently jumps too abruptly at 3:42).',
    'Prepare a crisp ≤30-second answer to "How is this different from just using ChatGPT?"',
    'Add a retention metric or pilot customer quote to the traction slide to strengthen the skeptical investor case.',
  ],

  top_issues: [
    {
      id: 'f-001',
      agent: 'compliance',
      severity: 'critical',
      category: 'compliance',
      title: '"Fully private" conflicts with policy §4.1',
      description:
        'At 2:34 you stated the product is "fully private and never sends data to the cloud." Policy §4.1 requires disclosure of optional cloud fallback mode.',
      timestamp: 154,
      slide_ref: 'slide_4',
      claim_text: 'fully private and never sends data to the cloud',
      suggestion:
        'Change to: "Private by default — all processing runs on-device. An optional cloud mode is available for users who opt in."',
    },
    {
      id: 'f-002',
      agent: 'compliance',
      severity: 'critical',
      category: 'compliance',
      title: '"Fully automated" conflicts with policy §3.2',
      description:
        'At 4:11 you claimed the workflow is "fully automated." Policy §3.2 mandates that edge cases require manual human review.',
      timestamp: 251,
      slide_ref: 'slide_6',
      claim_text: 'the entire workflow is fully automated',
      suggestion: 'Replace with: "Automated for 95% of standard cases; edge cases are flagged for manual review per our policy."',
    },
    {
      id: 'f-003',
      agent: 'coach',
      severity: 'warning',
      category: 'structure',
      title: 'Abrupt demo-to-business-model transition at 3:42',
      description:
        'The transition from the live demo to the business model is jarring. There is no bridging sentence, causing the audience to mentally context-switch without framing.',
      timestamp: 222,
      suggestion: 'Add: "What you just saw is the core product. Here\'s how we monetize it." before advancing the slide.',
    },
    {
      id: 'f-004',
      agent: 'coach',
      severity: 'warning',
      category: 'clarity',
      title: 'Solution slide overloaded with technical jargon',
      description:
        'Slide 3 uses "multi-agent orchestration," "LoRA fine-tuning," and "tokenized function dispatch" without explanation. Non-technical audiences will disengage.',
      timestamp: 118,
      slide_ref: 'slide_3',
      suggestion: 'Lead with the outcome ("analyzes your pitch in 90 seconds") before explaining the mechanism.',
    },
    {
      id: 'f-005',
      agent: 'coach',
      severity: 'info',
      category: 'clarity',
      title: 'Strong problem statement — preserve this opening',
      description:
        'Your first 45 seconds are excellent. The "pitch rehearsal is a black box" hook is memorable and clearly frames the gap.',
      timestamp: 12,
    },
    {
      id: 'f-006',
      agent: 'persona',
      severity: 'warning',
      category: 'persona_question',
      title: 'Skeptical Investor: "Why not just use ChatGPT?"',
      description:
        'Persona: Skeptical Investor. This question arose from your generic AI differentiation framing on the traction slide.',
      timestamp: 298,
      persona: 'skeptical_investor',
      suggestion:
        'Prepare: "ChatGPT requires sending your pitch to the cloud and has no sales-specific training. PitchPilot runs on-device, uses specialized models for each evaluation task, and integrates with your timeline."',
    },
    {
      id: 'f-007',
      agent: 'persona',
      severity: 'info',
      category: 'persona_question',
      title: 'Technical Reviewer: On-device inference latency?',
      description:
        'Persona: Technical Reviewer. Wants specifics on inference latency for the 90-second claim.',
      timestamp: 198,
      persona: 'technical_reviewer',
      suggestion: 'Have concrete benchmarks ready: "On an M2 MacBook Pro: 90s for a 5-minute video, 4.2s/frame OCR, real-time audio."',
    },
    {
      id: 'f-008',
      agent: 'compliance',
      severity: 'warning',
      category: 'risk',
      title: 'ROI claim lacks supporting data',
      description: 'At 5:20 you claimed "3x close rate improvement" without citing a source or pilot data.',
      timestamp: 320,
      slide_ref: 'slide_8',
      claim_text: '3x close rate improvement',
      suggestion: 'Add source: cite pilot customer or qualify as "hypothesis to be validated in pilot."',
    },
  ],

  findings: [],

  stakeholder_questions: [
    {
      id: 'q-001',
      persona: 'Skeptical Investor',
      question: 'How is this meaningfully different from asking ChatGPT to review my pitch script?',
      difficulty: 'hard',
      category: 'differentiation',
      timestamp: 298,
      suggested_answer:
        'Three key differences: on-device privacy (no data leaves the machine), multimodal analysis (video + slides + audio, not just text), and specialized models fine-tuned for pitch evaluation rather than general conversation.',
    },
    {
      id: 'q-002',
      persona: 'Skeptical Investor',
      question: 'What is your go-to-market strategy and why will enterprise sales teams adopt this?',
      difficulty: 'medium',
      category: 'business_model',
      suggested_answer: 'Focus on compliance-sensitive industries (fintech, healthcare) where on-device is a requirement, not a feature.',
    },
    {
      id: 'q-003',
      persona: 'Technical Reviewer',
      question: 'What is the actual end-to-end latency on consumer hardware? Have you measured it?',
      difficulty: 'medium',
      category: 'performance',
      timestamp: 198,
      suggested_answer: 'M2 MacBook Pro: 87s for a 5-min video. M1: ~2min. Windows with CUDA: ~45s.',
    },
    {
      id: 'q-004',
      persona: 'Compliance Officer',
      question: 'How do you ensure the AI\'s compliance assessments are not themselves a compliance liability?',
      difficulty: 'hard',
      category: 'compliance',
      suggested_answer:
        'The tool surfaces potential issues for human review — it does not make compliance determinations. All outputs are framed as "suggested review items."',
    },
    {
      id: 'q-005',
      persona: 'Technical Reviewer',
      question: 'Why FunctionGemma for routing instead of a simpler classifier?',
      difficulty: 'easy',
      category: 'architecture',
      suggested_answer:
        'FunctionGemma was designed specifically for function dispatch with structured output. A classifier would require separate handling of argument extraction.',
    },
  ],

  timeline: [
    { timestamp: 12, category: 'clarity', color: 'blue', label: 'Strong hook', finding_id: 'f-005', agent: 'coach' },
    { timestamp: 118, category: 'clarity', color: 'yellow', label: 'Jargon overload on slide 3', finding_id: 'f-004', agent: 'coach' },
    { timestamp: 154, category: 'compliance', color: 'red', label: '"Fully private" claim', finding_id: 'f-001', agent: 'compliance' },
    { timestamp: 198, category: 'persona_question', color: 'purple', label: 'Latency question', finding_id: 'f-007', agent: 'persona' },
    { timestamp: 222, category: 'structure', color: 'yellow', label: 'Demo transition gap', finding_id: 'f-003', agent: 'coach' },
    { timestamp: 251, category: 'compliance', color: 'red', label: '"Fully automated" claim', finding_id: 'f-002', agent: 'compliance' },
    { timestamp: 298, category: 'persona_question', color: 'purple', label: '"Why not ChatGPT?"', finding_id: 'f-006', agent: 'persona' },
    { timestamp: 320, category: 'risk', color: 'red', label: 'Unsourced ROI claim', finding_id: 'f-008', agent: 'compliance' },
  ],
};
