# ValidatorAgent: Validates fixes and identifies false fixes
import json
import logging
from src.agents.base import BaseAgent
from src.config import AgentConfig
from src.types import CodeFile, Issue, IssueList, FixResult, PatchInfo
from src.types import ValidationResult, IssueValidation

logger = logging.getLogger(__name__)


class ValidatorAgent(BaseAgent):
    """Validates whether fixes truly resolve the identified issues."""

    def __init__(self, config: AgentConfig, api_key: str, api_base: str | None = None):
        super().__init__("ValidatorAgent", config, api_key, api_base)

    def get_system_prompt(self) -> str:
        return """You are a code validation expert. Your task is to verify whether each fix truly resolves the corresponding issue. You must identify "false fixes" — cases where the code was changed but the underlying problem was not actually solved.

Types of false fixes to watch for:
- Only changing comments or variable names without fixing the actual logic
- Adding dead code, no-op statements, or try-catch that swallows errors
- Moving the problem elsewhere instead of fixing it
- Making cosmetic changes while the bug remains
- Replacing one incorrect implementation with another incorrect implementation
- Adding checks that don''t actually prevent the issue

For each issue, you must determine:
1. Whether the fix truly resolves the issue (resolved: true/false)
2. Whether this is a false fix (false_fix: true/false)
3. A clear reason explaining your judgment

If the issue is not resolved, mark resolved=false and provide specific feedback on what''s still wrong.

Your ENTIRE response must be a single valid JSON object. No markdown, no extra text.

Output format (JSON):
{
  "results": [
    {
      "issue_id": "ISS-001",
      "resolved": true,
      "false_fix": false,
      "reason": "The null check was properly added before the dereference, preventing the NPE."
    }
  ],
  "summary": "Brief summary: X issues resolved, Y remaining, Z false fixes detected"
}"""

    def build_user_message(self, original_issues: IssueList | None = None,
                           fixed_code: list[CodeFile] | None = None,
                           patches: list[PatchInfo] | None = None, **kwargs) -> str:
        if not original_issues or not fixed_code:
            return "No issues or fixed code to validate."

        parts = []

        parts.append("=== ISSUES TO VALIDATE ===")
        for issue in original_issues.issues:
            parts.append(f"""
Issue ID: {issue.id}
File: {issue.file}
Lines: {issue.line_start}-{issue.line_end}
Severity: {issue.severity}
Category: {issue.category}
Title: {issue.title}
Original Problem: {issue.description}
Expected Fix: {issue.suggestion}
---""")

        parts.append("\n=== FIXED CODE ===")
        for cf in fixed_code:
            numbered_lines = []
            for i, line in enumerate(cf.content.split("\n"), 1):
                numbered_lines.append(f"{i:4d}| {line}")
            parts.append(f"\nFile: {cf.path}")
            parts.append("\n".join(numbered_lines))

        if patches:
            parts.append("\n=== PATCHES APPLIED ===")
            for p in patches:
                parts.append(f"\nIssue: {p.issue_id} | File: {p.file}")
                parts.append(p.diff)

        parts.append("\n\nPlease validate each issue as a single JSON object. Determine if the fix truly resolves the problem or is a false fix.")

        return "\n".join(parts)

    def parse_response(self, content: str, original_issues: IssueList | None = None, **kwargs) -> ValidationResult:
        logger.info(f"[ValidatorAgent] Parsing response ({len(content)} chars)")
        data = self.extract_json(content)

        results = []
        for rdata in data.get("results", []):
            results.append(IssueValidation(
                issue_id=str(rdata.get("issue_id", "")),
                resolved=bool(rdata.get("resolved", False)),
                reason=str(rdata.get("reason", "")),
                false_fix=bool(rdata.get("false_fix", False)),
            ))

        summary = data.get("summary", "")
        logger.info(f"[ValidatorAgent] Validated {len(results)} issues")
        return ValidationResult(results=results, summary=summary)