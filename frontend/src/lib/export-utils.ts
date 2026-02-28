/**
 * PitchPilot — Client-side export utilities.
 *
 * Provides JSON, CSV, and print-to-PDF export for ReadinessReport data.
 * All operations happen in the browser — no extra backend calls needed.
 */

import type { ReadinessReport, Finding } from '@/types/api';

// ---------------------------------------------------------------------------
// Shared download helper
// ---------------------------------------------------------------------------

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

function escapeCsvCell(value: string | number | undefined | null): string {
  const str = value == null ? '' : String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildCsvRow(cells: (string | number | undefined | null)[]): string {
  return cells.map(escapeCsvCell).join(',');
}

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

export function exportReportJSON(report: ReadinessReport, sessionId: string): void {
  const blob = new Blob([JSON.stringify(report, null, 2)], {
    type: 'application/json',
  });
  triggerDownload(blob, `pitchpilot-report-${sessionId}.json`);
}

// ---------------------------------------------------------------------------
// CSV export — five labelled sections in one file
// ---------------------------------------------------------------------------

export function exportReportCSV(report: ReadinessReport, sessionId: string): void {
  const lines: string[] = [];

  // ── Section 1: summary metadata ──────────────────────────────────────────
  lines.push('PITCHPILOT READINESS REPORT');
  lines.push(buildCsvRow(['Session ID', sessionId]));
  lines.push(buildCsvRow(['Score', report.score.overall]));
  lines.push(buildCsvRow(['Created', report.created_at]));
  lines.push('');

  // ── Section 2: dimension scores ──────────────────────────────────────────
  lines.push('DIMENSIONS');
  lines.push(buildCsvRow(['Dimension', 'Score', 'Rationale']));
  for (const dim of report.score.dimensions) {
    lines.push(buildCsvRow([dim.dimension, dim.score, dim.rationale]));
  }
  lines.push('');

  // ── Section 3: priority fixes ─────────────────────────────────────────────
  lines.push('PRIORITY FIXES');
  lines.push(buildCsvRow(['#', 'Action']));
  report.score.priority_fixes.forEach((fix, i) => {
    lines.push(buildCsvRow([i + 1, fix]));
  });
  lines.push('');

  // ── Section 4: findings ───────────────────────────────────────────────────
  lines.push('AGENT FINDINGS');
  lines.push(
    buildCsvRow(['ID', 'Agent', 'Severity', 'Title', 'Detail', 'Suggestion', 'Timestamp (s)', 'Policy Ref']),
  );
  for (const f of report.findings) {
    lines.push(
      buildCsvRow([
        f.id,
        f.agent,
        f.severity,
        f.title,
        f.detail,
        f.suggestion ?? '',
        f.timestamp ?? '',
        f.policy_reference ?? '',
      ]),
    );
  }
  lines.push('');

  // ── Section 5: stakeholder questions ─────────────────────────────────────
  lines.push('STAKEHOLDER QUESTIONS');
  lines.push(buildCsvRow(['ID', 'Persona', 'Difficulty', 'Question', 'Follow-up']));
  for (const q of report.persona_questions) {
    lines.push(
      buildCsvRow([q.id, q.persona, q.difficulty, q.question, q.follow_up ?? '']),
    );
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, `pitchpilot-report-${sessionId}.csv`);
}

// ---------------------------------------------------------------------------
// PDF export — opens a print-ready HTML page in a new tab
// ---------------------------------------------------------------------------

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warning:  '#f59e0b',
  info:     '#3b82f6',
};

const AGENT_COLOR: Record<string, string> = {
  compliance: '#ef4444',
  coach:      '#3b82f6',
  persona:    '#a855f7',
};

function scoreColor(score: number): string {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#f59e0b';
  return '#ef4444';
}

function computeGrade(score: number): string {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
}

function formatTs(seconds: number | undefined): string {
  if (seconds == null || seconds === 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function buildFindingCard(f: Finding): string {
  return `
    <div style="border:1.5px solid #e5e7eb;border-left:4px solid ${SEVERITY_COLOR[f.severity] ?? '#9ca3af'};padding:12px 14px;margin-bottom:10px;page-break-inside:avoid">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
        <span style="background:${AGENT_COLOR[f.agent] ?? '#9ca3af'};color:#fff;font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;text-transform:uppercase;letter-spacing:.05em">${f.agent}</span>
        <span style="background:${SEVERITY_COLOR[f.severity] ?? '#e5e7eb'};color:#fff;font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;text-transform:uppercase;letter-spacing:.05em">${f.severity}</span>
        ${f.timestamp ? `<span style="margin-left:auto;font-size:11px;color:#9ca3af">${formatTs(f.timestamp)}</span>` : ''}
      </div>
      <div style="font-weight:600;font-size:14px;margin-bottom:4px">${f.title}</div>
      <div style="font-size:13px;color:#374151;line-height:1.5;margin-bottom:${f.suggestion ? '8px' : '0'}">${f.detail}</div>
      ${f.suggestion ? `<div style="font-size:12px;color:#059669;background:#f0fdf4;padding:6px 10px;border-radius:4px;border-left:3px solid #059669">💡 ${f.suggestion}</div>` : ''}
      ${f.policy_reference ? `<div style="font-size:11px;color:#9ca3af;margin-top:6px">Policy ref: ${f.policy_reference}</div>` : ''}
    </div>`;
}

export function exportReportPDF(report: ReadinessReport, sessionId: string): void {
  const overall = report.score.overall;
  const grade = computeGrade(overall);
  const color = scoreColor(overall);

  const dimensionRows = report.score.dimensions
    .map(
      (d) => `
      <tr>
        <td style="padding:8px 12px;font-weight:600">${d.dimension}</td>
        <td style="padding:8px 12px;text-align:center">
          <span style="display:inline-block;background:${scoreColor(d.score)};color:#fff;padding:2px 8px;border-radius:4px;font-weight:700;font-size:13px">${d.score}</span>
        </td>
        <td style="padding:8px 12px;color:#6b7280;font-size:13px">${d.rationale}</td>
      </tr>`,
    )
    .join('');

  const priorityFixRows = report.score.priority_fixes
    .map(
      (fix, i) => `
      <li style="margin-bottom:10px;line-height:1.6">
        <span style="display:inline-block;background:#111;color:#fff;font-size:11px;font-weight:700;padding:1px 7px;border-radius:3px;margin-right:8px">${i + 1}</span>
        ${fix}
      </li>`,
    )
    .join('');

  const findingCards = report.findings.map(buildFindingCard).join('');

  const questionCards = report.persona_questions
    .map(
      (q) => `
      <div style="border:1.5px solid #e5e7eb;padding:12px 14px;margin-bottom:10px;page-break-inside:avoid">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="font-size:11px;font-weight:700;color:#a855f7;text-transform:uppercase;letter-spacing:.05em">${q.persona}</span>
          <span style="font-size:10px;color:${SEVERITY_COLOR[q.difficulty] ?? '#9ca3af'};font-weight:600;text-transform:uppercase;margin-left:auto">${q.difficulty}</span>
        </div>
        <div style="font-size:14px;font-weight:600;margin-bottom:${q.follow_up ? '8px' : '0'}">${q.question}</div>
        ${q.follow_up ? `<div style="font-size:12px;color:#6b7280;line-height:1.5;border-top:1px solid #f3f4f6;padding-top:8px;margin-top:4px"><em>${q.follow_up}</em></div>` : ''}
      </div>`,
    )
    .join('');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>PitchPilot Report — ${sessionId}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #fff;
      color: #111;
      padding: 40px;
      max-width: 900px;
      margin: 0 auto;
      font-size: 14px;
      line-height: 1.5;
    }
    @media print {
      body { padding: 20px; }
      .no-print { display: none !important; }
    }
    h2 { font-size: 18px; font-weight: 700; margin: 28px 0 12px; border-bottom: 2px solid #111; padding-bottom: 6px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    thead th {
      background: #f9fafb; text-align: left; padding: 8px 12px;
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; color: #6b7280; border-bottom: 2px solid #e5e7eb;
    }
    tbody tr:nth-child(even) { background: #f9fafb; }
    .print-btn {
      position: fixed; bottom: 24px; right: 24px;
      background: #111; color: #fff; border: none; cursor: pointer;
      padding: 10px 20px; font-size: 13px; font-weight: 700;
      text-transform: uppercase; letter-spacing: .05em; border-radius: 4px;
    }
    .print-btn:hover { background: #374151; }
  </style>
</head>
<body>

  <!-- Header -->
  <div style="display:flex;align-items:flex-end;justify-content:space-between;border-bottom:4px solid #111;padding-bottom:16px;margin-bottom:24px">
    <div>
      <div style="font-size:36px;font-weight:900;letter-spacing:.08em;line-height:1">PITCHPILOT</div>
      <div style="font-size:12px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">Readiness Report</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em">Session</div>
      <div style="font-family:monospace;font-size:13px;color:#374151">${sessionId}</div>
      <div style="font-size:11px;color:#9ca3af;margin-top:4px">${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</div>
    </div>
  </div>

  <!-- Score banner -->
  <div style="display:flex;gap:16px;margin-bottom:24px">
    <div style="border:3px solid #111;padding:16px 24px;display:flex;align-items:center;gap:16px;flex-shrink:0">
      <div>
        <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px">Readiness Score</div>
        <div style="font-size:52px;font-weight:900;line-height:1;color:${color}">${overall}</div>
        <div style="font-size:11px;color:#9ca3af">/100</div>
      </div>
      <div style="width:1px;height:60px;background:#e5e7eb"></div>
      <div>
        <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px">Grade</div>
        <div style="font-size:52px;font-weight:900;line-height:1;color:${color}">${grade}</div>
      </div>
    </div>
    <div style="flex:1;border:3px solid #111;padding:16px 20px">
      <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Executive Summary</div>
      <p style="font-size:13px;color:#374151;line-height:1.7">${report.summary}</p>
    </div>
  </div>

  <!-- Dimensions -->
  <h2>Dimension Scores</h2>
  <table>
    <thead><tr><th>Dimension</th><th>Score</th><th>Rationale</th></tr></thead>
    <tbody>${dimensionRows}</tbody>
  </table>

  <!-- Priority fixes -->
  <h2>Priority Fixes</h2>
  <ol style="padding-left:0;list-style:none;margin-bottom:8px">${priorityFixRows}</ol>

  <!-- Findings -->
  <h2>Agent Findings (${report.findings.length})</h2>
  ${findingCards || '<p style="color:#9ca3af;font-size:13px">No findings.</p>'}

  <!-- Stakeholder questions -->
  ${report.persona_questions.length > 0 ? `
  <h2>Stakeholder Questions (${report.persona_questions.length})</h2>
  ${questionCards}
  ` : ''}

  <button class="print-btn no-print" onclick="window.print()">Print / Save as PDF</button>

</body>
</html>`;

  const printWindow = window.open('', '_blank', 'width=1000,height=800');
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
  }
}
