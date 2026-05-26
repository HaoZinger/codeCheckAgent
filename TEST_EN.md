# TEST.md ? Test Strategy & Cases

## Test Strategy

Since the system core depends on LLM API calls, testing is split into two layers:

1. **Unit tests** (automated): Cover orchestration logic, data structures, Scanner, Reporter ? modules independent of LLM
2. **Integration tests** (manual/conditional): End-to-end scenarios requiring a real API key

### Executable Automated Tests

See `tests/` directory. Uses Mock objects to simulate agent behavior, verifying:
- Scanner correctly scans files
- Orchestrator correctly manages rounds
- Convergence/non-convergence logic
- Reporter correctly generates reports

---

## Test Cases

### Case 1: Happy Path ? 3 Issues All Fixed

**Scenario**: Python code with 3 obvious issues, system fixes all after multiple rounds.

**Input** (`sample.py`):
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

**Steps**:
1. Save code to `test_input/sample.py`
2. Run `python src/main.py ./test_input --max-rounds 3`
3. Observe terminal real-time output

**Expected**:
- Reviewer finds at least 3 issues (division by zero, unclosed file, inconsistent return type)
- Fixer addresses each issue
- Validator confirms fixes are effective
- After 1-3 rounds all issues resolved
- Report shows `converged=true`
- `fixed_code/sample.py` contains fixed code

---

### Case 2: Validator Rejection ? False Fix

**Scenario**: Fixer makes a superficial change; Validator correctly identifies and triggers next round.

**Input**:
```python
def process_data(data):
    result = data["key"].upper()   # possible KeyError
    return result

def calculate(x):
    return eval(x)                 # security risk: eval
```

**Expected**:
- Reviewer finds `eval` security issue and missing KeyError handling
- If Fixer only adds try-except but leaves eval, Validator marks `false_fix=true`
- System triggers next round
- Final report shows rejected fix records

---

### Case 3: Non-Convergence ? Max Rounds Reached

**Scenario**: A complex issue resists fixing; max rounds reached with correct residual output.

**Input**:
```python
def find_median(arr):
    arr.sort()
    n = len(arr)
    if n % 2 == 0:
        return (arr[n//2] + arr[n//2 - 1]) / 2
    else:
        return arr[n//2 + 1]  # BUG: should be n//2

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)  # performance issue
```

**Steps**:
1. Save and run with `--max-rounds 2`

**Expected**:
- System outputs "Maximum rounds (2) reached"
- Report shows `converged=false`
- Residual issues correctly listed

---

### Case 4: Agent Failure ? API Timeout

**Scenario**: Simulate an agent API timeout; system does not crash and degrades gracefully.

**Input**: Any code file

**Steps**:
1. Set extremely short timeout (modify `timeout_seconds: 1` in config)
2. Or use an invalid API endpoint
3. Run and observe

**Expected**:
- System does not crash
- Clear error message: `[AgentName] ERROR: ...`
- Round skipped, existing results preserved
- Final report still generated (with completed rounds)

---

### Case 5: Edge Cases

#### 5a: Empty Code

**Input**: Empty directory or directory with no supported code files

**Expected**:
- Scanner: "No supported code files found"
- System exits cleanly, exit code 0
- No agent calls

#### 5b: Very Long Code

**Input**: A single file exceeding `max_file_chars` threshold

**Expected**:
- Scanner auto-chunks the file
- Terminal shows "Large files split into N chunks"
- Review proceeds normally

#### 5c: Syntactically Correct but Logically Wrong

**Input**:
```python
def is_even(n):
    return n % 2 == 0

def process_list(items):
    # logic error: modifying list while iterating
    for i in range(len(items)):
        if items[i] < 0:
            items.remove(items[i])
    return items

def calculate_discount(price, is_member):
    if is_member:
        return price * 0.9
    else:
        return price * 1.1  # non-members pay more? suspicious
```

**Expected**:
- Reviewer identifies logic issues (modifying while iterating, suspicious pricing)
- Fixer attempts fixes
- Validator checks corrected logic
