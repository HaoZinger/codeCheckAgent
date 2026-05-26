#!/usr/bin/env python3
"""
CodeCheckAgent - Multi-Agent Code Review and Auto-Fix System

Usage:
    python src/main.py <target_directory> [options]
    python src/main.py ./my-project --provider deepseek --max-rounds 5
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config, PROVIDER_PRESETS
from src.orchestrator import Orchestrator
from src.reporter import generate_report


def setup_logging(verbose: bool, log_dir: str = "./codecheck_output"):
    import os as _os
    _os.makedirs(log_dir, exist_ok=True)
    log_file = _os.path.join(log_dir, "codecheck.log")

    console_level = logging.DEBUG if verbose else logging.ERROR
    file_level = logging.DEBUG

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    root.handlers.clear()

    # Console handler (clean terminal output)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler (full debug log)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Log the startup
    logging.debug("Log file: %s", log_file)


def main():
    provider_choices = list(PROVIDER_PRESETS.keys())

    parser = argparse.ArgumentParser(
        description="CodeCheckAgent - Multi-Agent Code Review and Auto-Fix System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py ./my-code
  python src/main.py ./my-code --provider deepseek
  python src/main.py ./my-code --provider deepseek-v4 --max-rounds 5
  python src/main.py ./my-code --config custom_config.yaml
  python src/main.py ./my-code --api-key sk-xxx --api-base https://api.example.com/v1

Available providers:
  openai       - OpenAI (GPT-4o, GPT-4-turbo, etc.)      env: OPENAI_API_KEY
  deepseek     - DeepSeek (V3, R1)                       env: DEEPSEEK_API_KEY
  deepseek-v4  - DeepSeek V4 Pro                         env: DEEPSEEK_API_KEY
  custom       - Custom OpenAI-compatible endpoint        env: OPENAI_API_KEY
        """,
    )

    parser.add_argument(
        "target", nargs="?",
        help="Target directory containing code to review",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=provider_choices,
        default=None,
        help=f"LLM provider preset (choices: {', '.join(provider_choices)})",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for reports and fixed code",
    )
    parser.add_argument(
        "--max-rounds", "-r",
        type=int,
        default=None,
        help="Maximum review rounds (default: 3)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (overrides config and env var)",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="API base URL (overrides provider preset)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for all agents (overrides provider default)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available provider presets and exit",
    )

    args = parser.parse_args()

    # --list-providers: show presets and exit (no target needed)
    if args.list_providers:
        print("\nAvailable LLM Provider Presets:\n")
        for name, preset in PROVIDER_PRESETS.items():
            print(f"  {name:14s}  {preset.description}")
            print(f"  {'':14s}  Model: {preset.default_model}")
            print(f"  {'':14s}  Env:   {preset.api_key_env}")
            if preset.api_base:
                print(f"  {'':14s}  URL:   {preset.api_base}")
            print()
        return 0

    # target is required for normal operation
    if not args.target:
        parser.print_help()
        print("\nERROR: target directory is required")
        sys.exit(1)

    # ---- Load configuration ----
    # (loaded early so we know the output dir for logging)
    config_path = args.config
    if config_path and os.path.exists(config_path):
        config = Config.from_yaml(config_path)
    elif os.path.exists("config.yaml"):
        config = Config.from_yaml("config.yaml")
    elif os.path.exists(os.path.join(os.path.dirname(__file__), "..", "config.yaml")):
        config = Config.from_yaml(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    else:
        config = Config.from_env()

    # Override provider if specified via CLI
    if args.provider:
        config.provider = args.provider
        config.apply_provider_preset()

    # Override with other CLI arguments
    if args.api_key:
        config.api_key = args.api_key
    if args.api_base:
        config.api_base = args.api_base
    if args.max_rounds is not None:
        config.orchestrator.max_rounds = args.max_rounds
    if args.output:
        config.orchestrator.output_dir = args.output
    if args.model:
        config.reviewer.model = args.model
        config.fixer.model = args.model
        config.validator.model = args.model

    # Setup logging (now that we know the output dir)
    setup_logging(args.verbose, config.orchestrator.output_dir)

    # ---- Validate ----
    if not config.api_key:
        preset = PROVIDER_PRESETS.get(config.provider)
        env_hint = preset.api_key_env if preset else "OPENAI_API_KEY"
        print(f"ERROR: API key is required for provider '{config.provider}'.")
        print(f"Set it via one of:")
        print(f"  1. Environment variable: {env_hint}")
        print(f"  2. Config file: config.yaml -> api_key")
        print(f"  3. CLI argument: --api-key")
        print(f"\nTip: use --list-providers to see all available providers")
        sys.exit(1)

    target_dir = os.path.abspath(args.target)
    if not os.path.isdir(target_dir):
        print(f"ERROR: Target directory not found: {target_dir}")
        sys.exit(1)

    # ---- Run ----
    print(f"\n{'='*60}")
    print(f"  Configuration")
    print(f"{'='*60}")
    print(config.summary())
    print(f"{'='*60}")

    try:
        orchestrator = Orchestrator(config)
        report = orchestrator.run(target_dir)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)

    # ---- Generate report ----
    if report.total_rounds > 0 or report.total_issues_found > 0:
        report_path = generate_report(report, config.orchestrator.output_dir)
        code_dir = os.path.join(config.orchestrator.output_dir, "fixed_code")

        print(f"\n{'='*60}")
        print(f"  Review Complete!")
        print(f"{'='*60}")
        log_file = os.path.join(config.orchestrator.output_dir, "codecheck.log")
        print(f"  Log:        {log_file}")
        print(f"  Report:     {report_path}")
        if report.fixed_code:
            print(f"  Fixed Code: {code_dir}")
        print(f"  Issues:     {report.total_issues_found} found / {report.total_issues_fixed} fixed")
        if report.residual_issues:
            print(f"  [WARN]      {len(report.residual_issues)} issue(s) remain unresolved")
        print()

    return 0 if report.converged else 1


if __name__ == "__main__":
    sys.exit(main())