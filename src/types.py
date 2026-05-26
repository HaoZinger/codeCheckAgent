# Shared data types for CodeCheckAgent
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CodeFile:
    """Represents a single code file."""
    path: str
    content: str
    language: str = ""


@dataclass
class Issue:
    """A single issue found by the Reviewer."""
    id: str
    file: str
    line_start: int
    line_end: int
    severity: str          # "critical" | "major" | "minor" | "info"
    category: str          # "bug" | "security" | "style" | "performance" | "logic"
    title: str
    description: str
    suggestion: str
    status: str = "open"   # "open" | "fixed" | "false_fix"


@dataclass
class IssueList:
    """Collection of issues from a review round."""
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""


@dataclass
class PatchInfo:
    """Information about a single code fix."""
    issue_id: str
    file: str
    diff: str


@dataclass
class FixResult:
    """Result from the Fixer agent."""
    fixed_code: list[CodeFile] = field(default_factory=list)
    patches: list[PatchInfo] = field(default_factory=list)


@dataclass
class IssueValidation:
    """Validation result for a single issue."""
    issue_id: str
    resolved: bool
    reason: str
    false_fix: bool = False


@dataclass
class ValidationResult:
    """Result from the Validator agent."""
    results: list[IssueValidation] = field(default_factory=list)
    summary: str = ""


@dataclass
class RoundResult:
    """Complete result of one round."""
    round_num: int
    issues_found: int
    issues_fixed: int
    issues_remaining: int
    issues: list[Issue] = field(default_factory=list)
    patches: list[PatchInfo] = field(default_factory=list)
    validation: Optional[ValidationResult] = None


@dataclass
class ReviewReport:
    """Final review report."""
    total_rounds: int
    total_files: int
    total_issues_found: int
    total_issues_fixed: int
    residual_issues: list[Issue] = field(default_factory=list)
    rounds: list[RoundResult] = field(default_factory=list)
    converged: bool = False
    fixed_code: list[CodeFile] = field(default_factory=list)
