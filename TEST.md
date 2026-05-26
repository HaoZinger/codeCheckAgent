# TEST.md — 测试策略与用例

## 测试策略

由于系统核心依赖 LLM API 调用，测试分为两层：

1. **单元测试**（可自动化）：覆盖编排逻辑、数据结构、Scanner、Reporter 等不依赖 LLM 的模块
2. **集成测试**（需手动/有条件执行）：需要真实 API Key 的端到端场景

### 可执行自动化测试（编排逻辑）

参见 `tests/` 目录（加分项）。使用 Mock 对象模拟 Agent 行为，验证：
- Scanner 正确扫描文件
- Orchestrator 正确管理轮次
- 收敛/未收敛逻辑正确
- Reporter 正确生成报告

---

## 测试用例

### 用例 1: Happy Path — 3 个问题全部修复

**场景描述**: 一段包含 3 个明显问题的 Python 代码，系统经过多轮迭代成功修复所有问题。

**输入** (`sample.py`):
```python
def divide(a, b):
    return a / b

def read_file(path):
    f = open(path, 'r')
    return f.read()

def get_user(users, name):
    for u in users:
        if u.name == name:
            return u
    return "Not found"
```

**操作步骤**:
1. 将上述代码保存到 `test_input/sample.py`
2. 运行 `python -m src.main ./test_input --max-rounds 3`
3. 观察终端实时输出

**预期结果**:
- Reviewer 发现至少 3 个问题（除零错误、文件未关闭、返回值类型不一致）
- Fixer 对每个问题进行修复
- Validator 确认修复有效
- 经过 1~3 轮后所有问题修复
- 报告显示 converged=true
- `fixed_code/sample.py` 包含修复后的代码

---

### 用例 2: Validator 拒绝场景 — 虚假修复

**场景描述**: Fixer 对某个问题只做了表面修改，Validator 能正确识别并触发下一轮。

**输入**:
```python
def process_data(data):
    result = data["key"].upper()   # 可能 KeyError
    return result

def calculate(x):
    return eval(x)                 # 安全风险: eval
```

**操作步骤**:
1. 保存代码到 `test_input/false_fix.py`
2. 运行 `python -m src.main ./test_input --max-rounds 3`
3. 观察 Validator 的输出

**预期结果**:
- Reviewer 发现 `eval` 安全问题和缺少 KeyError 处理
- Fixer 如果只添加了 `try-except` 但 `eval` 问题仍存在（或反过来），Validator 标记 `false_fix=true`
- 系统触发下一轮修复
- 最终报告中可看到被拒绝的修复记录

---

### 用例 3: 未收敛场景 — 达到最大轮次

**场景描述**: 代码中有一个复杂问题难以修复，达到最大轮次后正确输出残留问题。

**输入**:
```python
# 故意制造一个很难修复的逻辑问题
def find_median(arr):
    arr.sort()
    n = len(arr)
    if n % 2 == 0:
        return (arr[n//2] + arr[n//2 - 1]) / 2
    else:
        return arr[n//2 + 1]  # BUG: 应该是 n//2

def fibonacci(n):
    # 故意写一个指数复杂度的实现
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)  # 性能问题
```

**操作步骤**:
1. 保存代码并运行，设置 `--max-rounds 2`
2. 观察未收敛时的输出

**预期结果**:
- Reviewer 发现问题
- 经过 2 轮后仍未全部修复
- 系统输出 "已达最大轮次，以下问题未能修复"
- 报告中 `converged=false`
- 残留问题列表正确显示

---

### 用例 4: Agent 失败场景 — API 超时

**场景描述**: 模拟某个 Agent API 调用超时，系统不崩溃并提供降级行为。

**输入**: 任意代码文件

**操作步骤**:
1. 设置极短的 timeout（修改 config.yaml 中对应 agent 的 `timeout_seconds: 1`）
2. 或使用无效的 API 端点
3. 运行系统观察行为

**预期结果**:
- 系统不崩溃
- 打印清晰的错误信息 `[AgentName] ERROR: ...`
- 该轮次被跳过，继续输出已有结果
- 最终报告仍能生成（包含已完成的轮次信息）

---

### 用例 5: 边界输入

#### 5a: 空代码

**场景描述**: 目标目录中没有代码文件或代码文件内容为空。

**输入**: 空文件夹或仅有非代码文件（如图片）的文件夹

**操作步骤**:
1. `mkdir empty_dir`
2. `python -m src.main ./empty_dir`

**预期结果**:
- Scanner 提示 "No supported code files found"
- 系统正常退出，退出码 0
- 不调用任何 Agent

#### 5b: 超长代码

**场景描述**: 单个代码文件超过 `max_file_chars` 阈值。

**输入**: 一个超过 8000 字符的 Python 文件

**操作步骤**:
1. 生成一个超长代码文件
2. 运行系统

**预期结果**:
- Scanner 自动将文件分块处理
- 终端显示 "Large files split into N chunks"
- 审查正常进行

#### 5c: 语法正确但逻辑有问题的代码

**场景描述**: 代码语法完全正确但存在逻辑错误。

**输入**:
```python
def is_even(n):
    return n % 2 == 0

def process_list(items):
    # 逻辑错误：遍历时修改列表
    for i in range(len(items)):
        if items[i] < 0:
            items.remove(items[i])
    return items

def calculate_discount(price, is_member):
    if is_member:
        return price * 0.9
    else:
        return price * 1.1  # 非会员反而涨价？逻辑可疑
```

**操作步骤**:
1. 保存并运行

**预期结果**:
- Reviewer 能识别逻辑问题（遍历时修改列表、不合理的定价逻辑）
- Fixer 尝试修复
- Validator 验证修复后的逻辑是否正确
