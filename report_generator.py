"""
Report Generator
Team Alpha — Task 6

Aggregates a list of Issues into a ScanReport and renders it as
JSON, HTML (via Jinja2), and Markdown.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from models import (
    Issue,
    ScanReport,
    ScanSummary,
    SeverityLevel,
    SEVERITY_SCORE,
)


# ─── Report builder ───────────────────────────────────────────────────────────

def build_report(
    issues: List[Issue],
    target_url: str,
    scan_name: str = "API Security Scan",
    total_endpoints: int = 0,
    total_requests: int = 0,
    scan_start: Optional[datetime] = None,
    scan_end: Optional[datetime] = None,
    metadata: Optional[Dict] = None,
) -> ScanReport:
    """Construct a ScanReport from a list of classified Issues."""
    scan_end = scan_end or datetime.utcnow()
    scan_start = scan_start or scan_end
    duration = (scan_end - scan_start).total_seconds()

    counts = {s: 0 for s in SeverityLevel}
    for issue in issues:
        counts[issue.severity] += 1

    summary = ScanSummary(
        total_endpoints=total_endpoints,
        total_requests=total_requests,
        total_issues=len(issues),
        critical_count=counts[SeverityLevel.CRITICAL],
        high_count=counts[SeverityLevel.HIGH],
        medium_count=counts[SeverityLevel.MEDIUM],
        low_count=counts[SeverityLevel.LOW],
        info_count=counts[SeverityLevel.INFO],
        duration_seconds=round(duration, 2),
        scan_start=scan_start,
        scan_end=scan_end,
    )

    # Sort issues by severity score descending
    sorted_issues = sorted(
        issues, key=lambda i: SEVERITY_SCORE.get(i.severity, 0), reverse=True
    )

    return ScanReport(
        report_id=str(uuid.uuid4()),
        target_url=target_url,
        scan_name=scan_name,
        summary=summary,
        issues=sorted_issues,
        metadata=metadata or {},
    )


# ─── JSON renderer ────────────────────────────────────────────────────────────

def _issue_to_dict(issue: Issue) -> dict:
    repro = None
    if issue.repro:
        repro = {
            "description":      issue.repro.description,
            "method":           issue.repro.request_method,
            "url":              issue.repro.request_url,
            "user_a_token":     issue.repro.user_a_token,
            "user_b_token":     issue.repro.user_b_token,
            "expected_status":  issue.repro.expected_status,
            "actual_status":    issue.repro.actual_status,
            "curl":             issue.repro.curl_command,
        }

    diff = issue.diff
    return {
        "issue_id":     issue.issue_id,
        "type":         issue.issue_type.value,
        "severity":     issue.severity.value,
        "title":        issue.title,
        "description":  issue.description,
        "endpoint":     issue.endpoint,
        "method":       issue.method,
        "cwe":          issue.cwe,
        "owasp":        issue.owasp,
        "recommendation": issue.recommendation,
        "discovered_at": issue.discovered_at.isoformat(),
        "evidence": {
            "body_similarity":   diff.body_similarity,
            "status_delta":      diff.status_delta,
            "leaked_fields":     diff.leaked_fields[:20],
            "foreign_ids_found": diff.foreign_ids_found[:10],
            "anomaly_reason":    diff.anomaly_reason,
            "user_a": {
                "user_id":    diff.response_a.user_id,
                "role":       diff.response_a.role,
                "status":     diff.response_a.status_code,
            },
            "user_b": {
                "user_id":    diff.response_b.user_id,
                "role":       diff.response_b.role,
                "status":     diff.response_b.status_code,
            },
        },
        "reproduction": repro,
    }


def generate_json(report: ScanReport, indent: int = 2) -> str:
    """Render ScanReport as a JSON string."""
    data = {
        "report_id":  report.report_id,
        "scan_name":  report.scan_name,
        "target_url": report.target_url,
        "created_at": report.created_at.isoformat(),
        "metadata":   report.metadata,
        "summary": {
            "total_endpoints":  report.summary.total_endpoints,
            "total_requests":   report.summary.total_requests,
            "total_issues":     report.summary.total_issues,
            "critical":         report.summary.critical_count,
            "high":             report.summary.high_count,
            "medium":           report.summary.medium_count,
            "low":              report.summary.low_count,
            "info":             report.summary.info_count,
            "duration_seconds": report.summary.duration_seconds,
            "scan_start":       report.summary.scan_start.isoformat() if report.summary.scan_start else None,
            "scan_end":         report.summary.scan_end.isoformat() if report.summary.scan_end else None,
        },
        "issues": [_issue_to_dict(i) for i in report.issues],
    }
    return json.dumps(data, indent=indent)


# ─── Markdown renderer ────────────────────────────────────────────────────────

_SEVERITY_EMOJI = {
    SeverityLevel.CRITICAL: "🔴",
    SeverityLevel.HIGH:     "🟠",
    SeverityLevel.MEDIUM:   "🟡",
    SeverityLevel.LOW:      "🔵",
    SeverityLevel.INFO:     "⚪",
}


def generate_markdown(report: ScanReport) -> str:
    s = report.summary
    lines = [
        f"# {report.scan_name}",
        f"",
        f"**Target:** `{report.target_url}`  ",
        f"**Report ID:** `{report.report_id}`  ",
        f"**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Duration:** {s.duration_seconds}s  ",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Endpoints Scanned | {s.total_endpoints} |",
        f"| Requests Made | {s.total_requests} |",
        f"| Total Issues | {s.total_issues} |",
        f"| 🔴 Critical | {s.critical_count} |",
        f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",
        f"| 🔵 Low | {s.low_count} |",
        f"",
        f"---",
        f"",
        f"## Findings",
        f"",
    ]

    if not report.issues:
        lines.append("_No issues found._")
        return "\n".join(lines)

    for idx, issue in enumerate(report.issues, 1):
        emoji = _SEVERITY_EMOJI.get(issue.severity, "⚪")
        diff = issue.diff
        lines += [
            f"### {idx}. {emoji} {issue.title}",
            f"",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Type** | `{issue.issue_type.value}` |",
            f"| **Severity** | `{issue.severity.value}` |",
            f"| **Endpoint** | `{issue.method} {issue.endpoint}` |",
            f"| **CWE** | {issue.cwe} |",
            f"| **OWASP** | {issue.owasp} |",
            f"",
            f"**Description:**  ",
            f"{issue.description}",
            f"",
            f"**Evidence:**",
            f"- Body similarity: `{diff.body_similarity:.0%}`",
            f"- Status: User A `{diff.response_a.status_code}` → User B `{diff.response_b.status_code}`",
        ]
        if diff.foreign_ids_found:
            lines.append(f"- Foreign IDs found: `{', '.join(diff.foreign_ids_found[:5])}`")
        if diff.anomaly_reason:
            lines.append(f"- Anomaly: {diff.anomaly_reason}")

        if issue.repro:
            lines += [
                f"",
                f"**Reproduction:**",
                f"```bash",
                f"{issue.repro.curl_command}",
                f"```",
            ]

        lines += [
            f"",
            f"**Recommendation:**  ",
            f"{issue.recommendation}",
            f"",
            f"---",
            f"",
        ]

    return "\n".join(lines)


# ─── HTML renderer ────────────────────────────────────────────────────────────

_SEVERITY_COLOR = {
    "CRITICAL": "#dc2626",
    "HIGH":     "#ea580c",
    "MEDIUM":   "#d97706",
    "LOW":      "#2563eb",
    "INFO":     "#6b7280",
}

_SEVERITY_BG = {
    "CRITICAL": "#fef2f2",
    "HIGH":     "#fff7ed",
    "MEDIUM":   "#fffbeb",
    "LOW":      "#eff6ff",
    "INFO":     "#f9fafb",
}


def generate_html(report: ScanReport) -> str:
    s = report.summary

    def badge(severity: str) -> str:
        color = _SEVERITY_COLOR.get(severity, "#6b7280")
        bg    = _SEVERITY_BG.get(severity, "#f9fafb")
        return (
            f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;">'
            f"{severity}</span>"
        )

    issues_html = ""
    for idx, issue in enumerate(report.issues, 1):
        diff = issue.diff
        curl = issue.repro.curl_command if issue.repro else "N/A"
        leaked = ", ".join(f"<code>{f}</code>" for f in diff.leaked_fields[:10]) or "—"
        foreign = ", ".join(f"<code>{i}</code>" for i in diff.foreign_ids_found[:5]) or "—"

        issues_html += f"""
        <div class="issue" id="issue-{idx}">
          <div class="issue-header">
            <span class="issue-num">#{idx}</span>
            {badge(issue.severity.value)}
            <span class="issue-type">{issue.issue_type.value}</span>
            <span class="issue-title">{issue.title}</span>
          </div>
          <div class="issue-body">
            <div class="grid2">
              <div><strong>Endpoint:</strong> <code>{issue.method} {issue.endpoint}</code></div>
              <div><strong>Discovered:</strong> {issue.discovered_at.strftime('%Y-%m-%d %H:%M UTC')}</div>
              <div><strong>CWE:</strong> {issue.cwe}</div>
              <div><strong>OWASP:</strong> {issue.owasp}</div>
            </div>
            <div class="section-label">Description</div>
            <p>{issue.description}</p>
            <div class="section-label">Evidence</div>
            <table class="evidence-table">
              <tr><td>Body Similarity</td><td><strong>{diff.body_similarity:.0%}</strong></td></tr>
              <tr><td>Status A → B</td><td><code>{diff.response_a.status_code}</code> → <code>{diff.response_b.status_code}</code></td></tr>
              <tr><td>User A</td><td>{diff.response_a.user_id} (role: {diff.response_a.role})</td></tr>
              <tr><td>User B</td><td>{diff.response_b.user_id} (role: {diff.response_b.role})</td></tr>
              <tr><td>Leaked Fields</td><td>{leaked}</td></tr>
              <tr><td>Foreign IDs</td><td>{foreign}</td></tr>
              <tr><td>Anomaly Reason</td><td>{diff.anomaly_reason or "—"}</td></tr>
            </table>
            <div class="section-label">Reproduction</div>
            <pre class="curl">{curl}</pre>
            <div class="section-label">Recommendation</div>
            <p class="recommendation">{issue.recommendation}</p>
          </div>
        </div>
        """

    no_issues = '<p style="color:#6b7280;font-style:italic;">No issues found.</p>' if not report.issues else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{report.scan_name} — Security Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f8fafc; color: #1e293b; line-height: 1.6; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .meta {{ color: #64748b; font-size: 13px; margin-bottom: 2rem; }}
    .meta span {{ margin-right: 1.5rem; }}

    /* Summary cards */
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 2rem; }}
    .summary-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; text-align: center; }}
    .summary-card .num {{ font-size: 28px; font-weight: 700; }}
    .summary-card .lbl {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .05em; }}

    /* Issues */
    .issue {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }}
    .issue-header {{ display: flex; align-items: center; gap: 10px; padding: 12px 16px;
                     border-bottom: 1px solid #f1f5f9; background: #f8fafc; flex-wrap: wrap; }}
    .issue-num {{ font-size: 13px; color: #94a3b8; font-weight: 600; }}
    .issue-type {{ font-size: 12px; color: #475569; font-family: monospace; }}
    .issue-title {{ font-size: 14px; font-weight: 600; flex: 1; min-width: 200px; }}
    .issue-body {{ padding: 16px; }}
    .section-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .07em;
                      color: #94a3b8; margin: 16px 0 6px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 13px; margin-bottom: 4px; }}
    @media(max-width: 560px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
    p {{ font-size: 13px; color: #475569; }}
    code {{ background: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-size: 12px; }}
    pre.curl {{ background: #0f172a; color: #e2e8f0; padding: 12px 16px; border-radius: 8px;
                font-size: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; margin-top: 4px; }}
    .evidence-table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }}
    .evidence-table td {{ padding: 5px 10px; border: 1px solid #f1f5f9; vertical-align: top; }}
    .evidence-table td:first-child {{ color: #64748b; white-space: nowrap; width: 160px; background: #f8fafc; font-weight: 500; }}
    .recommendation {{ background: #f0fdf4; border-left: 3px solid #22c55e; padding: 10px 14px;
                       border-radius: 0 6px 6px 0; font-size: 13px; color: #166534; margin-top: 4px; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0; }}
    .footer {{ text-align: center; font-size: 12px; color: #94a3b8; margin-top: 2rem; }}
  </style>
</head>
<body>
<div class="container">
  <h1>{report.scan_name}</h1>
  <div class="meta">
    <span>🎯 <strong>{report.target_url}</strong></span>
    <span>🕒 {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}</span>
    <span>⏱ {s.duration_seconds}s</span>
    <span>ID: <code>{report.report_id[:8]}…</code></span>
  </div>

  <div class="summary-grid">
    <div class="summary-card"><div class="num">{s.total_endpoints}</div><div class="lbl">Endpoints</div></div>
    <div class="summary-card"><div class="num">{s.total_requests}</div><div class="lbl">Requests</div></div>
    <div class="summary-card"><div class="num" style="color:#dc2626">{s.critical_count}</div><div class="lbl">Critical</div></div>
    <div class="summary-card"><div class="num" style="color:#ea580c">{s.high_count}</div><div class="lbl">High</div></div>
    <div class="summary-card"><div class="num" style="color:#d97706">{s.medium_count}</div><div class="lbl">Medium</div></div>
    <div class="summary-card"><div class="num" style="color:#2563eb">{s.low_count}</div><div class="lbl">Low</div></div>
  </div>

  <hr/>
  <h2 style="font-size:16px;font-weight:600;margin-bottom:1rem;">Findings ({s.total_issues})</h2>
  {no_issues}
  {issues_html}

  <div class="footer">Generated by Team Alpha Security Scanner &bull; Task 6 — Response Diff Engine</div>
</div>
</body>
</html>"""


# ─── Save to disk ─────────────────────────────────────────────────────────────

def save_report(
    report: ScanReport,
    output_dir: str = "./reports",
    formats: List[str] = ("json", "html", "md"),
) -> Dict[str, str]:
    """
    Write report files to disk.
    Returns a dict mapping format → file path.
    """
    ts = report.created_at.strftime("%Y%m%d_%H%M%S")
    folder = Path(output_dir) / f"scan_{ts}_{report.report_id[:8]}"
    folder.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, str] = {}

    if "json" in formats:
        p = folder / "report.json"
        p.write_text(generate_json(report), encoding="utf-8")
        paths["json"] = str(p)

    if "html" in formats:
        p = folder / "report.html"
        p.write_text(generate_html(report), encoding="utf-8")
        paths["html"] = str(p)

    if "md" in formats:
        p = folder / "report.md"
        p.write_text(generate_markdown(report), encoding="utf-8")
        paths["md"] = str(p)

    return paths
