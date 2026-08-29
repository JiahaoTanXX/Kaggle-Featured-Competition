#!/usr/bin/env python3
"""Offline-first LLM replay analyst.

Without --call-api it only creates a review packet and deterministic diagnostics.
With --call-api it calls an OpenAI-compatible /chat/completions endpoint. This is
strictly a post-match tool and is never imported by the Kaggle submission.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def deterministic_diagnostics(summary: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    actions = summary.get("action_counts", {})
    total = sum(int(v) for v in actions.values()) or 1
    idle_ratio = int(actions.get("PASS", 0)) / total
    if summary.get("weed_count", 0):
        result.append({
            "evidence": f"终局有 {summary['weed_count']} 个 WEED",
            "hypothesis": "浇水或除草调度优先级不足",
            "experiment": "提高防损任务优先级，并与当前调度在相同种子、双座位下对比",
        })
    if idle_ratio > 0.45:
        result.append({
            "evidence": f"PASS 占全部单位动作的 {idle_ratio:.1%}",
            "hypothesis": "劳动力过剩或目标分配不足",
            "experiment": "对 hire_target 做 4/6/8 消融，比较净收益和动作利用率",
        })
    if sum(int(v) for v in summary.get("final_shed", {}).values()):
        result.append({
            "evidence": f"终局未出售库存 {summary['final_shed']}",
            "hypothesis": "最后一天清仓逻辑不完整",
            "experiment": "增加末日逐回合清仓，比较终局现金和未售库存",
        })
    if summary.get("margin", 0) < 0:
        result.append({
            "evidence": f"对局净胜差 {summary['margin']:.0f}",
            "hypothesis": "当前生产组合或市场时机弱于该对手",
            "experiment": "固定对手与种子，对作物组合、市场感知和对手感知分别做消融",
        })
    return result[:3]


def call_compatible_api(endpoint: str, model: str, api_key: str, system: str, summary: dict[str, Any]) -> dict[str, Any]:
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(summary, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--call-api", action="store_true")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    system = (ROOT / "analyst" / "system_prompt.md").read_text(encoding="utf-8")
    result: dict[str, Any] = {
        "mode": "offline",
        "source_summary": str(args.summary),
        "deterministic_diagnostics": deterministic_diagnostics(summary),
        "llm_prompt": {"system": system, "user": summary},
    }
    if args.call_api:
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise SystemExit(f"missing API key environment variable: {args.api_key_env}")
        result["mode"] = "llm"
        result["llm_analysis"] = call_compatible_api(args.endpoint, args.model, api_key, system, summary)

    output = args.output or args.summary.with_suffix(".analysis.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
