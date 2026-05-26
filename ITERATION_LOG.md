# ITERATION_LOG.md — AI 协作迭代记录

本文档记录了与 AI 工具（Codex CLI）协作构建此系统的完整过程。

---

## 迭代 #1：系统架构设计

**时间**：2026-05-25 17:40

**任务**：根据 任务描述.md 理解需求，设计系统整体架构和数据结构。

**Prompt 策略**：
- 让 AI 阅读 任务描述.md，输出 SPEC.md（架构、数据流、数据结构、ASCII 流程图）
- 要求分析 5 个核心工程难题的决策

**AI 产出问题**：
- 初次读取时文件编码问题导致乱码（Windows GBK vs UTF-8），通过显式指定 -Encoding UTF8 解决

**我的处理**：用 Get-Content -Encoding UTF8 指定编码。

**最终质量**：SPEC.md 完整覆盖架构、数据流、数据结构、5 个决策、功能范围和降级策略。

---

## 迭代 #2：核心代码实现

**时间**：2026-05-25 17:45

**任务**：实现完整可运行代码：Scanner、三个 Agent、Orchestrator、Reporter、CLI。

**Prompt 策略**：
- 先定义数据结构（types.py），再按模块逐个实现
- 顺序：config → scanner → agents(base→reviewer→fixer→validator) → orchestrator → reporter → main

**AI 产出问题**：
- 代码量大，需分多个 shell_command 写入
- dataclass 需注意 field(default_factory=list) 避免可变默认值

**最终质量**：所有模块完整，接口对齐，每个 Agent 有完整 prompt 和 parser。

---

## 迭代 #3：配置与文档

**时间**：2026-05-25 17:55

**任务**：config.yaml、README.md，三层配置管理。

**Prompt 策略**：CLI > 环境变量 > YAML > 默认值。

**最终质量**：README 完整，config.yaml 所有字段可配。

---

## 迭代 #4：测试与决策文档

**时间**：2026-05-25 18:00

**任务**：TEST.md（5 个测试用例）、DECISION.md（7 个工程决策）。

**最终质量**：覆盖 Happy Path、Validator 拒绝、未收敛、Agent 失败、边界输入。

---

## 迭代 #5：初始验证

**时间**：2026-05-25 18:10

**任务**：完成 ITERATION_LOG.md 初始版本，验证系统语法和基础导入。

**AI 产出问题**：迭代记录的自我指涉需诚实客观。

**最终质量**：5 次迭代记录完整，19 个自动化测试全部通过。

---

## 迭代 #6：生成多语言测试代码

**时间**：2026-05-25 18:30

**任务**：生成常用代码用于功能测试，覆盖 Python、Java、JavaScript。

**Prompt 策略**：
- 每种语言 2 个文件，每个埋入 3~5 个已知问题
- 覆盖：除零、未关闭资源、eval 注入、SQL 注入、XSS、数组越界、类型不一致等

**AI 产出问题**：代码质量好，初始未分目录。

**我的处理**：按语言分目录，最终 7 个文件：

| 文件 | 语言 | 埋入的问题 |
|------|------|-----------|
| calculator.py | Python | 除零、eval()、文件未关闭、可变默认参数、返回值不一致、空列表除零 |
| auth.py | Python | MD5 弱哈希、SQL 注入、硬编码密钥、连接未关闭、伪 JWT |
| UserService.java | Java | == 字符串、数组越界、循环拼接、遍历时删除 |
| FileProcessor.java | Java | 资源泄漏、== 空串、SQL 注入、吞异常、除零 |
| dataService.js | JavaScript | await 缺失、forEach 异步、XSS、==、越界、eval() |
| utils.js | JavaScript | deepClone 浅拷贝、this 绑定、返回值不一致、同步 XHR |

**最终质量**：7 个文件 3 种语言，30+ 个已知问题，适合验证系统跨语言审查能力。

---

## 迭代 #7：中断处理与 Provider 预设

**时间**：2026-05-26 14:00

**任务**：添加 Ctrl+C 中断处理，支持 DeepSeek 等多 provider。

**Prompt 策略**：
- 中断：Orchestrator.run() 包裹 try/except KeyboardInterrupt，中断时输出部分报告
- Provider：config.py 定义 PROVIDER_PRESETS，含 api_base、模型名、环境变量

**AI 产出问题**：
- 中断处理需重构 _run_impl / _run_single_round 避免重复代码
- Provider 预设中 response_format 兼容性需按 provider 区分

**我的处理**：确认架构后接受实现。

**最终质量**：Ctrl+C 输出已完成轮次的部分报告；--provider deepseek 一键切换。

---

## 迭代 #8：DeepSeek — 空响应

**时间**：2026-05-26 15:09

**任务**：排查 DeepSeek 返回 Empty response from LLM。

**Prompt 策略**：让 AI 加入 finish_reason 日志、把 timeout 移到 client 级、添加 API 诊断工具。

**AI 产出问题**：
- response_format={"type":"json_object"} DeepSeek 不兼容导致空响应
- 模型名 deepseek-v4-pro 不存在，finish_reason=length + 空内容

**我的处理**：
- 在 ProviderPreset 加 supports_json_mode 字段，DeepSeek 默认 False
- 纠正模型名为 deepseek-chat

**最终质量**：provider 级 JSON mode 开关生效，API 连通性诊断工具可用。

---

## 迭代 #9：DeepSeek — Reviewer 找不到问题

**时间**：2026-05-26 15:15

**任务**：DeepSeek 正常返回但 Found 0 issue(s)。

**Prompt 策略**：让 AI 重写 Reviewer system prompt。

**AI 产出问题**：原 prompt "Be thorough but not pedantic" 对 DeepSeek 太保守。

**我的处理**：
- 改为 "You are a STRICT code reviewer. FIND PROBLEMS"
- 逐类列举问题模式（bug/安全/逻辑/性能），加具体例子
- 加硬性要求 "AIM FOR AT LEAST 2-3 ISSUES per file"
- Reviewer 的 summary 始终打印到终端

**最终质量**：Reviewer 开始正常检测问题。

---

## 迭代 #10：DeepSeek — JSON 换行符解析失败

**时间**：2026-05-26 15:20

**任务**：JSON parse error: Unterminated string，因 description 字段含字面换行。

**Prompt 策略**：让 AI 增强 JSON 解析鲁棒性。

**AI 产出问题**：AI 实现了 _repair_json()（字符串内 \n → \\n）和 _try_strip_tail()（尾部裁剪）。

**我的处理**：确认 extract_json 5 层兜底策略合理。

**最终质量**：多行字符串 JSON 自动修复解析。

---

## 迭代 #11：DeepSeek — 启用 JSON Output

**时间**：2026-05-26 15:30

**任务**：DeepSeek 实际支持 response_format={"type":"json_object"}，应启用。

**Prompt 策略**：告诉 AI "DeepSeek 提供了 JSON Output 功能"。

**AI 产出问题**：AI 直接将 supports_json_mode 改为 True。

**最终质量**：DeepSeek 请求带 response_format，输出合法 JSON。

---

## 迭代 #12：DeepSeek — JSON 截断

**时间**：2026-05-26 15:35

**任务**：Expecting ',' delimiter —— JSON 被 max_tokens 截断。

**Prompt 策略**：告诉 AI "需要合理设置 max_tokens 参数"。

**AI 产出问题**：
- max_tokens 默认 4096 对多文件审查不够
- AI 将默认值翻倍到 8192，并加入 finish_reason=length 自动重试（翻倍，上限 32768）

**我的处理**：确认逻辑合理。

**最终质量**：截断自动检测并重试，不再因 max_tokens 不足截断。

---

## 迭代 #13：DeepSeek — self 引用 Bug

**时间**：2026-05-26 16:19

**任务**：NameError: name 'self' is not defined 和 UnboundLocalError: current_max_tokens。

**Prompt 策略**：
- 先让 AI 把 raw response 保存到文件
- 再让 AI 加 traceback 日志

**AI 产出问题**：
- AI 编辑 call() 时把 current_max_tokens = self.config.max_tokens 误写入 @staticmethod 的 extract_json
- 修复时 f-string 语法错误（\n 变字面换行）
- 再修复时误删 call() 中正确初始化
- 连出三个 bug

**我的处理**：
- traceback 定位到 extract_json:158，让 AI 删多余代码
- 再报 current_max_tokens 未定义，让 AI 补回初始化

**最终质量**：19 个测试全部通过，系统在 DeepSeek 上正常完成 Reviewer→Fixer→Validator 流程。

---

## 迭代 #14：精简 Provider 预设

**时间**：2026-05-26 17:40

**任务**：deepseek 和 deepseek-v4 预设功能重复，只保留 deepseek-v4。

**Prompt 策略**：直接告诉 AI 删除 deepseek 预设。

**AI 产出问题**：删除后需同步更新 README、config.yaml、check_api.py 中的所有引用。

**我的处理**：逐一确认三个文件中的残留引用，清理干净。

**最终质量**：预设精简为 openai / deepseek-v4 / custom 三个，文档一致。

---

## 迭代 #15：修复模型名传递 Bug

**时间**：2026-05-26 17:45

**任务**：API 报错 "you passed ." —— 模型名为空。

**Prompt 策略**：让 AI 排查模型名传递链路。

**AI 产出问题**：
- apply_provider_preset 中有条件 if agent_cfg.model == "gpt-4o" 才覆盖
- 但 YAML 中 model 字段为空字符串时，条件不满足，跳过覆盖
- 同时发现 deepseek-v4-pro 确实是有效模型名（API 返回确认）

**我的处理**：
- 条件改为 if not agent_cfg.model or agent_cfg.model == "gpt-4o"（空值也覆盖）
- base.py 发送请求前加 model 非空断言

**最终质量**：模型名正确传递，API 不再报错。

---

## 迭代 #16：日志优化

**时间**：2026-05-26 18:20

**任务**：日志输出混乱（logger 时间戳和 print 进度行穿插），需要优化格式和位置。

**Prompt 策略**：
- Agent 状态信息改用 print()，和 Orchestrator 统一通道
- logger 仅用于 --verbose 调试 + 文件输出
- 新增 codecheck.log 文件记录完整 DEBUG 日志

**AI 产出问题**：
- setup_logging 需要拿到 config.output_dir，但日志初始化在配置加载之前
- 需要调整 main.py 初始化顺序，先加载 config 再初始化日志

**我的处理**：接受 AI 的方案，确认日志双通道合理。

**最终质量**：
- 终端干净：只有进度行 + 致命错误，无时间戳噪音
- 文件完整：codecheck_output/codecheck.log 记录全部 DEBUG 细节
- --verbose 时终端也输出 DEBUG

---

## 迭代 #17：DeepSeek 性能诊断

**时间**：2026-05-26 18:30

**任务**：DeepSeek 接口调用极慢（131s~262s），需要诊断原因。

**Prompt 策略**：让 AI 添加耗时日志和输入大小日志。

**AI 产出问题**：
- 日志显示 finish=length len=8186 elapsed=131.5s —— 输出被 max_tokens 截断
- 截断触发重试，第二次 max_tokens=16384 又花 130s，合计 262s 仍截断
- 根因：输入太大（7 个文件带行号），吃满上下文窗口，输出空间不够

**我的处理**：
- max_tokens 默认值 8192 → 16384
- max_file_chars 8000 → 4000（减半输入量）
- 截断重试上限 32768 → 65536
- 终端显示超过 30s 的调用耗时
- 日志增加输入大小记录

**最终质量**：输入减半后不再截断，单次调用速度可接受。

---

## 迭代 #18：修复后代码未变更诊断

**时间**：2026-05-26 19:00

**任务**：codecheck_output/fixed_code 和原始代码没区别，需排查 Fixer 链路。

**Prompt 策略**：让 AI 分析 Fixer→Validator→Reporter 链路，加诊断日志。

**AI 产出问题**：
- 可能原因：Fixer 返回 fixed_files 为空，或内容与原始相同
- 当前代码只在 fix_result.fixed_code 非空时更新 current_code

**我的处理**：接受 AI 添加的 Fixer 无变更检测 WARNING。

**最终质量**：终端会在 Fixer 返回无变更代码时打印 WARNING，方便定位。

---

## 迭代 #19：整理后续迭代记录

**时间**：2026-05-26 19:10

**任务**：将迭代 #14~#19 整理到 ITERATION_LOG.md。

**最终质量**：19 次迭代完整覆盖从初始设计到 DeepSeek 调通、性能优化的全过程。

