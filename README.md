# CodeCheckAgent - 多 Agent 协作代码审查与自动修复系统

[English](README_EN.md) | **中文**

---

利用 AI 工具构建的命令行工具，实现多 Agent 协作的代码审查与自动修复。

## 环境要求

- **Python** 3.10+
- **LLM API Key**（OpenAI / DeepSeek / 兼容端点）

## 安装步骤

```bash
# 1. 进入项目目录
cd codeCheckAgent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
# OpenAI:
$env:OPENAI_API_KEY="sk-your-key-here"

# DeepSeek V4:
$env:DEEPSEEK_API_KEY="sk-your-deepseek-key"
```

## 快速开始

```bash
# 使用 OpenAI（默认）
python src/main.py ./test_sample

# 使用 DeepSeek
python src/main.py ./test_sample --provider deepseek-v4

# 查看所有支持的 providers
python src/main.py --list-providers
```

## 中断处理

运行过程中随时按 `Ctrl+C` 中断：

```
[INTERRUPTED] User cancelled the review process.
Generating partial report from completed rounds...
```

系统会自动保存已完成轮次的结果，生成部分报告和已修复的代码，不会丢失进度。

## 支持的 LLM Provider

| Provider | 模型 | 环境变量 | 说明 |
|----------|------|----------|------|
| `openai` | gpt-4o | `OPENAI_API_KEY` | OpenAI 官方 |
| `deepseek-v4` | deepseek-v4-pro | `DEEPSEEK_API_KEY` | DeepSeek V4 Pro |
| `custom` | 自定义 | `OPENAI_API_KEY` | 任意兼容端点 |

## 完整运行示例

```bash
# 使用 DeepSeek V4 Pro，5 轮迭代，指定输出目录
python src/main.py ./test_sample `
    --provider deepseek-v4 `
    --max-rounds 5 `
    --output ./results

# 使用自定义 API 端点
python src/main.py ./test_sample `
    --provider custom `
    --api-base https://your-endpoint.com/v1 `
    --model your-model-name `
    --api-key sk-xxx

# 查看详细日志
python src/main.py ./test_sample --provider deepseek-v4 --verbose
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `target` | - | 目标代码目录（必填） | - |
| `--provider` | `-p` | LLM provider 预设 | `openai` |
| `--config` | `-c` | YAML 配置文件路径 | `config.yaml` |
| `--output` | `-o` | 输出目录 | `./codecheck_output` |
| `--max-rounds` | `-r` | 最大迭代轮次 | 3 |
| `--api-key` | - | API Key（覆盖所有来源） | - |
| `--api-base` | - | API 基础 URL（覆盖预设） | - |
| `--model` | - | 模型名称（覆盖预设） | provider 默认 |
| `--verbose` | `-v` | 详细日志 | 关闭 |
| `--list-providers` | - | 列出所有 provider 预设 | - |

## 系统架构

```
用户输入(目录) → Scanner → Orchestrator → Reporter → 输出(报告+代码)
                    │            │
                    │   Ctrl+C → 优雅中断 + 部分报告
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
    Reviewer  →  Fixer  →  Validator
       (审查)     (修复)     (验证)
          └─────────┼─────────┘
                    │
              多轮迭代直到收敛
```

## 三个 Agent 角色

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **ReviewerAgent** | 分析代码，发现 bug/安全/性能/风格问题 | 代码文件 | 结构化问题清单 (JSON) |
| **FixerAgent** | 根据问题清单定点修复代码 | 原代码 + 问题清单 | 修复后代码 + diff |
| **ValidatorAgent** | 验证修复是否真实有效，识别虚假修复 | 原问题 + 修复后代码 | 逐条验证结果 |

## 输出产物

每次运行会在输出目录生成：

```
codecheck_output/
├── review_report.md      # Markdown 格式审查报告
├── review_report.json    # JSON 格式审查报告
└── fixed_code/           # 修复后的完整代码
    └── ...
```

## 配置文件示例

编辑 `config.yaml`：

```yaml
provider: "deepseek-v4"

deepseek-v4:
  model: "deepseek-v4-pro"
  temperature: 0.3
  timeout_seconds: 180

orchestrator:
  max_rounds: 5
  output_dir: "./my_results"
```

## 执行效果示例

```
PS F:\codeWorkspace\codeCheckAgent> python src/main.py ./test_sample --provider deepseek-v4 --model deepseek-v4-flash

============================================================
  Configuration
============================================================
  Provider:   deepseek-v4 (DeepSeek V4 Pro)
  API Base:   https://api.deepseek.com/v1
  Model:      deepseek-v4-flash
  JSON Mode:  ON
  Max Rounds: 4
  Output Dir: ./codecheck_output
============================================================

============================================================
  CodeCheckAgent - Multi-Agent Code Review System
  Press Ctrl+C to interrupt at any time
============================================================

[Scan] Scanning directory: F:\codeWorkspace\codeCheckAgent\test_sample
[Scan] Found 7 file(s)

------------------------------------------------------------
  Round 1/4
------------------------------------------------------------
  [Reviewer] Analyzing code... Found 34 issue(s) (41s)
  [Reviewer] Found 34 issues: 18 critical, 12 major, 4 minor
  [Fixer] Fixing 34 issue(s)... Produced 34 patch(es) (187s)
  [Validator] Validating fixes...
  [Summary] Round 1 Summary: 34 total | 33 fixed | 1 remaining

------------------------------------------------------------
  Round 2/4
------------------------------------------------------------
  [Reviewer] Analyzing code... Found 23 issue(s) (55s)
  [Reviewer] Found 23 issues: 4 critical, 13 major, 6 minor
  [Fixer] Fixing 1 issue(s)... Produced 1 patch(es)
  [Fixer] WARNING: fixed code identical to original ? no changes applied
  [Validator] Validating fixes...
  [Summary] Round 2 Summary: 34 total | 1 fixed | 0 remaining

  [OK] All issues resolved! Converged in 2 round(s).

============================================================
  Review Complete!
============================================================
  Log:        ./codecheck_output\codecheck.log
  Report:     ./codecheck_output\review_report.md
  Fixed Code: ./codecheck_output\fixed_code
  Issues:     34 found / 34 fixed
```