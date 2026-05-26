# FixerAgent: Fixes issues identified by ReviewerAgent
import json
import logging
from src.agents.base import BaseAgent
from src.config import AgentConfig
from src.types import CodeFile, Issue, IssueList, FixResult, PatchInfo

logger = logging.getLogger(__name__)


class FixerAgent(BaseAgent):
    """Fixes code issues based on the Reviewer''s issue list."""

    def __init__(self, config: AgentConfig, api_key: str, api_base: str | None = None):
        super().__init__("FixerAgent", config, api_key, api_base)

    def get_system_prompt(self) -> str:
        return """You are an expert code fixer. Your task is to fix ONLY the issues identified by the code reviewer. You must NOT make any changes beyond what is necessary to fix the listed issues.

Rules:
1. ONLY fix issues that are explicitly listed in the issue list.
2. Do NOT refactor code, change formatting, or "improve" anything beyond the fixes.
3. For each fix, you must provide a unified diff showing exactly what changed.
4. Output the COMPLETE fixed file content for each modified file.
5. If an issue cannot be fixed (e.g., unclear suggestion), mark it as unfixable in the notes.
6. Preserve all existing code structure, comments, and formatting.
7. Your ENTIRE response must be a single valid JSON object. No markdown, no extra text.

Output format (JSON):
{
  "fixed_files": [
    {
      "path": "relative/file/path.py",
      "content": "complete fixed file content here"
    }
  ],
  "patches": [
    {
      "issue_id": "ISS-001",
      "file": "relative/file/path.py",
      "diff": "unified diff showing the change"
    }
  ],
  "unfixable": ["ISS-XXX if any"],
  "notes": "any notes about the fixes"
}"""

    def build_user_message(self, original_code: list[CodeFile] | None = None,
                           issues: IssueList | None = None, **kwargs) -> str:
        if not original_code or not issues:
            return "No code or issues to fix."

        parts = []

        parts.append("=== ORIGINAL CODE FILES ===")
        for cf in original_code:
            numbered_lines = []
            for i, line in enumerate(cf.content.split("\n"), 1):
                numbered_lines.append(f"{i:4d}| {line}")
            parts.append(f"\nFile: {cf.path} ({cf.language})")
            parts.append("\n".join(numbered_lines))

        parts.append("\n\n=== ISSUES TO FIX ===")
        for issue in issues.issues:
            parts.append(f"""
Issue ID: {issue.id}
File: {issue.file}
Lines: {issue.line_start}-{issue.line_end}
Severity: {issue.severity}
Category: {issue.category}
Title: {issue.title}
Description: {issue.description}
Suggestion: {issue.suggestion}
---""")

        parts.append("\nPlease fix ALL of the above issues. Output the complete fixed file(s) and the diff for each change as a single JSON object.")

        return "\n".join(parts)

    def parse_response(self, content: str, original_code: list[CodeFile] | None = None,
                       issues: IssueList | None = None, **kwargs) -> FixResult:
        logger.info(f"[FixerAgent] Parsing response ({len(content)} chars)")
        data = self.extract_json(content)

        fixed_code = []
        for fdata in data.get("fixed_files", []):
            fixed_code.append(CodeFile(
                path=fdata.get("path", ""),
                content=fdata.get("content", ""),
            ))

        patches = []
        for pdata in data.get("patches", []):
            patches.append(PatchInfo(
                issue_id=pdata.get("issue_id", ""),
                file=pdata.get("file", ""),
                diff=pdata.get("diff", ""),
            ))

        logger.info(f"[FixerAgent] Fixed {len(fixed_code)} files, {len(patches)} patches")
        return FixResult(fixed_code=fixed_code, patches=patches)