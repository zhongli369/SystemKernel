# SystemKernel — 确定性 AI 路由与执行内核

**SystemKernel 不是一个框架，也不是一个库。它是一个确定性内核，负责路由 AI 能力、编排任务并强制执行验证。**

## 核心定位

SystemKernel 只做三件事：

1. **技能路由（Adapter）** — 将意图 + 上下文映射到最佳匹配技能。单一入口。确定性。无状态。
2. **任务编排（TaskSystem）** — 管理任务生命周期（backlog → active → done），支持步骤分解与状态跟踪。
3. **执行验证（ExecutionLoop）** — 对变更代码运行验证检查，带有限定重试（最多 2 次）。

没有 Agent 框架。没有概率猜测。没有影子逻辑。

## 快速开始

```python
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
from ExecutionLoop.loop import run, ExecutionRequest, ResolvedCapability

# 1. 路由意图 → 技能
binding = resolve(CapabilityRequest(
    intent="refactor",
    context="降低 utils/helpers.py 中的耦合度",
    source="my-project"
))
print(f"解析结果: {binding.skill_id} (置信度: {binding.confidence:.2f})")

# 2. 执行并验证
capability = ResolvedCapability(
    skill_id=binding.skill_id,
    confidence=binding.confidence
)

result = run(ExecutionRequest(
    capability=capability,
    target="utils/helpers.py",
    verification=("lint", "typecheck")
))

# 3. 检查结果
print(f"成功: {result.success}")
print(f"可修正: {result.correction_remaining}")
print(result.summary)
```

## 系统架构

```
请求 (意图 + 上下文)
        │
        ▼
┌──────────────────────┐
│  Adapter.resolve()   │  ← 技能路由（返回绑定，不执行）
└──────────┬───────────┘
           │ CapabilityBinding
           ▼
┌──────────────────────┐
│  TaskSystem          │  ← 任务创建、步骤分解、状态跟踪
└──────────┬───────────┘
           │ 带技能分配的任务
           ▼
┌──────────────────────┐
│  ExecutionLoop.run() │  ← 执行 + 验证（最多 2 次尝试）
└──────────┬───────────┘
           │ ExecutionResult
           ▼
         结果
```

**关注点分离：**

| 关注点 | 负责模块 | 禁止 |
|---------|-------|----------|
| 技能路由 | Adapter | 执行 |
| 技能匹配 | SkillSystem | 执行、持有状态 |
| 任务生命周期 | TaskSystem | 路由技能、执行 |
| 执行 + 验证 | ExecutionLoop | 路由技能、创建任务 |

## 公共 API

### Adapter（技能路由）

**导入路径:** `SkillsManagementSystem.core.adapter`

```python
from SkillsManagementSystem.core.adapter import (
    resolve, get_registry_info, get_skill_metadata,
    CapabilityRequest, CapabilityBinding, INTENT_HINTS
)

# 路由意图 + 上下文 → 技能绑定
binding = resolve(CapabilityRequest(
    intent="refactor",          # "refactor"|"decouple"|"stabilize"|"optimize"|"cleanup"|""
    context="描述信息",            # 自由文本目标描述
    source="调用方标识"            # 可选审计标签
))
# → CapabilityBinding(skill_id, confidence, alternatives, reason)

# 查看注册表（只读）
info = get_registry_info()
# → {"all_skills": [{"name": "...", ...}, ...]}

# 查看单个技能（只读）
meta = get_skill_metadata("skill-name")
# → {"name": "...", "package": "...", ...} 或 {}

# 可用的意图提示（只读参考）
INTENT_HINTS  # → {"refactor": "...", "decouple": "...", ...}
```

### ExecutionLoop（验证）

**导入路径:** `ExecutionLoop.loop`

```python
from ExecutionLoop.loop import (
    run, write_summary_to_task,
    ExecutionRequest, ResolvedCapability, ExecutionResult
)

capability = ResolvedCapability(skill_id="some-skill", confidence=0.85)

result = run(ExecutionRequest(
    capability=capability,
    target="path/to/changed/file.py",
    verification=("lint", "typecheck", "test")  # 命名检查或 shell 命令
))
# → ExecutionResult(success, corrected, verification_passed, attempt, correction_remaining, summary)

# 如果 result.correction_remaining 为 True：
#   调用方应用一次修正，然后以 correction_attempted=True 再次调用 run()
```

**命名验证检查：**

| 检查 | 命令 |
|-------|---------|
| `"lint"` | `ruff check .` |
| `"typecheck"` | `mypy .` |
| `"test"` | `pytest -q --tb=short` |

也接受自定义 shell 命令作为验证字符串。

### TaskSystem（任务编排）

**导入路径:** `TaskSystem.core.task_manager`

```python
from TaskSystem.core.task_manager import (
    create_task, start_task, complete_task,
    add_step, done_step, list_steps,
    add_context_log, task_show, query_tasks,
    suggest_skills_for_step, bind_skill
)

# 创建和管理任务
task = create_task("实现功能 X")
task = start_task(task["id"])
task = complete_task(task["id"])

# 步骤分解
add_step(task["id"], "设计接口")
add_step(task["id"], "编写测试")
done_step(task["id"], step_id=1)

# 技能绑定（通过 Adapter 路由）
skills = suggest_skills_for_step("重构这个函数")
bind_skill(task["id"], step_id=2, skill_name=skills[0])
```

TaskSystem 将技能选择委托给 Adapter，自身绝不路由技能。

## 合约规则（重要）

这些规则由 `architecture_guard.py` 强制执行。CRITICAL 级别的违规会阻止合并。

### 路由规则

- **单一入口：** `Adapter.resolve()` 是将意图路由到技能的**唯一**方式
- **禁止影子路由：** 不允许"先尝试 Adapter，不行再用自己的方式"的模式
- **内核内无回退：** 当 Adapter 返回空绑定时，SystemKernel 停止 — 不重试、不回退、不替换
- **禁止子进程路由：** 不得使用 `subprocess.run` / `subprocess.Popen` 进行技能路由
- **禁止 sys.path 操作：** 函数体内禁止 `sys.path.insert` / `sys.path.append`
- **禁止 importlib：** 禁止用于模块发现或路由
- **禁止直接访问注册表：** 所有元数据访问必须通过 Adapter 的 `get_registry_info()` / `get_skill_metadata()`

### 执行规则

- **ExecutionLoop 不得路由技能**或创建任务
- **ExecutionLoop 必须无状态** — 无缓存路由状态
- **最多 2 次尝试：** 初始 → 一次修正 → 停止。无无限循环。

### 意图映射规则

- **`INTENT_HINTS` 仅存在于 `adapter.py` 中** — 任何地方不得有副本
- **禁止 `if intent == "X": skill = "Y"` 决策链**
- **禁止 `match intent:` 模式**进行技能选择

## 安装

### 仓库位置

```
F:\Claude\SystemKernel\
```

### 导入路径设置

SystemKernel 设计为从同级项目使用。将工作区根目录添加到 Python 路径：

```python
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent  # 根据需要调整
if str(workspace) not in sys.path:
    sys.path.insert(0, str(workspace))

# 现在可以导入：
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
from ExecutionLoop.loop import run, ExecutionRequest, ResolvedCapability
```

工作区根目录（`F:\Claude\`）必须在 `sys.path` 上，以便 `SkillsManagementSystem` 和 `ExecutionLoop` 作为顶级包导入。

### 运行架构守卫

```bash
cd F:\Claude\SystemKernel
python architecture_guard.py           # 人类可读输出
python architecture_guard.py --json    # 机器可读输出
```

通过守卫意味着零个 CRITICAL 违规，稳定性得分 100/100。

## 仓库结构

```
SystemKernel/
├── SkillsManagementSystem/   ← SkillSystem（路由引擎 + 注册表）
│   └── core/
│       └── adapter.py        ← 唯一的公共路由入口
├── TaskSystem/               ← 任务编排 + 状态跟踪
│   └── core/
│       └── task_manager.py   ← 任务 CRUD、步骤、技能绑定
├── ExecutionLoop/            ← 执行 + 验证工具
│   └── loop.py               ← 有限验证循环（最多 2 次尝试）
├── architecture_guard.py     ← 合约执行（静态分析）
├── CLAUDE.md                 ← 调用协议规范
├── README.md                 ← 英文入口文档
├── README_CN.md              ← 中文入口文档
└── examples/
    └── basic_usage.py        ← 最小端到端示例
```

## 稳定性声明

**SystemKernel v1.0 已冻结。**

- 公共 API 签名（Adapter、ExecutionLoop、TaskSystem）稳定，不会更改
- 仅允许附加性更改（新技能、新意图提示、新验证检查）
- 未经冻结覆盖程序，不得进行结构性修改
- 冻结覆盖程序要求：记录理由、更新 `architecture_guard.py`、全面重新验证、升级 CLAUDE.md 版本

SkillSystem 的内部实现（匹配算法、注册表结构、别名解析）可以演进，只要公共合约保持不变。

### 不可变边界

- Adapter 是技能选择、元数据和路由的**唯一**入口
- SkillSystem 内部（routing_pipeline、capability_registry 等）是**私有的**
- ExecutionLoop 是**纯粹的** — 不做路由决策，不创建任务
- 不允许新的层、入口点或替代路由系统

### 允许演进

- SkillSystem 内部逻辑改进（routing_engine）
- 注册表添加（新技能）
- Adapter `INTENT_HINTS` 添加（仅附加，不得删除或重命名）

## 版本

SystemKernel: **v1.0 (FROZEN)** | 协议规范: **v1.0** | 稳定性得分: **100/100**
