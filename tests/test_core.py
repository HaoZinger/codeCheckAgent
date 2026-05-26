# Tests for CodeCheckAgent
# Covers: Scanner, Config, Orchestrator logic (with mocked agents), Reporter
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config, AgentConfig, OrchestratorConfig
from src.scanner import scan_directory, LANGUAGE_MAP, chunk_large_file
from src.types import (
    CodeFile, Issue, IssueList, FixResult, PatchInfo,
    RoundResult, ReviewReport, IssueValidation, ValidationResult,
)
from src.reporter import generate_report, _build_markdown_report, _build_json_report


class TestScanner(unittest.TestCase):
    """Test the code file scanner."""

    def setUp(self):
        self.config = Config()

    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = scan_directory(tmpdir, self.config)
            self.assertEqual(len(files), 0)

    def test_scan_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_path = os.path.join(tmpdir, "test.py")
            with open(py_path, "w") as f:
                f.write("print('hello')")
            txt_path = os.path.join(tmpdir, "readme.png")
            with open(txt_path, "w") as f:
                f.write("hello")

            files = scan_directory(tmpdir, self.config)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].language, "Python")
            self.assertIn("print('hello')", files[0].content)

    def test_scan_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("a")
            with open(os.path.join(subdir, "b.py"), "w") as f:
                f.write("b")

            files = scan_directory(tmpdir, self.config)
            self.assertEqual(len(files), 2)

    def test_language_map_coverage(self):
        self.assertEqual(LANGUAGE_MAP[".py"], "Python")
        self.assertEqual(LANGUAGE_MAP[".js"], "JavaScript")
        self.assertEqual(LANGUAGE_MAP[".go"], "Go")
        self.assertEqual(LANGUAGE_MAP[".rs"], "Rust")

    def test_chunk_large_file(self):
        cf = CodeFile(path="test.py", content="line\n" * 100, language="Python")
        # With max_chars=10, should produce many small chunks
        chunks = chunk_large_file(cf, max_chars=10)
        self.assertGreater(len(chunks), 1)

    def test_chunk_small_file(self):
        cf = CodeFile(path="test.py", content="short", language="Python")
        chunks = chunk_large_file(cf, max_chars=8000)
        self.assertEqual(len(chunks), 1)


class TestConfig(unittest.TestCase):
    """Test configuration loading."""

    def test_default_config(self):
        config = Config()
        self.assertEqual(config.orchestrator.max_rounds, 3)
        self.assertIsNone(config.api_key)
        self.assertEqual(config.reviewer.model, "gpt-4o")

    def test_env_config(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            config = Config.from_env()
            self.assertEqual(config.api_key, "test-key")

    def test_yaml_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
api_key: "test-key-yaml"
orchestrator:
  max_rounds: 5
reviewer:
  model: "gpt-3.5-turbo"
""")
            f.flush()
            config = Config.from_yaml(f.name)
            self.assertEqual(config.api_key, "test-key-yaml")
            self.assertEqual(config.orchestrator.max_rounds, 5)
            self.assertEqual(config.reviewer.model, "gpt-3.5-turbo")
        os.unlink(f.name)


class TestTypes(unittest.TestCase):
    """Test data type construction."""

    def test_issue_creation(self):
        issue = Issue(
            id="ISS-001", file="test.py", line_start=10, line_end=12,
            severity="critical", category="bug",
            title="Null pointer", description="NPE risk",
            suggestion="Add null check", status="open",
        )
        self.assertEqual(issue.id, "ISS-001")
        self.assertEqual(issue.status, "open")

    def test_issue_list_defaults(self):
        il = IssueList()
        self.assertEqual(len(il.issues), 0)
        self.assertEqual(il.summary, "")

    def test_review_report(self):
        report = ReviewReport(
            total_rounds=3, total_files=5,
            total_issues_found=10, total_issues_fixed=8,
            converged=False,
        )
        self.assertFalse(report.converged)
        self.assertEqual(report.total_issues_fixed, 8)


class TestOrchestratorLogic(unittest.TestCase):
    """Test orchestrator logic with mocked agents."""

    def _make_mock_config(self):
        config = Config()
        config.api_key = "mock-key"
        config.orchestrator.max_rounds = 3
        return config

    def _make_sample_code(self):
        return [CodeFile(
            path="test.py",
            content="def foo(): pass\n",
            language="Python",
        )]

    def test_orchestrator_requires_api_key(self):
        config = Config()
        from src.orchestrator import Orchestrator
        with self.assertRaises(ValueError):
            Orchestrator(config)

    @patch("src.orchestrator.ReviewerAgent")
    @patch("src.orchestrator.FixerAgent")
    @patch("src.orchestrator.ValidatorAgent")
    @patch("src.orchestrator.scan_directory")
    def test_full_convergence(self, mock_scan, mock_validator_cls, mock_fixer_cls, mock_reviewer_cls):
        """Test that orchestrator handles full convergence correctly."""
        mock_scan.return_value = self._make_sample_code()

        # Mock Reviewer: finds 2 issues
        mock_reviewer = MagicMock()
        mock_reviewer.run.return_value = IssueList(issues=[
            Issue("ISS-001", "test.py", 1, 1, "major", "bug", "Bug1", "desc1", "fix1", "open"),
            Issue("ISS-002", "test.py", 1, 1, "minor", "style", "Bug2", "desc2", "fix2", "open"),
        ], summary="Found 2 issues")
        mock_reviewer_cls.return_value = mock_reviewer

        # Mock Fixer
        mock_fixer = MagicMock()
        mock_fixer.run.return_value = FixResult(
            fixed_code=self._make_sample_code(),
            patches=[
                PatchInfo("ISS-001", "test.py", "diff1"),
                PatchInfo("ISS-002", "test.py", "diff2"),
            ],
        )
        mock_fixer_cls.return_value = mock_fixer

        # Mock Validator: all resolved
        mock_validator = MagicMock()
        mock_validator.run.return_value = ValidationResult(results=[
            IssueValidation("ISS-001", True, "Fixed", False),
            IssueValidation("ISS-002", True, "Fixed", False),
        ], summary="All fixed")
        mock_validator_cls.return_value = mock_validator

        from src.orchestrator import Orchestrator
        orch = Orchestrator(self._make_mock_config())
        report = orch.run("dummy_dir")

        self.assertTrue(report.converged)
        self.assertEqual(report.total_rounds, 1)
        self.assertEqual(report.total_issues_fixed, 2)
        self.assertEqual(len(report.residual_issues), 0)

    @patch("src.orchestrator.ReviewerAgent")
    @patch("src.orchestrator.FixerAgent")
    @patch("src.orchestrator.ValidatorAgent")
    @patch("src.orchestrator.scan_directory")
    def test_false_fix_triggers_another_round(self, mock_scan, mock_validator_cls, mock_fixer_cls, mock_reviewer_cls):
        """Test that a false fix triggers another round."""
        mock_scan.return_value = self._make_sample_code()

        # Mock Reviewer: 1 issue
        mock_reviewer = MagicMock()
        mock_reviewer.run.return_value = IssueList(issues=[
            Issue("ISS-001", "test.py", 1, 1, "critical", "bug", "Bug", "desc", "fix", "open"),
        ], summary="Found 1 issue")
        mock_reviewer_cls.return_value = mock_reviewer

        # Mock Fixer
        mock_fixer = MagicMock()
        mock_fixer.run.return_value = FixResult(
            fixed_code=self._make_sample_code(),
            patches=[PatchInfo("ISS-001", "test.py", "diff")],
        )
        mock_fixer_cls.return_value = mock_fixer

        # Mock Validator: first round false fix, second round resolved
        mock_validator = MagicMock()
        mock_validator.run.side_effect = [
            ValidationResult(results=[
                IssueValidation("ISS-001", False, "Still broken", True),
            ], summary="False fix detected"),
            ValidationResult(results=[
                IssueValidation("ISS-001", True, "Fixed", False),
            ], summary="Fixed"),
        ]
        mock_validator_cls.return_value = mock_validator

        from src.orchestrator import Orchestrator
        orch = Orchestrator(self._make_mock_config())
        report = orch.run("dummy_dir")

        self.assertTrue(report.converged)
        self.assertEqual(report.total_rounds, 2)

    @patch("src.orchestrator.ReviewerAgent")
    @patch("src.orchestrator.FixerAgent")
    @patch("src.orchestrator.ValidatorAgent")
    @patch("src.orchestrator.scan_directory")
    def test_max_rounds_reached(self, mock_scan, mock_validator_cls, mock_fixer_cls, mock_reviewer_cls):
        """Test that system correctly handles reaching max rounds."""
        mock_scan.return_value = self._make_sample_code()

        mock_reviewer = MagicMock()
        mock_reviewer.run.return_value = IssueList(issues=[
            Issue("ISS-001", "test.py", 1, 1, "critical", "bug", "Hard bug", "desc", "fix", "open"),
        ], summary="Found 1 issue")
        mock_reviewer_cls.return_value = mock_reviewer

        mock_fixer = MagicMock()
        mock_fixer.run.return_value = FixResult(
            fixed_code=self._make_sample_code(),
            patches=[PatchInfo("ISS-001", "test.py", "diff")],
        )
        mock_fixer_cls.return_value = mock_fixer

        # Validator never confirms fix
        mock_validator = MagicMock()
        mock_validator.run.return_value = ValidationResult(results=[
            IssueValidation("ISS-001", False, "Still broken", False),
        ], summary="Not fixed")
        mock_validator_cls.return_value = mock_validator

        config = self._make_mock_config()
        config.orchestrator.max_rounds = 2  # Only 2 rounds

        from src.orchestrator import Orchestrator
        orch = Orchestrator(config)
        report = orch.run("dummy_dir")

        self.assertFalse(report.converged)
        self.assertEqual(report.total_rounds, 2)
        self.assertEqual(len(report.residual_issues), 1)


class TestReporter(unittest.TestCase):
    """Test report generation."""

    def test_generate_markdown_report(self):
        report = ReviewReport(
            total_rounds=2,
            total_files=3,
            total_issues_found=5,
            total_issues_fixed=4,
            residual_issues=[
                Issue("ISS-005", "test.py", 10, 12, "major", "bug",
                      "Remaining bug", "desc", "fix", "false_fix"),
            ],
            rounds=[
                RoundResult(
                    round_num=1,
                    issues_found=3, issues_fixed=2, issues_remaining=1,
                    patches=[PatchInfo("ISS-001", "test.py", "-old\n+new")],
                    validation=ValidationResult(
                        results=[
                            IssueValidation("ISS-001", True, "Fixed", False),
                            IssueValidation("ISS-002", True, "Fixed", False),
                            IssueValidation("ISS-003", False, "Not fixed", False),
                        ],
                        summary="2 fixed, 1 remaining",
                    ),
                ),
                RoundResult(
                    round_num=2,
                    issues_found=2, issues_fixed=1, issues_remaining=1,
                ),
            ],
            converged=False,
            fixed_code=[CodeFile("test.py", "fixed content", "Python")],
        )

        md = _build_markdown_report(report)
        self.assertIn("CodeCheckAgent", md)
        self.assertIn("Residual Issues", md)
        self.assertIn("Remaining bug", md)
        self.assertIn("Round 1", md)
        self.assertIn("-old", md)

    def test_generate_json_report(self):
        report = ReviewReport(
            total_rounds=1, total_files=1,
            total_issues_found=1, total_issues_fixed=1,
            converged=True,
            rounds=[RoundResult(round_num=1, issues_found=1, issues_fixed=1, issues_remaining=0)],
        )
        data = _build_json_report(report)
        self.assertEqual(data["total_issues_found"], 1)
        self.assertTrue(data["converged"])
        self.assertIn("generated_at", data)

    def test_generate_report_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = ReviewReport(
                total_rounds=1, total_files=1,
                total_issues_found=0, total_issues_fixed=0,
                converged=True,
                fixed_code=[CodeFile("test.py", "content", "Python")],
            )
            path = generate_report(report, tmpdir)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "review_report.json")))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "fixed_code", "test.py")))


if __name__ == "__main__":
    unittest.main()
