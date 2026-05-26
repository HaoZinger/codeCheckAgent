# SPEC.md ? Multi-Agent Code Review & Auto-Fix System Specification

## 1. System Architecture

### 1.1 Overall Architecture

```
+-----------------------------------------------------+
|                  CLI Entry (main.py)                  |
|           Args parsing / Config loading / Boot        |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|                 Scanner (scanner.py)                  |
|        Scan target directory -> collect code files    |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|             Orchestrator (orchestrator.py)            |
|                                                     |
|   +---------------------------------------------+   |
|   |              Multi-Round Loop                |   |
|   |                                             |   |
|   |  Round N:                                   |   |
|   |    ReviewerAgent --> IssueList               |   |
|   |         |                                    |   |
|   |         v                                    |   |
|   |    FixerAgent --> FixedCode                   |   |
|   |         |                                    |   |
|   |         v                                    |   |
|   |    ValidatorAgent --> ValidationResult        |   |
|   |         |                                    |   |
|   |         v                                    |   |
|   |    [Converged?] --Yes--> Output              |   |
|   |         |                                    |   |
|   |         No (under limit)                     |   |
|   |         |                                    |   |
|   |         +--> Next Round                      |   |
|   +---------------------------------------------+   |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|               Reporter (reporter.py)                 |
|      Generate review report (JSON/Markdown)          |
|      + output fixed code                             |
+-----------------------------------------------------+
```

### 1.2 Agent Roles & Data Flow

```
Input Code --> ReviewerAgent --> IssueList (structured JSON)
                                      |
                                      v
                                FixerAgent --> FixedCode + PatchInfo
                                      |
                                      v
                              ValidatorAgent --> ValidationResult
                                      |
                            +---------+---------+
                            |                   |
                       All Fixed          Unresolved
                            |                   |
                            v                   v
                        Output           Next Round (or max rounds output)
```

## 2. Data Structures

### 2.1 Code File

```python
@dataclass
class CodeFile:
    path: str           # relative path
    content: str        # file content
    language: str       # inferred from extension
```

### 2.2 ReviewerAgent Output: IssueList

```python
@dataclass
class Issue:
    id: str                    # e.g. "ISS-001"
    file: str                  # file path
    line_start: int            # 1-based
    line_end: int              # 1-based
    severity: str              # critical|major|minor|info
    category: str              # bug|security|style|performance|logic
    title: str                 # short summary
    description: str           # detailed explanation
    suggestion: str            # fix recommendation
    status: str                # open|fixed|false_fix

@dataclass
class IssueList:
    issues: list[Issue]
    summary: str
```

### 2.3 FixerAgent Input/Output

```python
@dataclass
class FixRequest:
    original_code: list[CodeFile]
    issues: IssueList

@dataclass
class FixResult:
    fixed_code: list[CodeFile]
    patches: list[PatchInfo]

@dataclass
class PatchInfo:
    issue_id: str
    file: str
    diff: str                # unified diff format
```

### 2.4 ValidatorAgent Input/Output

```python
@dataclass
class ValidationRequest:
    original_issues: IssueList
    fixed_code: list[CodeFile]
    patches: list[PatchInfo]

@dataclass
class ValidationResult:
    results: list[IssueValidation]
    summary: str

@dataclass
class IssueValidation:
    issue_id: str
    resolved: bool
    reason: str
    false_fix: bool
```

### 2.5 Round Result

```python
@dataclass
class RoundResult:
    round_num: int
    issues_found: int
    issues_fixed: int
    issues_remaining: int
    issues: list[Issue]
    patches: list[PatchInfo]
    validation: ValidationResult | None
```

### 2.6 Final Review Report

```python
@dataclass
class ReviewReport:
    total_rounds: int
    total_files: int
    total_issues_found: int
    total_issues_fixed: int
    residual_issues: list[Issue]
    rounds: list[RoundResult]
    converged: bool
    fixed_code: list[CodeFile]
```

## 3. Five Core Engineering Decisions

### Decision 1: Ensuring Structured LLM Output

**Choice**: Use `response_format: {"type": "json_object"}` or Function Calling with strict JSON Schema constraints.

**Rationale**: Constraining JSON output is more reliable than parsing natural language. Pydantic secondary validation with retry on failure.

**Limitation**: Even in JSON mode, LLMs may output non-conforming content, requiring fallback parsing + retry.

### Decision 2: How Does Fixer Modify Code Without Introducing New Issues?

**Choice**: Fixer outputs complete fixed file content + unified diff per change. System prompt strictly constrains "only modify locations marked in issues" and requires a diff as proof.

**Rationale**: Full file output ensures completeness; diff enables Validator review and report display.

**Limitation**: LLM may over-modify (e.g. auto-formatting), requiring Validator secondary review.

### Decision 3: How Does Validator Detect "False Fixes"?

**Choice**: Validator receives original issue + original code snippet + fixed code snippet, compares each, and outputs a judgment reason. Prompt explicitly defines false-fix patterns (comment-only changes, variable renames without logic changes, dead code additions, etc.).

**Rationale**: Three-way comparison + forced reasoning output improves detection accuracy.

**Limitation**: For complex logic issues, LLM judgment may be inaccurate.

### Decision 4: Context Management Across Rounds

**Choice**: Each round calls agents independently without retaining conversation history. Context is passed through structured data (IssueList status fields). Each agent receives: current code + current issue status.

**Rationale**: Avoids context bloat and attention decay. Structured data is more precise than chat history.

**Limitation**: Agents cannot learn from prior rounds' experience. A condensed round summary could be introduced later.

### Decision 5: Handling Multiple Programming Languages

**Choice**: Language-agnostic design ? Scanner identifies language by file extension, agent prompts include language type. No language-specific handling.

**Rationale**: Maintains system generality; LLMs natively support multiple languages.

**Limitation**: Language-specific best practices vary; generic prompts are less effective than specialized ones. Language-specific review rules can be added later.

## 4. Feature Scope

### Required [Mandatory]

| Feature | Status |
|---------|--------|
| ReviewerAgent: structured issue list output | Done |
| FixerAgent: targeted fixes based on issues | Done |
| ValidatorAgent: verify fixes + detect false fixes | Done |
| Multi-round iteration: Reviewer-Fixer-Validator loop | Done |
| Convergence: all fixed or max rounds (default 3) | Done |
| Non-convergence: list residual issues | Done |
| Real-time per-round progress output | Done |
| Final structured review report (Markdown) | Done |
| Final fixed code output | Done |
| Single-agent failure without crash + error message | Done |

### Optional [Bonus]

| Feature | Status |
|---------|--------|
| Dynamic priority: sort by severity | Skipped (time-constrained, fixed severity sort) |
| Context compression: condensed history | Skipped (each round is independent) |
| Diff format per-round code changes | Done |
| HTML export for review report | Skipped (Markdown is sufficient) |
| Agent retry mechanism | Done |
| Executable automated tests | Done (orchestration logic tests) |

### Out of Scope

- **No Web UI**: CLI-only to reduce complexity
- **No Git integration**: Direct file operations, no Git dependency
- **No real-time collaboration**: Single-user batch processing
- **No incremental review**: Full review each run, no change tracking

## 5. Known Defects & Degradation Strategies

### Defect 1: LLM Output Uncertainty
- **Degradation**: Max 3 retries per agent call; if still invalid, mark as agent failure and skip round
- **Impact**: Some issues may go unreviewed or unfixed

### Defect 2: Token Limits for Large/Many Files
- **Degradation**: Chunk files exceeding threshold (default 4000 chars)
- **Impact**: Cross-chunk related issues may be missed

### Defect 3: False Fix Misses
- **Degradation**: If Validator gives ambiguous judgment, default to "not resolved" and enter next round
- **Impact**: May extend iteration rounds but won't miss real issues

### Defect 4: Lack of Language-Specific Deep Rules
- **Degradation**: Rely on LLM's own knowledge; no language-specific rule injection
- **Impact**: Review quality for specific languages depends on LLM training data

### Defect 5: No Incremental Fix Capability
- **Degradation**: Full code output each round, higher cost
- **Impact**: Higher token consumption; suitable for small-to-medium code review scenarios
