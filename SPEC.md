# SPEC.md — 多 Agent 协作代码审查与自动修复系统规格文档

## 1. 系统架构

### 1.1 总体架构

```
┌─────────────────────────────────────────────────────┐
│                     CLI 入口 (main.py)                │
│                 参数解析 / 配置加载 / 启动              │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                  Scanner (scanner.py)                │
│            扫描目标文件夹 → 收集代码文件列表             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              Orchestrator (orchestrator.py)           │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │              多轮迭代循环                      │   │
│   │                                             │   │
│   │  Round N:                                   │   │
│   │    ReviewerAgent ──→ IssueList               │   │
│   │         │                                    │   │
│   │         ▼                                    │   │
│   │    FixerAgent ──→ FixedCode                   │   │
│   │         │                                    │   │
│   │         ▼                                    │   │
│   │    ValidatorAgent ──→ ValidationResult        │   │
│   │         │                                    │   │
│   │         ▼                                    │   │
│   │    [收敛?] ──Yes──→ 输出结果                   │   │
│   │         │                                    │   │
│   │         No (未达上限)                          │   │
│   │         │                                    │   │
│   │         └──→ 下一轮                            │   │
│   └─────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              Reporter (reporter.py)                  │
│       生成审查报告 (JSON/Markdown) + 输出修复后代码     │
└─────────────────────────────────────────────────────┘
```

### 1.2 Agent 角色与数据流

```
输入代码 ──→ ReviewerAgent ──→ IssueList (结构化JSON)
                                      │
                                      ▼
                                FixerAgent ──→ FixedCode + PatchInfo
                                      │
                                      ▼
                              ValidatorAgent ──→ ValidationResult
                                      │
                            ┌─────────┴─────────┐
                            │                   │
                        已全部修复           存在未修复
                            │                   │
                            ▼                   ▼
                        输出结果           进入下一轮(或超限输出)
```

## 2. 数据结构定义

### 2.1 代码文件

```python
@dataclass
class CodeFile:
    path: str           # 相对路径
    content: str        # 文件内容
    language: str       # 编程语言 (从扩展名推断)
```

### 2.2 ReviewerAgent 输出: IssueList

```python
@dataclass
class Issue:
    id: str                    # 唯一标识, 如 "ISS-001"
    file: str                  # 文件路径
    line_start: int            # 起始行号
    line_end: int              # 结束行号
    severity: str              # "critical" | "major" | "minor" | "info"
    category: str              # "bug" | "security" | "style" | "performance" | "logic"
    title: str                 # 问题简述
    description: str           # 详细描述
    suggestion: str            # 修复建议
    status: str                # "open" | "fixed" | "false_fix"

@dataclass
class IssueList:
    issues: list[Issue]
    summary: str               # 本轮审查摘要
```

### 2.3 FixerAgent 输入/输出

```python
# 输入
@dataclass
class FixRequest:
    original_code: list[CodeFile]
    issues: IssueList

# 输出
@dataclass
class FixResult:
    fixed_code: list[CodeFile]    # 修复后的代码文件
    patches: list[PatchInfo]      # 每个修复对应的patch信息

@dataclass
class PatchInfo:
    issue_id: str
    file: str
    diff: str                     # unified diff 格式
```

### 2.4 ValidatorAgent 输入/输出

```python
# 输入
@dataclass
class ValidationRequest:
    original_issues: IssueList
    fixed_code: list[CodeFile]
    patches: list[PatchInfo]

# 输出
@dataclass
class ValidationResult:
    results: list[IssueValidation]    # 每个issue的验证结果
    summary: str

@dataclass
class IssueValidation:
    issue_id: str
    resolved: bool                    # 是否真正解决
    reason: str                       # 判断理由
    false_fix: bool                   # 是否为虚假修复
```

### 2.5 轮次结果

```python
@dataclass
class RoundResult:
    round_num: int
    issues_found: int
    issues_fixed: int
    issues_remaining: int
    issues: list[Issue]
    patches: list[PatchInfo]
    validation: ValidationResult
```

### 2.6 最终审查报告

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

## 3. 五个核心工程难题的决策

### 难题1: LLM 输出如何保证结构化？

**选择**: 使用 OpenAI 的 `response_format: {"type": "json_object"}` 或 Function Calling，配合严格的 JSON Schema 约束输出格式。

**理由**: 直接约束 JSON 输出比解析自然语言更可靠。配合 Pydantic 进行二次校验，解析失败时触发重试。

**局限**: 即使是 JSON 模式，LLM 仍可能输出不符合 schema 的内容，需要 fallback 解析 + 重试。

### 难题2: Fixer 如何精确修改代码而不引入新问题？

**选择**: 让 Fixer 输出完整修复后的文件内容 + 每个修改的 unified diff。通过 system prompt 严格约束"只修改 issue 中标记的位置"，并要求输出每个修改的 diff 自证。

**理由**: 输出完整文件确保代码完整性，输出 diff 便于 Validator 审查和报告展示。

**局限**: LLM 可能过度修改（如自动格式化），需要通过 Validator 二次把关。

### 难题3: Validator 如何识别"虚假修复"？

**选择**: Validator 接收原始 issue、原始代码片段、修复后的代码片段三者，要求逐条对比并给出判断理由。Prompt 中明确定义"虚假修复"的典型模式（如只改注释、重命名变量但不改逻辑、添加无用代码等）。

**理由**: 三者对比 + 强制输出判断理由能有效提高识别准确率。

**局限**: 对于复杂逻辑问题，LLM 判断可能不准确，存在误判风险。

### 难题4: 多轮迭代中上下文如何管理？

**选择**: 每轮独立调用 Agent，不保留历史对话。通过结构化数据（IssueList 的状态字段）传递上下文。每个 Agent 的输入只包含：当前代码 + 当前 Issue 状态。

**理由**: 避免上下文膨胀导致的 token 浪费和注意力衰减。结构化数据比对话历史更精确。

**局限**: Agent 无法学习前几轮的"经验"，可能重复犯错。未来可引入精简的 round summary。

### 难题5: 如何处理不同编程语言？

**选择**: 语言无关设计——Scanner 通过文件扩展名识别语言，Agent prompt 中告知语言类型。不对特定语言做特殊处理。

**理由**: 保持系统通用性，LLM 本身支持多语言。

**局限**: 不同语言的最佳实践差异大，通用 prompt 效果不如专用 prompt。未来可扩展语言特定的审查规则。

## 4. 功能范围

### 必须完成项 [必须]

| 功能 | 状态 |
|------|------|
| ReviewerAgent: 分析代码输出结构化问题清单 | ✅ |
| FixerAgent: 根据问题清单定点修复 | ✅ |
| ValidatorAgent: 验证修复+识别虚假修复 | ✅ |
| 多轮迭代: Reviewer→Fixer→Validator 循环 | ✅ |
| 收敛条件: 全部修复或达到最大轮次(默认3轮) | ✅ |
| 未收敛处理: 列出残留问题 | ✅ |
| 每轮实时进度输出 | ✅ |
| 最终结构化审查报告 (Markdown) | ✅ |
| 最终输出修复后完整代码 | ✅ |
| 单Agent失败不崩溃+错误信息 | ✅ |

### 可选完成项 [可选]

| 功能 | 状态 |
|------|------|
| 动态优先级: 按严重程度排序 | ❌ (时间有限，固定按severity排序) |
| 上下文压缩: 精简历史传递 | ❌ (当前设计中每轮独立) |
| diff格式展示每轮代码变化 | ✅ |
| 审查报告导出为HTML | ❌ (Markdown已足够) |
| Agent重试机制 | ✅ |
| 可执行自动化测试 | ✅ (编排逻辑测试) |

### 不做的事情

- **不提供 Web UI**：专注 CLI 工具，降低复杂度
- **不支持 Git 集成**：直接操作文件，不依赖 Git
- **不做实时协作**：单用户单次运行的批处理模式
- **不做增量审查**：每次全量审查，不追踪变更历史

## 5. 已知缺陷与降级策略

### 缺陷1: LLM输出的不确定性
- **降级**: 每个Agent调用最多重试3次，输出仍不合格时标记为Agent失败，跳过该轮
- **影响**: 可能导致部分问题未被审查或修复

### 缺陷2: 大文件/多文件场景的token限制
- **降级**: 文件超过阈值(默认8000字符)时进行分块处理
- **影响**: 跨块的关联问题可能遗漏

### 缺陷3: 虚假修复的漏判
- **降级**: Validator如给出模糊判断，默认标记为"未修复"，进入下一轮
- **影响**: 可能延长迭代轮次，但不会放过真实问题

### 缺陷4: 缺乏对特定语言深度规则的了解
- **降级**: 依赖LLM自身知识，不做语言特定规则注入
- **影响**: 对特定语言的审查质量依赖LLM训练数据

### 缺陷5: 无增量修复能力
- **降级**: 每轮都重新输出完整代码，成本较高
- **影响**: token消耗大，适合中小型代码审查场景
