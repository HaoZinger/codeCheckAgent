# ITERATION_LOG.md ? AI Collaboration Iteration Records

This document records the complete process of collaborating with AI tools (Codex CLI) to build this system.

---

## Iteration #1: System Architecture Design

**Date**: 2026-05-25 17:40

**Task**: Understand requirements from the task description and design overall system architecture.

**Prompt Strategy**: Have AI read the task description, output SPEC.md (architecture, data flow, data structures, ASCII flowchart), and analyze five core engineering decisions.

**AI Issues**: Initial read had encoding issues (Windows GBK vs UTF-8). Resolved by specifying `-Encoding UTF8`.

**Final Quality**: SPEC.md covers architecture, data flow, data structures, 5 decisions, feature scope, and degradation strategies.

---

## Iteration #2: Core Code Implementation

**Date**: 2026-05-25 17:45

**Task**: Implement complete runnable code: Scanner, three Agents, Orchestrator, Reporter, CLI.

**Prompt Strategy**: Define data structures first (types.py), then implement modules sequentially: config -> scanner -> agents(base->reviewer->fixer->validator) -> orchestrator -> reporter -> main.

**AI Issues**: Large code volume required multiple shell_command writes; dataclass needed `field(default_factory=list)` for mutable defaults.

**Final Quality**: All modules complete, interfaces aligned, each agent has full prompt and parser.

---

## Iteration #3: Config & Documentation

**Date**: 2026-05-25 17:55

**Task**: Create config.yaml, README.md, three-layer config management.

**Final Quality**: Complete README, all fields configurable in config.yaml.

---

## Iteration #4: Test & Decision Docs

**Date**: 2026-05-25 18:00

**Task**: TEST.md (5 test cases), DECISION.md (7 engineering decisions).

**Final Quality**: Covers Happy Path, Validator rejection, non-convergence, agent failure, edge cases.

---

## Iteration #5: Initial Validation

**Date**: 2026-05-25 18:10

**Task**: Complete ITERATION_LOG.md initial version, verify system syntax and imports.

**Final Quality**: 5 iterations recorded, 19 automated tests all passing.

---

## Iteration #6: Multi-Language Test Code

**Date**: 2026-05-25 18:30

**Task**: Generate test code in Python, Java, JavaScript for functional testing.

**Prompt Strategy**: 2 files per language, each with 3-5 known issues covering: division by zero, unclosed resources, eval injection, SQL injection, XSS, array bounds, type inconsistency.

**My Handling**: Organized by language into `test_sample/python/`, `java/`, `javascript/`. Final: 7 files, 30+ known issues.

| File | Language | Issues Embedded |
|------|----------|----------------|
| `calculator.py` | Python | Div by zero, `eval()`, unclosed file, mutable default arg, inconsistent return, empty list div |
| `auth.py` | Python | MD5 weak hash, SQL injection, hardcoded secret, unclosed connection, fake JWT |
| `UserService.java` | Java | `==` for strings, array bounds, string concat in loop, concurrent modification |
| `FileProcessor.java` | Java | Resource leak, `==` for empty string, SQL injection, swallowed exception, div by zero |
| `dataService.js` | JavaScript | Missing `await`, async in forEach, XSS, `==`, bounds, `eval()` |
| `utils.js` | JavaScript | Shallow deepClone, `this` binding, inconsistent return, sync XHR |

---

## Iteration #7: Interrupt Handling & Provider Presets

**Date**: 2026-05-26 14:00

**Task**: Add Ctrl+C graceful interrupt handling, support DeepSeek and other providers.

**Prompt Strategy**: Interrupt: wrap `Orchestrator.run()` with `try/except KeyboardInterrupt`, output partial report. Provider: define `PROVIDER_PRESETS` in config.py with api_base, model name, env vars.

**AI Issues**: Interrupt handling required refactoring `_run_impl` / `_run_single_round` to avoid code duplication. Provider preset `response_format` compatibility needed per-provider distinction.

**Final Quality**: Ctrl+C outputs partial report from completed rounds; `--provider deepseek-v4` one-click switch.

---

## Iteration #8: DeepSeek ? Empty Response

**Date**: 2026-05-26 15:09

**Task**: Diagnose DeepSeek returning `Empty response from LLM`.

**AI Issues**: `response_format={"type":"json_object"}` incompatible with DeepSeek causing empty response. Model name `deepseek-v4-pro` was thought invalid (actually was valid; the real issue was elsewhere).

**My Handling**: Added `supports_json_mode` field to `ProviderPreset`, default `False` for DeepSeek initially. Added API connectivity diagnostic tool.

**Final Quality**: Provider-level JSON mode switch working; API diagnostic tool available.

---

## Iteration #9: DeepSeek ? Reviewer Finding No Issues

**Date**: 2026-05-26 15:15

**Task**: DeepSeek returned normally but `Found 0 issue(s)`.

**AI Issues**: Original prompt "Be thorough but not pedantic" was too conservative for DeepSeek.

**My Handling**: Rewrote prompt to "You are a STRICT code reviewer. FIND PROBLEMS". Listed issue categories with concrete examples. Added hard requirement "AIM FOR AT LEAST 2-3 ISSUES per file". Reviewer summary now always printed to terminal.

**Final Quality**: Reviewer began detecting issues normally.

---

## Iteration #10: DeepSeek ? JSON Newline Parse Failure

**Date**: 2026-05-26 15:20

**Task**: `Unterminated string` error ? `description` field contained literal newlines.

**AI Issues**: DeepSeek output multi-line strings in JSON. AI implemented `_repair_json()` (auto-escape `\n` in strings) and `_try_strip_tail()` (trailing character removal).

**My Handling**: Confirmed the 5-layer fallback strategy in `extract_json` is reasonable.

**Final Quality**: Multi-line string JSON auto-repaired and parsed correctly.

---

## Iteration #11: DeepSeek ? Enable JSON Output

**Date**: 2026-05-26 15:30

**Task**: DeepSeek actually supports `response_format={"type":"json_object"}`, should be enabled.

**Prompt Strategy**: Told AI "DeepSeek provides JSON Output feature".

**Final Quality**: DeepSeek requests now include `response_format`, outputting valid JSON.

---

## Iteration #12: DeepSeek ? JSON Truncation

**Date**: 2026-05-26 15:35

**Task**: `Expecting ',' delimiter` ? JSON truncated by `max_tokens`.

**AI Issues**: Default `max_tokens=4096` insufficient for multi-file review. AI doubled default to 8192, added `finish_reason=length` auto-retry (double tokens, cap 32768).

**Final Quality**: Truncation auto-detected and retried; no more truncation from insufficient max_tokens.

---

## Iteration #13: DeepSeek ? self Reference Bug

**Date**: 2026-05-26 16:19

**Task**: `NameError: name 'self' is not defined` and `UnboundLocalError: current_max_tokens`.

**AI Issues**: AI mistakenly wrote `current_max_tokens = self.config.max_tokens` into `@staticmethod` method. Fix caused f-string syntax error. Second fix deleted correct initialization. Three consecutive bugs from one edit.

**My Handling**: Traceback located `extract_json:158`, had AI remove stray code. Then `current_max_tokens` undefined, had AI restore initialization.

**Final Quality**: 19 tests all passing; system completed Reviewer->Fixer->Validator flow on DeepSeek.

---

## Iteration #14: Simplify Provider Presets

**Date**: 2026-05-26 17:40

**Task**: `deepseek` and `deepseek-v4` presets were duplicates; keep only `deepseek-v4`.

**AI Issues**: Needed to sync references across README, config.yaml, check_api.py.

**Final Quality**: Presets simplified to openai / deepseek-v4 / custom.

---

## Iteration #15: Fix Model Name Passing Bug

**Date**: 2026-05-26 17:45

**Task**: API error "you passed ." ? model name was empty.

**AI Issues**: `apply_provider_preset` had condition `if agent_cfg.model == "gpt-4o"` to override; empty model name didn't match.

**My Handling**: Changed condition to `if not agent_cfg.model or agent_cfg.model == "gpt-4o"`. Added model non-empty assertion before API call.

**Final Quality**: Model name correctly passed; API no longer reports "you passed .".

---

## Iteration #16: Log Optimization

**Date**: 2026-05-26 18:20

**Task**: Log output was messy (logger timestamps interleaving with print progress lines).

**Prompt Strategy**: Agent status -> print() (unified with Orchestrator channel). Logger -> file output only + --verbose terminal. Added `codecheck.log` for full DEBUG records.

**AI Issues**: `setup_logging` needed `config.output_dir` but logging initialized before config loading. Reordered to load config first.

**Final Quality**: Clean terminal (progress + fatal errors only, no timestamp noise). Complete file log at `codecheck_output/codecheck.log`.

---

## Iteration #17: DeepSeek Performance Diagnosis

**Date**: 2026-05-26 18:30

**Task**: DeepSeek API extremely slow (131s~262s); diagnose root cause.

**AI Issues**: Log showed `finish=length len=8186 elapsed=131.5s` ? output truncated by max_tokens. Truncation triggered retry at doubled tokens for another 130s, total 262s still truncated. Root cause: input too large (7 files with line numbers) consuming context window, leaving no output space.

**My Handling**: max_tokens default 8192 -> 16384; max_file_chars 8000 -> 4000 (halved input); retry cap 32768 -> 65536; terminal shows elapsed for calls >30s; log includes input size.

**Final Quality**: Reduced input prevents truncation; single call speed acceptable.

---

## Iteration #18: Fixed Code Not Changing Diagnosis

**Date**: 2026-05-26 19:00

**Task**: `codecheck_output/fixed_code` identical to original; need to diagnose Fixer pipeline.

**AI Issues**: Possible causes: Fixer returns empty `fixed_files`, or content identical to original. Current code only updates `current_code` when `fix_result.fixed_code` is non-empty.

**My Handling**: Added Fixer no-change detection WARNING in orchestrator.

**Final Quality**: Terminal prints WARNING when Fixer returns unchanged code.

---

## Iteration #19: Documentation Updates & Git Init

**Date**: 2026-05-26 19:10+

**Task**: Update iteration records, initialize git repository, add English documentation.

**Final Quality**: 19 iterations fully documented. Git repo initialized with .gitignore. English versions of all docs created (README_EN.md, SPEC_EN.md, TEST_EN.md, DECISION_EN.md, ITERATION_LOG_EN.md).
