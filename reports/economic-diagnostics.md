# EXP-002 Economic & Phase Diagnostics

## 1. 收益主要来自哪里？

本局从 `3,000` 起步，以 `11,408` 结束。现金账本得到总收入 `11,908`、总支出 `3,500`。收入来自出售收获物；未售出的库存不计入终局收益。

按作物的销售收入估算为：WHEAT ≈ 7,430 (60.62%), CARROT ≈ 4,826 (39.38%)。

这里的总收入由 `final cash - starting cash + expenditure` 得到，是现金账本值；分作物收入使用售出数量乘以下单前显示价格，因此只用于归因，动态订单内价格可能造成偏差。

## 2. 前期、中期、后期分别在做什么？

| Phase | Steps | Cash start→end | Spend | Crops(avg W/C) | Move | Productive | PASS | Utilization | Move/action |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| early | 0–179 | 3,000→4,028 | 1,040 | 8.1/7.5 | 776 | 239 | 197 | 83.75% | 3.25 |
| mid | 180–539 | 4,028→8,536 | 1,830 | 8.7/7.6 | 1807 | 492 | 131 | 94.61% | 3.67 |
| late | 540–719 | 8,536→11,408 | 630 | 6.2/5.0 | 700 | 188 | 323 | 73.33% | 3.72 |

前期集中购买 Wheat/Carrot 种子、每天雇工、铺满首块 5×5 土地并开始浇水；中期进入持续浇水、收获、补种和销售循环；后期停止形成新的长期资产，以收割清仓和处理剩余任务为主。

按 phase 的 farming action：

| Phase | Plant | Harvest | Water | Weed clear | Harvested WHEAT | Harvested CARROT |
|---|---:|---:|---:|---:|---:|---:|
| early | 53 | 22 | 151 | 12 | 39 | 35 |
| mid | 91 | 66 | 303 | 30 | 119 | 95 |
| late | 37 | 34 | 99 | 21 | 53 | 46 |

## 3. 最明显的三种资源浪费是什么？

1. **土地与现金同时闲置。** 全局 `idle cash ratio` 为 `100.00%`：其定义是仍有锁定象限时，现金足够购买下一象限的观测步占比。实际 expansion event 为 `0`，终局只解锁 `25` 格，其中 `25` 格仍为空，终局现金 `11,408`。
2. **移动开销偏高。** 全局每个 productive action 需要 `3.57` 次移动；phase 表显示了该比率在各阶段的变化。大量 worker turn 被用于重复走向水/收获任务。
3. **终盘劳动力闲置。** 最后 50 steps 有 `254` 次 PASS，平均每步 `5.18` 个 idle worker；同时仍保留 `2` 颗种子和 `11,408` 现金。

## 4. 当前最可能限制最终收益的三个瓶颈是什么？

1. **Expansion timing / economic strategy：** 从未 BUY_LAND，生产容量固定在首个 25 格象限，即使多数时间有能力支付下一象限也没有转化为资产。
2. **Crop selection / market diversification：** 实际生产和收入只来自 Wheat 与 Carrot；Tomato、Strawberry、Melon 和动物链均为 0。当前数据不能证明哪种替代组合最优，但能证明策略没有利用其他周期和价格曲线。
3. **Worker scheduling：** task diagnostics 显示 prevent_crop_loss、daily_water 和 harvest_ready 持续制造队列压力，且移动/有效动作比高；这会吞噬新增土地可能带来的劳动力容量。

重点 task reason 的 phase 证据：

| Phase | Reason | Generated | Assigned | Executed | Avg priority | Avg travel |
|---|---|---:|---:|---:|---:|---:|
| early | clear_weed | 274 | 100 | 12 | 55.0 | 2.36 |
| early | daily_water | 972 | 506 | 111 | 80.0 | 1.72 |
| early | harvest_ready | 381 | 98 | 23 | 70.0 | 1.62 |
| early | plant_carrot | 441 | 120 | 31 | 40.0 | 1.76 |
| early | plant_wheat | 336 | 68 | 22 | 40.0 | 1.12 |
| early | prevent_crop_loss | 123 | 123 | 40 | 100.0 | 1.40 |
| mid | clear_weed | 617 | 232 | 30 | 55.0 | 2.13 |
| mid | daily_water | 2039 | 1051 | 236 | 80.0 | 1.66 |
| mid | harvest_ready | 1184 | 404 | 67 | 70.0 | 2.03 |
| mid | plant_carrot | 879 | 180 | 53 | 40.0 | 1.38 |
| mid | plant_wheat | 474 | 139 | 38 | 40.0 | 1.42 |
| mid | prevent_crop_loss | 295 | 295 | 68 | 100.0 | 1.92 |
| late | clear_weed | 347 | 134 | 21 | 55.0 | 2.01 |
| late | daily_water | 694 | 343 | 75 | 80.0 | 1.75 |
| late | harvest_ready | 426 | 209 | 32 | 75.3 | 2.03 |
| late | plant_carrot | 386 | 69 | 23 | 40.0 | 1.14 |
| late | plant_wheat | 154 | 37 | 14 | 40.0 | 1.16 |
| late | prevent_crop_loss | 96 | 96 | 23 | 100.0 | 1.78 |

最后 50 steps：平均未用现金 `10,959.26`，平均空地 `22.38`，终局未收获 yield units `0`，高价值未执行 task appearances 为 `daily_water=84, harvest_ready=79`。

## 5. Planner efficiency 和 economic strategy 哪一个更值得优先优化？

**优先 economic strategy，随后再优化 planner。** 证据是当前 planner 已达到 86.59% 总体利用率，固定种子仍以 `11408 vs 3262` 获胜；但经济层从未扩地、只使用两种短周期作物，并以 `11,408` 现金结束。planner 的 3.57 movement/action 确实存在改善空间，但在现有 25 格生产上限下，单纯减少移动无法创造与扩地和资本再投资同等级的新增产能。这是诊断优先级判断，不是策略改动结论；下一实验仍需用单变量消融验证。

## 6. 本地 match score 与 Kaggle leaderboard score 是否相同？

**不同。** 本地 `11408` 是一场 720-turn episode 结束时的 bank coins，也是该局 reward；该局通过比较双方终局金币决定胜/负/平。Kaggle leaderboard 的 `354.2` 是跨多局对战的 skill rating：胜负结果和对手 rating 决定 rating 上下变化，官方明确说明金币差额不影响rating change；最终榜使用 Bradley–Terry tournament。

Kaggle 页面没有公开当前 live rating 更新的完整数值公式，因此精确解释 `354.2` 如何从每场结果计算得到应标记为 **unknown**，不能由 `11408` 换算。来源：[Kaggriculture Evaluation](https://www.kaggle.com/competitions/kaggriculture/overview#evaluation)。

完整逐步现金、资产、phase、worker 和 task 数据保存在 `reports/economic-diagnostics.json`。
