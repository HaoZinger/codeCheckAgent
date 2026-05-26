# Orchestrator: Manages multi-round code review workflow
import logging
import sys
import difflib

logger = logging.getLogger(__name__)
from src.agents.reviewer import ReviewerAgent
from src.agents.fixer import FixerAgent
from src.agents.validator import ValidatorAgent
from src.agents.base import AgentFailure
from src.config import Config
from src.scanner import scan_directory, chunk_large_file
from src.types import (
    CodeFile, Issue, IssueList, FixResult, RoundResult,
    ReviewReport, IssueValidation,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "info": 3}


class ReviewInterrupted(Exception):
    """Raised when the user interrupts the review process."""
    pass


class Orchestrator:
    """Manages the multi-agent, multi-round code review workflow."""

    def __init__(self, config: Config):
        self.config = config
        if not config.api_key:
            raise ValueError("API key is not set. Please set it via config.yaml, environment variable, or --api-key.")

        self.reviewer = ReviewerAgent(config.reviewer, config.api_key, config.api_base)
        self.fixer = FixerAgent(config.fixer, config.api_key, config.api_base)
        self.validator = ValidatorAgent(config.validator, config.api_key, config.api_base)
        self._interrupted = False

    def run(self, target_dir: str) -> ReviewReport:
        """Run the full review workflow on a target directory."""
        try:
            return self._run_impl(target_dir)
        except KeyboardInterrupt:
            self._interrupted = True
            print(f"\n\n  [INTERRUPTED] User cancelled the review process.")
            logger.warning("Review interrupted by user")
            print(f"  Generating partial report from completed rounds...")
            return self._build_partial_report()

    def _run_impl(self, target_dir: str) -> ReviewReport:
        """Internal implementation of the review workflow."""
        print(f"\n{'='*60}")
        print(f"  CodeCheckAgent - Multi-Agent Code Review System")
        print(f"  Press Ctrl+C to interrupt at any time")
        print(f"{'='*60}\n")

        # Step 1: Scan directory
        print(f"[Scan] Scanning directory: {target_dir}")
        code_files = scan_directory(target_dir, self.config)

        if not code_files:
            print("[Scan] No supported code files found.")
            return ReviewReport(
                total_rounds=0, total_files=0,
                total_issues_found=0, total_issues_fixed=0,
            )

        # Handle large files
        all_files = []
        for cf in code_files:
            chunks = chunk_large_file(cf, self.config.orchestrator.max_file_chars)
            all_files.extend(chunks)

        logger.info("Scan: %d file(s) in %s", len(code_files), target_dir)
        print(f"[Scan] Found {len(code_files)} file(s)")
        if len(all_files) > len(code_files):
            print(f"[Scan] Large files split into {len(all_files)} chunks for processing")

        # Initialize
        self._current_code = code_files
        self._review_code = all_files
        self._all_issues: list[Issue] = []
        self._round_results: list[RoundResult] = []

        # Multi-round loop
        for round_num in range(1, self.config.orchestrator.max_rounds + 1):
            self._current_round = round_num
            self._run_single_round(round_num)

            # Check convergence after each round
            open_issues = [i for i in self._all_issues if i.status in ("open", "false_fix")]
            if not open_issues:
                return ReviewReport(
                    total_rounds=len(self._round_results),
                    total_files=len(code_files),
                    total_issues_found=len(self._all_issues),
                    total_issues_fixed=sum(1 for i in self._all_issues if i.status == "fixed"),
                    residual_issues=[],
                    rounds=self._round_results,
                    converged=True,
                    fixed_code=self._current_code,
                )

        # Max rounds reached, not converged
        return self._build_partial_report()

    def _run_single_round(self, round_num: int):
        """Execute a single round of Reviewer -> Fixer -> Validator."""
        print(f"\n{'-'*60}")
        logger.info("Round %d/%d starting", round_num, self.config.orchestrator.max_rounds)
        print(f"  Round {round_num}/{self.config.orchestrator.max_rounds}")
        print(f"{'-'*60}")

        # --- Reviewer phase ---
        print(f"  [Reviewer] Analyzing code...", end=" ", flush=True)
        try:
            import time as _time; _t0 = _time.time()
            issue_list = self.reviewer.run(code_files=self._review_code)
            _elapsed = _time.time() - _t0
            _tag = f" ({_elapsed:.0f}s)" if _elapsed > 30 else ""
            print(f"Found {len(issue_list.issues)} issue(s){_tag}")
            if issue_list.summary:
                print(f"  [Reviewer] {issue_list.summary}")
        except AgentFailure as e:
            print(f"\n  [Reviewer] ERROR: {e}")
            self._print_round_summary(round_num, len(self._all_issues), 0, len(self._all_issues))
            return

        self._all_issues = self._merge_issues(self._all_issues, issue_list.issues)
        open_issues = [i for i in self._all_issues if i.status in ("open", "false_fix")]

        if not open_issues:
            print(f"  [Reviewer] No open issues remaining. Converged!")
            self._round_results.append(RoundResult(
                round_num=round_num, issues_found=0, issues_fixed=0,
                issues_remaining=0, issues=self._all_issues,
            ))
            return

        # Sort by severity (dynamic priority)
        open_issues.sort(key=lambda x: SEVERITY_ORDER.get(x.severity, 99))

        # --- Fixer phase ---
        fix_issues = IssueList(issues=open_issues, summary=f"Round {round_num} open issues")
        print(f"  [Fixer] Fixing {len(open_issues)} issue(s)...", end=" ", flush=True)
        try:
            import time as _time; _t0 = _time.time()
            fix_result = self.fixer.run(original_code=self._current_code, issues=fix_issues)
            _elapsed = _time.time() - _t0
            _tag = f" ({_elapsed:.0f}s)" if _elapsed > 30 else ""
            print(f"Produced {len(fix_result.patches)} patch(es){_tag}")
            # Warn if fixed code is identical to original
            if fix_result.fixed_code and self._current_code:
                changed = False
                for fc in fix_result.fixed_code:
                    for oc in self._current_code:
                        if fc.path == oc.path and fc.content != oc.content:
                            changed = True
                            break
                if not changed:
                    print(f"  [Fixer] WARNING: fixed code identical to original ? no changes applied")
        except AgentFailure as e:
            print(f"\n  [Fixer] ERROR: {e}")
            self._print_round_summary(round_num, len(self._all_issues), 0, len(open_issues))
            self._round_results.append(RoundResult(
                round_num=round_num, issues_found=len(open_issues),
                issues_fixed=0, issues_remaining=len(open_issues),
                issues=self._all_issues,
            ))
            return

        # --- Validator phase ---
        print(f"  [Validator] Validating fixes...", end=" ", flush=True)
        try:
            import time as _time; _t0 = _time.time()
            validation = self.validator.run(
                original_issues=fix_issues,
                fixed_code=fix_result.fixed_code,
                patches=fix_result.patches,
            )
        except AgentFailure as e:
            print(f"\n  [Validator] ERROR ({_elapsed:.0f}s): {e}")
            self._print_round_summary(round_num, len(self._all_issues), 0, len(open_issues))
            self._round_results.append(RoundResult(
                round_num=round_num, issues_found=len(open_issues),
                issues_fixed=0, issues_remaining=len(open_issues),
                issues=self._all_issues,
            ))
            return

        # Update issue statuses based on validation
        fixed_count = 0
        for vresult in validation.results:
            for issue in self._all_issues:
                if issue.id == vresult.issue_id:
                    if vresult.resolved:
                        issue.status = "fixed"
                        fixed_count += 1
                    elif vresult.false_fix:
                        issue.status = "false_fix"
                    break

        remaining = sum(1 for i in self._all_issues if i.status in ("open", "false_fix"))

        # Update current_code with fixed code
        if fix_result.fixed_code:
            self._current_code = fix_result.fixed_code
            self._review_code = []
            for cf in fix_result.fixed_code:
                chunks = chunk_large_file(cf, self.config.orchestrator.max_file_chars)
                self._review_code.extend(chunks)

        round_result = RoundResult(
            round_num=round_num,
            issues_found=len(open_issues),
            issues_fixed=fixed_count,
            issues_remaining=remaining,
            issues=[i for i in self._all_issues],
            patches=fix_result.patches,
            validation=validation,
        )
        self._round_results.append(round_result)
        self._print_round_summary(round_num, len(self._all_issues), fixed_count, remaining)

        if remaining == 0:
            print(f"\n  [OK] All issues resolved! Converged in {round_num} round(s).")

    def _build_partial_report(self) -> ReviewReport:
        """Build a report from whatever rounds have completed so far."""
        code_files = self._current_code if hasattr(self, '_current_code') else []
        all_issues = self._all_issues if hasattr(self, '_all_issues') else []
        round_results = self._round_results if hasattr(self, '_round_results') else []

        total_fixed = sum(1 for i in all_issues if i.status == "fixed")
        residual = [i for i in all_issues if i.status != "fixed"]
        converged = len(residual) == 0 and not self._interrupted

        if self._interrupted and residual:
            print(f"\n  [WARN] Review interrupted. {len(residual)} issue(s) remain unresolved:")
            for issue in residual:
                print(f"    - [{issue.id}] {issue.title} ({issue.severity}) - {issue.file}:{issue.line_start}")

        return ReviewReport(
            total_rounds=len(round_results),
            total_files=0,
            total_issues_found=len(all_issues),
            total_issues_fixed=total_fixed,
            residual_issues=residual,
            rounds=round_results,
            converged=converged,
            fixed_code=code_files,
        )

    def _merge_issues(self, existing: list[Issue], new_issues: list[Issue]) -> list[Issue]:
        """Merge new issues with existing ones, preserving fixed status."""
        existing_map = {i.id: i for i in existing}
        merged = []
        seen_ids = set()

        for issue in new_issues:
            if issue.id in existing_map:
                existing_issue = existing_map[issue.id]
                if existing_issue.status == "fixed":
                    issue.status = "fixed"
            merged.append(issue)
            seen_ids.add(issue.id)

        for issue in existing:
            if issue.id not in seen_ids:
                merged.append(issue)

        return merged

    def _print_round_summary(self, round_num: int, total: int, fixed: int, remaining: int):
        """Print a one-line round summary."""
        print(f"\n  [Summary] Round {round_num} Summary: {total} total | {fixed} fixed | {remaining} remaining")