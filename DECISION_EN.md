# DECISION.md ? Decision Records

---

## Decision #1: Programming Language

**Date**: 2026-05-25

**Context**: Need to choose between CLI tool and web application, and pick a programming language.

**Options**:
- A: Python CLI ? lightweight, fast development, mature AI/LLM ecosystem (official OpenAI SDK)
- B: TypeScript/Node.js web app ? provides Web UI, longer dev cycle
- C: Rust CLI ? best performance, slow development, immature LLM SDK

**Decision**: Python CLI (Option A)

**Rationale**:
- OpenAI's official Python SDK is the most mature and stable
- Python dataclasses + Pydantic suit structured data flow
- CLI meets core requirements; Web UI adds unnecessary complexity
- High dev efficiency, complete system feasible within 6 hours
- Cross-platform support (Windows/Linux/macOS)

**Risk**: Python CLI less user-friendly for non-technical users; performance may lag for very large projects vs compiled languages.

**Follow-up**: Could add simple Web UI (FastAPI + frontend) or use Rich library for prettier CLI output with more time.

---

## Decision #2: Inter-Agent Communication

**Date**: 2026-05-25

**Context**: Three agents need to pass data (Issue -> Code -> Validation result). Must choose a communication method.

**Options**:
- A: Structured JSON data passing (independent per-round calls, context via JSON)
- B: Conversational context (preserve full chat history)
- C: Hybrid (structured data + condensed round summary)

**Decision**: Structured JSON data passing (Option A)

**Rationale**:
- Independent per-round calls avoid context bloat (token waste + attention decay)
- JSON structured data is precise, parseable, verifiable
- Matches the "output must be structured format" constraint in SPEC
- Easier to implement retries and error handling
- Each agent has a clear responsibility with well-defined I/O types

**Risk**: Agents can't leverage prior rounds' "experience"; may repeat mistakes. LLM in fresh context may miss historical info.

**Follow-up**: Could add lightweight round summary (Option C), passing condensed prior-round info at round start.

---

## Decision #3: Code Fix Strategy

**Date**: 2026-05-25

**Context**: Fixer needs to output fixed code. Two main strategies: full file vs patch/diff.

**Options**:
- A: Fixer outputs full fixed files + diffs per change (current)
- B: Fixer outputs only diff/patch, system applies to original
- C: Fixer outputs only full fixed files, no diffs

**Decision**: Option A (full files + diffs)

**Rationale**:
- Full files ensure code integrity, avoid patch apply failures
- Diffs enable Validator to review specific changes and report display
- LLM more reliably outputs full files than precise diff format
- Both together provide redundancy

**Risk**: Larger output, higher token consumption. Large files may exceed token limits.

**Follow-up**: Could implement true diff-based fixes (Option B) for large files to reduce token consumption. Currently mitigated via file chunking.

---

## Decision #4: False Fix Detection Strategy

**Date**: 2026-05-25

**Context**: Validator must identify "false fixes" ? code changed but problem not solved.

**Options**:
- A: Pure LLM judgment (let Validator agent decide)
- B: Rule engine + LLM (detect common patterns via rules, LLM supplements)
- C: Static analysis + LLM (lint/static analysis tools first, LLM for final judgment)

**Decision**: Option A (pure LLM judgment, guided by well-designed prompt)

**Rationale**:
- Task explicitly requires Validator to have this capability but not a specific implementation
- Pure LLM approach is simple to implement, feasible within 6 hours
- Prompt explicitly defines false-fix patterns, guiding LLM to correct judgments
- No additional tool dependencies required

**Risk**: LLM judgment may be inaccurate for complex logic; false-fix misses possible. Performance varies across LLM models.

**Follow-up**: Could introduce Option B (rule engine), filtering simple patterns (comment-only changes, variable renames) first.

---

## Decision #5: Config Management

**Date**: 2026-05-25

**Context**: System needs to manage API keys, model parameters, timeouts, etc.

**Options**:
- A: YAML config file + env vars + CLI args (current)
- B: Pure env vars (12-factor app style)
- C: Pure CLI args

**Decision**: Option A (three-layer: YAML + env + CLI)

**Rationale**:
- YAML suits complex config (different params per agent)
- Env vars suit sensitive info (API keys) and CI/CD scenarios
- CLI args suit temporary overrides, convenient for debugging
- Priority: CLI > env > YAML > defaults, clear logic

**Risk**: Multiple config sources may cause confusion about which value is active. Should log the final effective config.

**Follow-up**: Add `--show-config` flag to print final effective configuration.

---

## Decision #6: Large File Handling

**Date**: 2026-05-25

**Context**: LLMs have token limits; large files may exceed context windows.

**Options**:
- A: File chunking by character count with line ranges (current)
- B: Truncate files (keep only first N chars)
- C: Refuse to process large files

**Decision**: Option A (file chunking)

**Rationale**:
- Chunking is more complete than truncation, won't lose code
- Cross-chunk context loss possible but better than no review at all
- System notifies user when files are chunked

**Risk**: Cross-chunk related issues may be missed (e.g., function defined in one chunk, called in another). Line numbers offset after chunking.

**Follow-up**: Could introduce semantic chunking (by function/class boundaries) or use models with longer context windows.

---

## Decision #7: Dynamic Priority

**Date**: 2026-05-25

**Context**: Dynamic priority is marked [Optional] in task description.

**Options**:
- A: Implement ? sort by severity each round
- B: Don't implement ? fix in Reviewer output order
- C: Full implementation ? consider severity, dependencies, fix difficulty

**Decision**: Option A (simple: sort by severity)

**Rationale**:
- High ROI: severity sort is 3 lines of code with actual value
- Ensures critical issues fixed first
- Option C requires LLM difficulty assessment, adding complexity and uncertainty

**Risk**: Simple severity sort may ignore dependencies between issues (fixing A may affect B).

**Follow-up**: Could extend to topological sort (considering dependency relationships) if needed.
