---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 第 1–4 步质检证据（对应 `internal/quality-checklist-2026-11-24.md`）

仓库路径均相对 `hvalo596/regime-adaptive-quant`；Step 1 在分支 `cursor/step1-state-construction-2dd4`，Step 2–4 在 `cursor/step2-real-futures-2dd4`（提交 `0ae4360`）。

## 第 1 步（回归）

| 项 | 结果 | 证据 |
|---|---|---|
| A1–A7 全量 | 通过（A8 为报告项） | 分支 step1：`artifacts/step1/acceptance.json`、`summary.md`；报告 `docs/step1-result-report.md`、`docs/step1-paper-report.md` |
| 共用代码改动后的回归 | 通过（逐位相同） | `scripts/check_regression_vs_step1.py`：两个世界上 tau_M、tau_R、s、D、C、毛收益、V 与第 1 步分支完全一致；运行记录在 `internal/step34-real-run-2026-11-24.md` |
| 缩小规模重跑（scale 0.15） | A1、A3–A6 通过；A2、A7 因小样本失败（M-A 的 P(τ≥1.28)=3.9% 来自 6 次空模拟；M-B 0.1 档 23 次切换比值 0.53，全量为 0.79） | `/tmp` 临时目录未入库，数字写在运行日志；A1 数字与原运行逐位相同。**未重跑 45 分钟全量**，这是已知缺口 |
| pytest | 通过 | 53 个（`tests/`），**2026-11-24 21:06 UTC** 协调员质检重跑全绿（44.8s） |
| summarize_step1 A1–A7 | 全部 pass | **2026-11-24 21:06 UTC** `python scripts/summarize_step1.py artifacts/step1` → acceptance.json 各 `pass: true` |

## 第 2 步（存在性）

| 项 | 证据 |
|---|---|
| ≥20 年窗口（商品 24.0 年；股指 10.3、国债 6.9 年的例外已说明） | `artifacts/step2/coverage_panel.csv`、`coverage_products.csv`；`docs/step2-result-report-v3.md` §2 |
| H0–H13、片段数（≥10 日片段 29/19/11/33）、§7.5 读法 | `artifacts/step2/hypotheses.csv`、`state_segments.csv`、`power_real_dims.csv`；报告 §4–§5 |
| 流水线级零分布、重校准 | `artifacts/step2/pipeline_null_theta_commodity.csv`、`calibration_commodity.json` |
| 试验账本（301 条） | `artifacts/step2/trial_ledger.csv` |
| 数据审计（28 个极端日、夜盘日期核实、日历） | `audit_extreme_days_*.csv`、`audit_night_session_*.csv`；报告 §4.6 |
| 诚实边界（功效；"未检出"≠"不存在"） | 报告 §1、§5 |

## 第 3 步（可预测性）

| 要求 | 证据 |
|---|---|
| 规则基准 → HMM → 持续性 → 变点逐层加 | 报告 §3、§5.1–§5.6；`artifacts/step3/model_comparison_commodity.csv`、`bocpd_commodity.csv` |
| 只用滤波概率；无前视 | 报告 §3；`tests/test_step34.py::test_increments_and_filter_are_causal`（篡改 t 后数据，z 与 p 不变） |
| HMM 低维（每条链 5 个参数；总计 10，远低于 240） | `src/regime_quant/step3.py`；报告 §3 |
| 标签对齐与重估稳定性 | `artifacts/step3/filter_fits_*.csv`（逐次重估、退化标记）；报告 §5.1（退化 90.5% / 95.2%） |
| 持续期 ÷ 检测延迟 | 报告 §4（合成直接测）、§5.5（真实：片段 ÷ 合成延迟，已声明为混合读数）；`best_case_delay_commodity.csv`、`switch_delay_summary.csv` |
| 检测延迟在合成数据上直接测 | `artifacts/step3/switch_delays.csv`、`switch_delay_summary.csv` |
| 流水线级零分布 / 假阳性 | `pipeline_null_filter.csv`、`pipeline_null_pvalues.csv`、`null_worlds_rates.csv` |
| 外生事件（保证金）提速 | `summary_commodity.json` → `margin_covariate_R_chain`（LR 0.40，p=0.68，仅 2021 年后） |
| ≥20 年与例外 | 报告 §2：商品 20.4 年；行业 6.8–16.0 年、股指 6.8 年、国债不可估计，原因已列 |
| 多重检验 | 报告 §5.2：六个统计量一族，Holm 后接近 1；主检验 1 个 |
| 边界结论而非口号 | 报告 §1、§6 |

## 第 4 步（可盈利性）

| 要求 | 证据 |
|---|---|
| 无状态基准（EW50、风险匹配的 VT、MOM/REV）与 EWA、近期表现 | 报告 §2、§5.1；`artifacts/step4/perf_commodity.csv`、`ewa_grid_commodity.csv` |
| 概率加权、熵惩罚、不动区间 | 报告 §2（FILT-SOFT/PEN/BAND）；`src/regime_quant/step4.py` |
| 信息价值三档（无状态/滤波/真值）与效率 | 报告 §4；`artifacts/step4/planted_info_value.csv`；真实数据只有①②两档，已声明 |
| 缩放 vs 重配（倾斜 + 择时）拆分 | 报告 §5.3（选择账户拆分）与缩放账户表；`selection_decomposition_*.csv`；恒等式测试 `tests/test_step34.py::test_strategy_identity_and_causality` |
| 成本网格 0/0.5/1/2×，预先固定 | 报告 §2；`perf_*.csv`；`STEP4_COST` |
| H9（状态对近期表现的增量） | 报告 §1(4)；`summary_commodity.json` |
| 主检验族 + 多重检验 | 报告 §5.2（4 个比较，Holm），§5.5（约 670 条比较全部记录，事后变体标注） |
| 假阳性（夏普比较在无条件倾斜下无效） | 报告 §4 第一张表；`artifacts/step3/null_worlds_rates.csv` |
| ≥20 年与例外 | 报告 §3：商品 20.4 年；其他面板短于 20 年，原因同第 3 步 |
| 边界结论 | 报告 §1、§6 |

## 已知缺口（如实）

1. 第 1 步全量回归（45 分钟）没有重跑；用逐位相同的比较与缩小规模的重跑代替。
2. 行业与股指面板的 Θ_c 没有重算流水线零分布；HMM 的 ν、先验无敏感性网格。
3. 国债面板第 3、4 步不可估计。
4. 席位（`fut_holding`）仍未取，H10 的席位签名没有数字（见第 2 步）。
5. GitHub PR 创建 403，只有分支与 compare 链接。
