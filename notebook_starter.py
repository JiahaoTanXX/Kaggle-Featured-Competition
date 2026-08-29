# %% [markdown]
# # Kaggriculture：模块化长时序决策 Agent
#
# 本 Notebook 只负责打包、烟雾测试和生成提交物。核心实现位于附带的
# `src/kaggriculture_agent/`，赛外 LLM Replay Analyst 不进入线上 Agent。

# %%
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from kaggle_environments import make
from main import agent

# %% [markdown]
# ## 固定种子烟雾测试

# %%
env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 20260829}, debug=True)
env.run([agent, "starter"])
[(state.reward, state.status) for state in env.steps[-1]]

# %% [markdown]
# ## 完整赛季验证

# %%
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 20260829}, debug=True)
env.run([agent, "starter"])
assert all(state.status == "DONE" for state in env.steps[-1])
[(state.reward, state.status) for state in env.steps[-1]]

# %% [markdown]
# ## 构建提交包

# %%
subprocess.run([sys.executable, "scripts/build_submission.py"], check=True)
