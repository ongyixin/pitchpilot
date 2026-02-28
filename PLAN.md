1. Project overview
Problem

Teams often rehearse pitches and demos without a reliable way to assess whether they are truly ready for a high-stakes audience. A presentation might sound polished, but still fail under scrutiny because:

claims are vague or unsupported

compliance-sensitive wording is risky

the demo flow is confusing or brittle

technical explanations do not hold up

likely audience objections are not anticipated

This is especially painful for startups, sales teams, and product teams working with confidential materials such as unreleased slides, internal product prototypes, product roadmaps, policy documents, and company strategy.

Solution

Build an on-device multimodal, multi-agent copilot that observes a locally rehearsed pitch or product demo, analyzes it from several perspectives, and answers the core question:

“Are we ready to demo under scrutiny?”

The system watches a rehearsal locally, extracts claims and demo flow, checks policy/compliance risk, simulates stakeholder questioning, and returns live coaching, a readiness report, and optionally annotated playback for review.

2. Design principle
Think system, not checklist

The value of the product is not in having isolated features like OCR, audience Q&A, compliance review, or coaching.

The value comes from how the components reinforce each other:

OCR gives the system access to slide text, policy docs, and visible UI

claim extraction turns observed content into something the agents can inspect

compliance review tests whether those claims are safe

persona agents test whether those claims are persuasive

technical review tests whether those claims are defensible

playback ties all of that feedback to specific moments in the rehearsal

This should feel like one integrated demo-readiness system, not a bundle of unrelated AI tricks.

3. Why on-device matters

This is one of the strongest parts of the concept.

On-device is important because:

presentations are confidential

demo builds may be unreleased

policy / compliance documents may be sensitive

spoken strategy and sales messaging should stay private

live rehearsal needs low latency

users are more willing to grant camera, mic, and screen access if data stays local

Judge-facing explanation

DemoSentinel runs on-device because it processes highly sensitive sales and product material — slides, spoken rehearsal, prototype UI, and internal policy documents — where privacy, responsiveness, and trust are essential.

4. Core product vision

DemoSentinel is a multi-agent local copilot that helps teams rehearse and stress-test their demo before they present it to investors, customers, internal leadership, or compliance reviewers.

It combines:

presentation coaching

claim extraction

OCR over documents and on-screen text

compliance / policy cross-checking

stakeholder persona simulation

optional product flow / UI walkthrough validation

annotated playback and post-hoc review

5. Main user story
Narrative

A user rehearses a pitch locally.

The system:

watches the user’s slides, screen, and spoken delivery

extracts claims, product flows, and visible documents

launches multiple specialist agents to investigate different dimensions

provides live coaching where helpful

generates a final readiness report

optionally records the session for annotated playback

Core question answered
Are we ready to demo this under scrutiny?
6. Main user workflows
A. Live Copilot Mode

Used during active rehearsal.

Inputs

screen share / slides

microphone

webcam

optional policy or sales materials

optional demo app / product walkthrough

Live outputs

pacing or clarity nudges

questions from audience personas

compliance warnings

reminders to support a claim

suggested follow-up points

Example

“You claimed this is fully automated — policy wording suggests exceptions.”

“This slide is dense; explain the value proposition first.”

“A technical reviewer may ask how this differs from rule-based automation.”

“Pause here — the product flow was unclear.”

B. Review Mode

Used after rehearsal.

Inputs

locally recorded rehearsal

transcript

extracted screen text / slide content

optional uploaded policy docs or product notes

Outputs

annotated playback timeline

comments grouped by agent

transcript-linked issues

readiness score by dimension

prioritized improvements

Why this mode is useful

Live feedback helps in the moment.
Playback helps the user reflect and improve deliberately.

7. Core system capabilities
1. Rehearsal observation

The system captures and processes:

visual input from slides / screen

audio from the speaker

optional webcam input

optional on-screen documents

2. Claim extraction

The system identifies:

product claims

value propositions

technical claims

compliance-sensitive statements

comparison claims

promises around automation, accuracy, privacy, safety, and workflow

3. OCR and document understanding

The system reads:

policy documents

pricing or feature slides

architecture diagrams

on-screen UI text

disclaimers and labels

4. Compliance / policy cross-checking

The system checks whether spoken or visual claims conflict with:

policy documents

approved messaging

required disclaimers

internal guardrails

5. Persona-based scrutiny

The system simulates likely questions and reactions from different stakeholders.

6. Readiness scoring

The system produces scores such as:

clarity

compliance safety

technical defensibility

stakeholder resilience

product demo robustness

7. Annotated playback

The system records the session locally and enables:

timestamped comments

category filters

transcript sync

per-agent review

8. Optional UI / product flow checking

This is a stretch feature. For hackathon scope, it is safer to frame this as:

validating visible demo flow coherence

checking a predefined flow against a script

or testing a sandbox / reference app rather than arbitrary third-party software

8. Multi-agent design
Agent 1: Presentation Coach
Role

Evaluate the structure and quality of the pitch.

Responsibilities

assess clarity and flow

detect rushed sections

identify narrative gaps

suggest slide-level improvements

flag jargon overload

Example outputs

“You introduced the solution before clearly stating the problem.”

“Your differentiation is still unclear.”

“The transition into the demo felt abrupt.”

Agent 2: Compliance Reviewer
Role

Cross-check claims and visuals against policy or approved messaging.

Responsibilities

OCR documents

extract relevant policy clauses

compare spoken claims against rules

flag missing disclaimers or risky wording

detect overstatements

Example outputs

“You said instant approval, but policy requires manual review in edge cases.”

“This feature claim may require additional qualification.”

“Consider adding a disclaimer on data retention.”

Agent 3: Technical Reviewer
Role

Pressure-test technical soundness.

Responsibilities

inspect technical claims made during the pitch

identify unsupported implementation claims

flag hand-wavy architecture explanations

ask likely engineering questions

Example outputs

“You described this as autonomous, but your explanation sounds workflow-based.”

“You claim on-device inference — be prepared to explain model deployment.”

“A reviewer may ask what runs locally versus what is cached.”

Agent 4: Audience Persona Simulator
Role

Simulate different types of stakeholders.

Suggested personas

skeptical investor

technical reviewer

friendly customer

compliance officer

confused first-time user

Responsibilities

ask questions mid-pitch or after sections

surface likely objections

rate how persuasive the presentation is from their viewpoint

Example outputs

“How is this different from existing sales enablement tools?”

“What’s the ROI for a customer?”

“Why must this run on-device?”

Agent 5: Demo / Flow Verifier
Role

Evaluate whether the demo flow is understandable and defensible.

Responsibilities

detect when the visible UI state is confusing

identify broken narrative in the click-through

optionally test predefined flows or use a reference app

Scope note

This is best treated as MVP+ or stretch, unless the team deliberately narrows the demo environment.

Agent 6: Delivery Signals Agent
Role

Provide lightweight delivery feedback.

Responsibilities

detect pacing issues

identify hesitation or filler words

mark moments of stress or uncertainty

optionally use webcam cues conservatively

Positioning

This is where “emotion detection” belongs. It should be framed as lightweight delivery support, not as the central value proposition.

9. Unified workflow
Step 1: Session setup

User selects:

Live Copilot or Review Mode

policy documents to load

target personas to simulate

optional demo script / talking points

optional reference materials for personalization or fine-tuning

Step 2: Rehearsal capture

System locally records:

audio

screen / slides

optional webcam

optional documents shown during session

Step 3: Multimodal understanding

System performs:

transcript generation

OCR on slides and documents

segment detection across sections of the talk

claim extraction

visible product flow analysis

Step 4: Multi-agent investigation

Agents analyze in parallel:

coach agent reviews structure

compliance agent checks risky claims

technical reviewer inspects defensibility

persona agents generate questions

delivery agent scores confidence and pacing

optional flow verifier checks demo coherence

Step 5: Live interventions

If live mode is enabled, system can:

interrupt at designated checkpoints

ask a question

display a warning

speak a quick prompt

suggest a revision after a section

Step 6: Final readiness output

System generates:

readiness score

summary of major issues

priority fixes

stakeholder questions to prepare for

transcript-linked comments

optional voice summary

Step 7: Annotated playback

If recording mode is enabled:

user replays the session locally

sees timeline markers by category

filters comments by agent

reviews transcript and screenshots

10. Recommended tech stack

This section should be one of the strongest parts of the plan, because the project is especially well matched to the Google DeepMind / Gemma ecosystem.

A. Core model stack
Gemma 3n — primary on-device reasoning model

Use Gemma 3n as the main local reasoning engine for DemoSentinel. Google describes Gemma 3n as designed for efficient execution on low-resource devices, with multimodal input support across text, image, video, and audio, making it the best fit for a rehearsal copilot that watches slides, listens to spoken delivery, and reasons over screen content locally.

FunctionGemma — tool calling and agent orchestration

Use FunctionGemma 270M as the lightweight function-calling planner. Google’s Hugging Face model card positions it as a specialized open model for function calling and explicitly says it is designed as a foundation for creating specialized function-calling models, with further fine-tuning expected. That makes it a strong fit for routing actions like:

start / stop recording

fetch relevant policy excerpts

generate persona questions

tag timestamps

create report sections

trigger playback filters

PaliGemma 2 — OCR and vision specialist

Use PaliGemma 2 for vision-heavy sub-tasks such as:

reading slide text

OCR over policy screenshots or on-screen documents

object / region grounding on UI screens

segmentation or detection when precise visual localization is needed

Google’s PaliGemma 2 model card describes it as a vision-language model designed for strong fine-tune transfer on text reading, object detection, and object segmentation, and PaliGemma prompting docs explicitly support OCR, detection, and segmentation task syntax. Google’s Gemma vision docs also note that for precise detection or segmentation, PaliGemma is often the more specialized choice than general Gemma image prompting.

Gemma 3 — optional higher-context reviewer

If the team runs the demo on a laptop rather than a phone-first target, Gemma 3 can optionally serve as a larger reviewer model for long-context aggregation, especially for multi-slide context, consolidated report drafting, and higher-level synthesis. Google documents Gemma 3 as supporting image + text input, 128K context, and function calling, though the smallest 270M and 1B variants are text-only.

B. Deployment stack
LiteRT / LiteRT-LM — on-device inference backbone

Use LiteRT and LiteRT-LM as the deployment story for local inference. Google describes LiteRT as its on-device framework for high-performance ML and GenAI deployment, and its GenAI overview emphasizes deployment across mobile, desktop, and web with CPU, GPU, and NPU acceleration. Google’s Gemma docs also distinguish LiteRT-LM as the lower-level, open-source framework for on-device LLM development with fine-grained control, while MediaPipe LLM Inference API is the higher-level integration path.

Recommended positioning

LiteRT-LM for the core on-device reasoning/runtime story

MediaPipe LLM Inference if you want a simpler demo integration path

local storage for recordings, transcripts, extracted OCR text, and timeline annotations

C. Fine-tuning strategy

Fine-tuning should be part of the plan, not just a passing mention.

Why fine-tune

Google’s Gemma tuning docs explicitly position fine-tuning as the way to improve performance for a specific task or domain, and official guides cover LoRA / QLoRA-based approaches, including Hugging Face-based workflows.

What to fine-tune on

Use lightweight adapters or focused fine-tunes on:

pitch decks

approved sales messaging

product strategy docs

compliance / policy language

likely objection / FAQ datasets

stakeholder persona examples

examples of good and bad rehearsal feedback

Best fine-tune targets

FunctionGemma for better tool routing, timestamp tagging, and report action generation

Gemma 3n for domain-adapted local reasoning over the team’s product and sales language

optionally PaliGemma 2 if you want better OCR / slide / UI understanding in a specific niche domain

Hackathon-friendly framing

We are not just running a generic local model. We are adapting the Gemma stack to the company’s own pitch materials, sales language, and compliance context so the feedback is private, domain-aware, and actually useful.

D. Development resources

The official implementation and experimentation resources line up well with this stack:

Gemma docs / model pages for model capabilities and platform guidance

Gemma Cookbook for examples and guides across Gemma workflows

Hugging Face Google model pages for Gemma-family model access and fine-tuning workflows

LiteRT-LM GitHub for lower-level on-device deployment control

11. Model-to-agent mapping

To make the system feel coherent, map each model to a clear role.

Gemma 3n

presentation coach

technical reviewer

readiness summarizer

delivery-support reasoning over transcript + screen + audio

FunctionGemma

function calling

tool routing

timeline tagging

report action generation

invoking persona agents or playback filters

PaliGemma 2

OCR

reading slides and policy screenshots

visual grounding on UI

detection / segmentation when the system needs to point to a specific visual element

LiteRT / LiteRT-LM

actual on-device execution path

efficient local inference

privacy-preserving deployment story

12. Product outputs
A. Live feedback

brief text prompts

optional voice nudges

checkpoint questions from personas

highlighted risky statements

B. Final readiness report

Suggested report sections:

overall readiness score

clarity and narrative

compliance and messaging risk

technical defensibility

audience objections

demo flow issues

next fixes to make before presentation

C. Annotated timeline

Timeline markers such as:

red = compliance issue

blue = technical issue

yellow = presentation clarity

purple = audience question

orange = delivery / pacing signal

D. Suggested revisions

The system can produce:

better wording for risky claims

likely FAQ answers

extra backup-slide prompts

suggested talk-track edits

13. MVP scope
Must-have

local rehearsal capture

transcript + OCR extraction

presentation coach agent

compliance reviewer agent

2–3 audience personas

final readiness report

recording + timestamped annotations

Nice-to-have

voice output

richer playback UI

technical reviewer agent

section-by-section scoring

Stretch

automatic UI testing

screen-state-based demo validation

live interruption by persona agents

delivery signal analysis from webcam

suggested rewritten slides

14. Recommended demo strategy

The cleanest demo is a meta demo:
you rehearse your own pitch once, then feed that recording back into DemoSentinel.

Demo flow

show a short rehearsal recording

system processes it locally

reveal multi-agent findings

show annotated playback

click into one compliance issue, one persona question, and one clarity suggestion

end with readiness score and recommended fixes

This makes the system easy to understand and avoids overcommitting to full arbitrary E2E automation.

15. Success criteria

A successful prototype should demonstrate that the system can:

observe a local rehearsal

extract meaningful claims and presentation context

surface at least one compliance or wording issue

generate useful stakeholder questions

provide a coherent readiness summary

show timestamped feedback in playback mode

If those work well, the product story lands.