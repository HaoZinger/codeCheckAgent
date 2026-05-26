# Report generator: produces structured review reports
import os
import json
from datetime import datetime
from src.types import ReviewReport, RoundResult, Issue, CodeFile


def generate_report(report: ReviewReport, output_dir: str) -> str:
    """Generate the final review report and save fixed code. Returns report path."""
    os.makedirs(output_dir, exist_ok=True)

    # Save fixed code
    code_dir = os.path.join(output_dir, "fixed_code")
    os.makedirs(code_dir, exist_ok=True)
    for cf in report.fixed_code:
        safe_path = cf.path.replace("\\", "/").lstrip("/")
        full_path = os.path.join(code_dir, safe_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(cf.content)

    # Generate Markdown report
    md_path = os.path.join(output_dir, "review_report.md")
    md_content = _build_markdown_report(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Generate JSON report
    json_path = os.path.join(output_dir, "review_report.json")
    json_content = _build_json_report(report)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_content, f, indent=2, ensure_ascii=False)

    return md_path


def _build_markdown_report(report: ReviewReport) -> str:
    """Build a Markdown formatted review report."""
    lines = []
    lines.append("# CodeCheckAgent - Review Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Files | {report.total_files} |")
    lines.append(f"| Total Rounds | {report.total_rounds} |")
    lines.append(f"| Issues Found | {report.total_issues_found} |")
    lines.append(f"| Issues Fixed | {report.total_issues_fixed} |")
    lines.append(f"| Issues Remaining | {len(report.residual_issues)} |")
    lines.append(f"| Converged | {'✅ Yes' if report.converged else '⚠️ No'} |")
    lines.append("")

    if report.residual_issues:
        lines.append("## Residual Issues")
        lines.append("")
        for issue in report.residual_issues:
            sev_emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡", "info": "🔵"}.get(issue.severity, "⚪")
            lines.append(f"### {sev_emoji} [{issue.id}] {issue.title}")
            lines.append(f"- **File:** `{issue.file}` (lines {issue.line_start}-{issue.line_end})")
            lines.append(f"- **Severity:** {issue.severity}")
            lines.append(f"- **Category:** {issue.category}")
            lines.append(f"- **Status:** {issue.status}")
            lines.append(f"- **Description:** {issue.description}")
            lines.append(f"- **Suggestion:** {issue.suggestion}")
            lines.append("")

    lines.append("## Round Details")
    lines.append("")
    for r in report.rounds:
        lines.append(f"### Round {r.round_num}")
        lines.append(f"- Issues found: {r.issues_found}")
        lines.append(f"- Issues fixed: {r.issues_fixed}")
        lines.append(f"- Issues remaining: {r.issues_remaining}")
        lines.append("")

        if r.validation:
            lines.append(f"**Validator Summary:** {r.validation.summary}")
            lines.append("")
            lines.append("| Issue ID | Resolved | False Fix | Reason |")
            lines.append("|----------|----------|-----------|--------|")
            for v in r.validation.results:
                resolved = "✅" if v.resolved else "❌"
                false_fix = "⚠️ Yes" if v.false_fix else "No"
                reason = v.reason[:100] + ("..." if len(v.reason) > 100 else "")
                lines.append(f"| {v.issue_id} | {resolved} | {false_fix} | {reason} |")
            lines.append("")

        if r.patches:
            lines.append("<details>")
            lines.append("<summary>Patches (click to expand)</summary>")
            lines.append("")
            for p in r.patches:
                lines.append(f"**{p.issue_id}** (`{p.file}`)")
                lines.append("")
                lines.append("```diff")
                lines.append(p.diff)
                lines.append("```")
                lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines)


def _build_json_report(report: ReviewReport) -> dict:
    """Build a JSON structured report."""
    return {
        "generated_at": datetime.now().isoformat(),
        "total_files": report.total_files,
        "total_rounds": report.total_rounds,
        "total_issues_found": report.total_issues_found,
        "total_issues_fixed": report.total_issues_fixed,
        "converged": report.converged,
        "residual_issues": [
            {
                "id": i.id,
                "file": i.file,
                "line_start": i.line_start,
                "line_end": i.line_end,
                "severity": i.severity,
                "category": i.category,
                "title": i.title,
                "description": i.description,
                "suggestion": i.suggestion,
                "status": i.status,
            }
            for i in report.residual_issues
        ],
        "rounds": [
            {
                "round_num": r.round_num,
                "issues_found": r.issues_found,
                "issues_fixed": r.issues_fixed,
                "issues_remaining": r.issues_remaining,
                "validation_summary": r.validation.summary if r.validation else "",
                "validation_results": [
                    {
                        "issue_id": v.issue_id,
                        "resolved": v.resolved,
                        "false_fix": v.false_fix,
                        "reason": v.reason,
                    }
                    for v in (r.validation.results if r.validation else [])
                ],
                "patches": [
                    {"issue_id": p.issue_id, "file": p.file, "diff": p.diff}
                    for p in r.patches
                ],
            }
            for r in report.rounds
        ],
    }
