# Kaggriculture：长时序自主决策 Agent 与评测系统

## 当前实现

- 模块化 Agent：状态解析、任务调度、资源规划、动态市场、对手感知、安全回退
- 官方三基线评测：`pass`、`random`、`starter`，固定种子且交换双方座位
- 回放结构化：动作、市场订单、逐日资金、终局库存、作物、失败标签
- 四组消融：规则基线、动态市场、对手感知、关闭调度对照
- 轻量价值模型：离线训练、版本化权重、线上无训练依赖
- LLM Replay Analyst：赛外读取结构化回放，输出诊断与可验证实验；不会进入 Kaggle 提交

```text
observation
   ↓
state parser → crop/resource planner → task scheduler → safety guard → legal actions
      ↘ market & opponent model ↗

replay → structured summary → deterministic checks → optional LLM analyst → next experiment
```

## 快速开始

```bash
cd competitions/kaggriculture
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 单局与回放
.venv/bin/python scripts/run_match.py --opponent starter --seed 20260829

# 三个官方基线、双座位、多随机种子
.venv/bin/python scripts/tournament.py --seeds 3

# 四组消融
.venv/bin/python scripts/run_ablations.py --opponent starter --seeds 3

# 单元测试和环境集成测试
.venv/bin/python -m unittest discover -s tests -v

# 构建 submission.tar.gz
.venv/bin/python scripts/build_submission.py
```

完整 720 回合对局耗时明显高于短烟雾测试；正式比较至少使用 10 个种子并交换座位。生成结果位于 `reports/generated/`，原始回放位于 `replays/`，两者默认不纳入版本控制。

## LLM Replay Analyst

默认模式完全离线，只生成确定性诊断和可审阅的提示包：

```bash
.venv/bin/python analyst/llm_replay_analyst.py replays/latest.summary.json
```

如需调用 OpenAI-compatible API，显式增加 `--call-api` 并通过环境变量提供密钥：

```bash
OPENAI_API_KEY=... .venv/bin/python analyst/llm_replay_analyst.py \
  replays/latest.summary.json --call-api --model gpt-5-mini
```

LLM 输出只能生成假设，任何策略改动必须回到固定种子、双座位的对照实验验证。


## 项目文件

- `main.py`：Kaggle 顶层入口
- `src/kaggriculture_agent/`：策略、规划、市场、安全、价值模型与回放结构化
- `scripts/`：对局、锦标赛、消融、回放分析和提交打包
- `analyst/`：赛外 LLM 分析组件
- `tests/`：纯逻辑测试和官方环境集成测试
- `reports/`：实验协议、技术报告和简历描述

轻量价值模型的训练入口是 `scripts/train_value_model.py`。训练数据必须使用独立的回放种子生成，且导出的权重只有在 held-out 双座位实验通过后才能写入线上配置。
