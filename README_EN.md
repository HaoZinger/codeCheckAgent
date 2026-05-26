# CodeCheckAgent -- Multi-Agent Code Review & Auto-Fix System

**English** | [中文](README.md)

---

A CLI tool built with AI, implementing multi-agent collaborative code review and automatic fix.

## Requirements

- **Python** 3.10+
- **LLM API Key** (OpenAI / DeepSeek V4 / compatible endpoints)

## Installation

```bash
# 1. Enter project directory
cd codeCheckAgent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API Key
# OpenAI:
$env:OPENAI_API_KEY="sk-your-key-here"

# DeepSeek V4:
$env:DEEPSEEK_API_KEY="sk-your-deepseek-key"
```

## Quick Start

```bash
# Use OpenAI (default)
python src/main.py ./test_sample

# Use DeepSeek V4
python src/main.py ./test_sample --provider deepseek-v4

# List all available providers
python src/main.py --list-providers
```

## Interrupt Handling

Press `Ctrl+C` at any time during execution:

```
[INTERRUPTED] User cancelled the review process.
Generating partial report from completed rounds...
```

The system saves results from completed rounds, generates a partial report, and preserves already-fixed code -- no progress is lost.

## Supported LLM Providers

| Provider | Model | Env Variable | Description |
|----------|------|-------------|-------------|
| `openai` | gpt-4o | `OPENAI_API_KEY` | OpenAI official |
| `deepseek-v4` | deepseek-v4-pro | `DEEPSEEK_API_KEY` | DeepSeek V4 Pro |
| `custom` | user-defined | `OPENAI_API_KEY` | Any compatible endpoint |

## Usage Examples

```bash
# DeepSeek V4 Pro, 5 rounds, custom output dir
python src/main.py ./test_sample `
    --provider deepseek-v4 `
    --max-rounds 5 `
    --output ./results

# Custom API endpoint
python src/main.py ./test_sample `
    --provider custom `
    --api-base https://your-endpoint.com/v1 `
    --model your-model-name `
    --api-key sk-xxx

# Verbose logging
python src/main.py ./test_sample --provider deepseek-v4 --verbose
```

## CLI Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `target` | -- | Target code directory (required) | -- |
| `--provider` | `-p` | LLM provider preset | `openai` |
| `--config` | `-c` | YAML config file path | `config.yaml` |
| `--output` | `-o` | Output directory | `./codecheck_output` |
| `--max-rounds` | `-r` | Max review rounds | 3 |
| `--api-key` | -- | API key (overrides all sources) | -- |
| `--api-base` | -- | API base URL (overrides preset) | -- |
| `--model` | -- | Model name (overrides preset) | provider default |
| `--verbose` | `-v` | Verbose logging | off |
| `--list-providers` | -- | List all provider presets | -- |

## Architecture

```
Input(dir) --> Scanner --> Orchestrator --> Reporter --> Output(report+code)
                 |            |
                 |   Ctrl+C --> graceful interrupt + partial report
                 |
       +---------+---------+
       |         |         |
 Reviewer  --> Fixer --> Validator
  (review)    (fix)     (validate)
       +---------+---------+
                 |
        multi-round until convergence
```

## Three Agent Roles

| Agent | Responsibility | Input | Output |
|-------|---------------|-------|--------|
| **ReviewerAgent** | Analyze code for bugs/security/performance/style issues | Code files | Structured issue list (JSON) |
| **FixerAgent** | Apply targeted fixes based on issue list | Original code + issues | Fixed code + diffs |
| **ValidatorAgent** | Verify fixes are real; identify false fixes | Issues + fixed code | Per-issue validation results |

## Output

Each run generates in the output directory:

```
codecheck_output/
+-- codecheck.log          # Full debug log
+-- review_report.md       # Markdown review report
+-- review_report.json     # JSON review report
+-- fixed_code/            # Fixed code files
    +-- ...
```

## Config File Example

Edit `config.yaml`:

```yaml
provider: "deepseek-v4"

reviewer:
  model: "deepseek-v4-pro"
  temperature: 0.3
  timeout_seconds: 180

orchestrator:
  max_rounds: 5
  output_dir: "./my_results"
```
