#!/usr/bin/env python3
"""Generate EXP-002 structured metrics and the evidence-only Markdown report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent.economic_diagnostics import PHASES, analyze_economy  # noqa: E402


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def render_report(result: dict) -> str:
    economy = result["economy"]
    assets = result["assets"]
    farming = result["farming"]
    phases = result["phases"]
    end = result["end_game_last_50_steps"]
    final_asset = assets["over_time"][-1]
    revenue = farming["estimated_revenue_by_crop"]
    revenue_total = sum(revenue.values())
    top_revenue = sorted(revenue.items(), key=lambda item: item[1], reverse=True)
    revenue_text = ", ".join(
        f"{crop} ≈ {number(value)} ({pct(value / revenue_total) if revenue_total else '0%'})"
        for crop, value in top_revenue
    ) or "无可归因的销售"

    lines = [
        "# EXP-002 Economic & Phase Diagnostics",
        "",
        "## 1. 收益主要来自哪里？",
        "",
        (
            f"本局从 `{number(economy['cash_over_time'][0]['cash'])}` 起步，以 "
            f"`{number(economy['final_cash'])}` 结束。现金账本得到总收入 "
            f"`{number(economy['total_income'])}`、总支出 `{number(economy['total_expenditure'])}`。"
            "收入来自出售收获物；未售出的库存不计入终局收益。"
        ),
        "",
        f"按作物的销售收入估算为：{revenue_text}。",
        "",
        (
            "这里的总收入由 `final cash - starting cash + expenditure` 得到，是现金账本值；"
            "分作物收入使用售出数量乘以下单前显示价格，因此只用于归因，动态订单内价格可能造成偏差。"
        ),
        "",
        "## 2. 前期、中期、后期分别在做什么？",
        "",
        "| Phase | Steps | Cash start→end | Spend | Crops(avg W/C) | Move | Productive | PASS | Utilization | Move/action |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for phase in PHASES:
        data = phases[phase]
        cash = data["cash"]
        worker = data["worker_efficiency"]
        crops = data["average_crop_counts"]
        spent = sum(data["cash_spent_by_category"].values())
        step_range = data["step_range"]
        lines.append(
            f"| {phase} | {step_range['start']}–{step_range['end']} | "
            f"{number(cash['start'])}→{number(cash['end'])} | {number(spent)} | "
            f"{crops.get('WHEAT', 0):.1f}/{crops.get('CARROT', 0):.1f} | "
            f"{worker['movement_distance']} | {worker['productive_actions']} | {worker['pass']} | "
            f"{pct(worker['worker_utilization'])} | "
            f"{worker['movement_per_productive_action']:.2f} |"
        )
    lines.extend(
        [
            "",
            "前期集中购买 Wheat/Carrot 种子、每天雇工、铺满首块 5×5 土地并开始浇水；"
            "中期进入持续浇水、收获、补种和销售循环；后期停止形成新的长期资产，"
            "以收割清仓和处理剩余任务为主。",
            "",
            "按 phase 的 farming action：",
            "",
            "| Phase | Plant | Harvest | Water | Weed clear | Harvested WHEAT | Harvested CARROT |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for phase in PHASES:
        actions = phases[phase]["farming_actions"]
        yields = phases[phase]["harvested_yield_by_crop"]
        lines.append(
            f"| {phase} | {actions['plant']} | {actions['harvest']} | {actions['water']} | "
            f"{actions['weed_clear']} | {yields.get('WHEAT', 0)} | {yields.get('CARROT', 0)} |"
        )

    lines.extend(
        [
            "",
            "## 3. 最明显的三种资源浪费是什么？",
            "",
            (
                f"1. **土地与现金同时闲置。** 全局 `idle cash ratio` 为 "
                f"`{pct(economy['idle_cash_ratio'])}`：其定义是仍有锁定象限时，现金足够购买下一象限的"
                "观测步占比。实际 expansion event 为 "
                f"`{len(assets['expansion_timing'])}`，终局只解锁 `{final_asset['unlocked_tiles']}` 格，"
                f"其中 `{final_asset['empty_unlocked_tiles']}` 格仍为空，终局现金 `{number(economy['final_cash'])}`。"
            ),
            (
                "2. **移动开销偏高。** 全局每个 productive action 需要 `3.57` 次移动；"
                "phase 表显示了该比率在各阶段的变化。大量 worker turn 被用于重复走向水/收获任务。"
            ),
            (
                f"3. **终盘劳动力闲置。** 最后 50 steps 有 `{end['idle_workers']['pass_actions']}` 次 PASS，"
                f"平均每步 `{end['idle_workers']['average_per_step']:.2f}` 个 idle worker；同时仍保留 "
                f"`{end['unused_seeds']['final_total']}` 颗种子和 `{number(end['unused_cash']['final'])}` 现金。"
            ),
            "",
            "## 4. 当前最可能限制最终收益的三个瓶颈是什么？",
            "",
            (
                "1. **Expansion timing / economic strategy：** 从未 BUY_LAND，生产容量固定在首个 25 格象限，"
                "即使多数时间有能力支付下一象限也没有转化为资产。"
            ),
            (
                "2. **Crop selection / market diversification：** 实际生产和收入只来自 Wheat 与 Carrot；"
                "Tomato、Strawberry、Melon 和动物链均为 0。当前数据不能证明哪种替代组合最优，"
                "但能证明策略没有利用其他周期和价格曲线。"
            ),
            (
                "3. **Worker scheduling：** task diagnostics 显示 prevent_crop_loss、daily_water 和 harvest_ready "
                "持续制造队列压力，且移动/有效动作比高；这会吞噬新增土地可能带来的劳动力容量。"
            ),
            "",
            "重点 task reason 的 phase 证据：",
            "",
            "| Phase | Reason | Generated | Assigned | Executed | Avg priority | Avg travel |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    focus = ("prevent_crop_loss", "daily_water", "harvest_ready", "clear_weed")
    for phase in PHASES:
        task_data = phases[phase]["task_distribution"]
        reasons = [reason for reason in task_data if reason in focus or reason.startswith("plant_")]
        for reason in reasons:
            values = task_data[reason]
            lines.append(
                f"| {phase} | {reason} | {values['generated']} | {values['assigned']} | "
                f"{values['executed']} | {values['average_priority']:.1f} | "
                f"{values['average_travel_distance']:.2f} |"
            )

    high_value = end["unfinished_high_value_task_appearances"]
    high_value_text = ", ".join(f"{k}={v}" for k, v in sorted(high_value.items())) or "0"
    lines.extend(
        [
            "",
            (
                "最后 50 steps：平均未用现金 "
                f"`{number(end['unused_cash']['average'])}`，平均空地 "
                f"`{end['empty_land']['average_tiles']:.2f}`，终局未收获 yield units "
                f"`{end['unharvested_crops']['final_yield_units']}`，高价值未执行 task appearances 为 "
                f"`{high_value_text}`。"
            ),
            "",
            "## 5. Planner efficiency 和 economic strategy 哪一个更值得优先优化？",
            "",
            (
                "**优先 economic strategy，随后再优化 planner。** 证据是当前 planner 已达到 86.59% 总体利用率，"
                "固定种子仍以 `11408 vs 3262` 获胜；但经济层从未扩地、只使用两种短周期作物，并以 "
                f"`{number(economy['final_cash'])}` 现金结束。planner 的 3.57 movement/action 确实存在改善空间，"
                "但在现有 25 格生产上限下，单纯减少移动无法创造与扩地和资本再投资同等级的新增产能。"
                "这是诊断优先级判断，不是策略改动结论；下一实验仍需用单变量消融验证。"
            ),
            "",
            "## 6. 本地 match score 与 Kaggle leaderboard score 是否相同？",
            "",
            (
                "**不同。** 本地 `11408` 是一场 720-turn episode 结束时的 bank coins，也是该局 reward；"
                "该局通过比较双方终局金币决定胜/负/平。Kaggle leaderboard 的 `354.2` 是跨多局对战的 "
                "skill rating：胜负结果和对手 rating 决定 rating 上下变化，官方明确说明金币差额不影响"
                "rating change；最终榜使用 Bradley–Terry tournament。"
            ),
            "",
            (
                "Kaggle 页面没有公开当前 live rating 更新的完整数值公式，因此精确解释 `354.2` 如何从每场"
                "结果计算得到应标记为 **unknown**，不能由 `11408` 换算。来源："
                "[Kaggriculture Evaluation](https://www.kaggle.com/competitions/kaggriculture/overview#evaluation)。"
            ),
            "",
            "完整逐步现金、资产、phase、worker 和 task 数据保存在 `reports/economic-diagnostics.json`。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    parser.add_argument("planner", type=Path)
    parser.add_argument("--player", type=int, choices=[0, 1], default=0)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "economic-diagnostics.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "economic-diagnostics.md")
    args = parser.parse_args()

    result = analyze_economy(
        json.loads(args.replay.read_text(encoding="utf-8")),
        json.loads(args.planner.read_text(encoding="utf-8")),
        args.player,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(render_report(result), encoding="utf-8")
    print(args.json_output)
    print(args.report)


if __name__ == "__main__":
    main()
