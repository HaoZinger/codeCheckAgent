# ReviewerAgent: Analyzes code and outputs structured issue list
import json
import logging
from src.agents.base import BaseAgent
from src.config import AgentConfig
from src.types import CodeFile, Issue, IssueList

logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """Analyzes code files and produces a structured list of issues."""

    def __init__(self, config: AgentConfig, api_key: str, api_base: str | None = None):
        super().__init__("ReviewerAgent", config, api_key, api_base)

    def get_system_prompt(self) -> str:
        return """You are a STRICT code reviewer. Your job is to FIND PROBLEMS — every piece of code has them.

SCAN AGGRESSIVELY for:
- BUGS: division by zero, null/None access, index out of bounds, missing error handling,
  type mismatches, unclosed resources (files, connections), race conditions
- SECURITY: SQL injection, hardcoded secrets, eval()/exec() usage, XSS (innerHTML),
  missing input validation, weak hashing (MD5/SHA1), command injection
- LOGIC: wrong algorithm, off-by-one, dead code, unreachable branches, incorrect conditions,
  return type inconsistency, modifying collection while iterating
- PERFORMANCE: O(n^2) where O(n) works, string concatenation in loops, unnecessary copies,
  missing caching, synchronous blocking calls where async is available
- CODE QUALITY: mutable default arguments, bare except, wildcard imports, overly broad
  exception catching, inconsistent return types, == instead of equals()

REQUIRED OUTPUT — a single JSON object with exactly these fields:
{
  "issues": [
    {
      "id": "ISS-001",          // unique, sequential
      "file": "path/to/file.py", // exactly as provided in the input
      "line_start": 10,         // integer, 1-based
      "line_end": 12,           // integer, 1-based (same as start if single line)
      "severity": "critical",   // critical|major|minor|info
      "category": "bug",        // bug|security|performance|logic|style
      "title": "short summary", // max 80 chars
      "description": "detailed explanation of WHY this is a problem",
      "suggestion": "specific code change that fixes it",
      "status": "open"
    }
  ],
  "summary": "Found N issues: 2 critical, 3 major, 1 minor"
}

RULES:
- AIM FOR AT LEAST 2-3 ISSUES per file. Real code always has problems.
- If you truly find NOTHING wrong, explain WHY in the summary.
- Be SPECIFIC about line numbers — they must match the numbered code.
- NEVER output anything except the JSON object. No markdown, no explanation.
- NEVER include ``` fences around the JSON."""

    def build_user_message(self, code_files: list[CodeFile] | None = None, **kwargs) -> str:
        if not code_files:
            return "No code files to review."

        parts = ["Review the following code files and FIND ALL ISSUES. Be strict and thorough."]
        parts.append("")

        for cf in code_files:
            numbered_lines = []
            for i, line in enumerate(cf.content.split("\n"), 1):
                numbered_lines.append(f"{i:4d}| {line}")
            numbered_content = "\n".join(numbered_lines)

            parts.append(f"""=== File: {cf.path} ===
Language: {cf.language}
Content (with line numbers):
{numbered_content}
=== End of {cf.path} ===""")

        parts.append("")
        parts.append("Now output a single JSON object with all issues found. Remember: be STRICT, find REAL problems.")

        return "\n".join(parts)

    def parse_response(self, content: str, code_files: list[CodeFile] | None = None, **kwargs) -> IssueList:
        logger.info(f"[ReviewerAgent] Parsing response ({len(content)} chars)")
        data = self.extract_json(content)

        issues = []
        for item in data.get("issues", []):
            issue = Issue(
                id=str(item.get("id", "")),
                file=str(item.get("file", "")),
                line_start=int(item.get("line_start", 0)),
                line_end=int(item.get("line_end", 0)),
                severity=str(item.get("severity", "minor")),
                category=str(item.get("category", "style")),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                suggestion=str(item.get("suggestion", "")),
                status="open",
            )
            issues.append(issue)

        summary = data.get("summary", "")
        logger.info(f"[ReviewerAgent] Found {len(issues)} issues")
        return IssueList(issues=issues, summary=summary)