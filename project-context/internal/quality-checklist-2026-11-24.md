# 第 1–4 步质检清单（协调员盯盘用）

> 工人每完成一步勾选并附证据路径；协调员验收前不宣布该步完成。依据：`docs/kai-dims-and-experiment-steps.md`、`docs/state-construction.md`、`docs/step1-plan-v2.md` A1–A8。
> **逐条证据详见** [`internal/step1-4-quality-evidence-2026-11-24.md`](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/step1-4-quality-evidence-2026-11-24.md)。

## 第 1 步（回归，改共用代码后必跑）

| # | 项 | 通过 | 证据 |
|---|---|---|---|
| A1–A7 | acceptance | ☑ | `artifacts/step1/acceptance.json`（2026-11-24 21:06 UTC 重跑 `summarize_step1.py`：A1–A7 `pass: true`） |
| A8 | 报告 | ☑ | `docs/step1-result-report.md`、`docs/step1-paper-report.md` |
| pytest | 全绿 | ☑ | 53 passed，44.8s（`cd repo && pytest -q`，2026-11-24 21:06 UTC） |

## 第 2 步（存在性，kai §第2步）

| # | 项 | 通过 | 证据 |
|---|---|---|---|
| 2.1 | ≥20y 覆盖表 + 剔除原因 | ☑ | `artifacts/step2/coverage_panel.csv`、`coverage_products.csv`；报告 v3 §2（商品 24.0y；股指/国债/行业例外） |
| 2.2 | 收盘到收盘、换月、涨跌停/换月/股指限制旗标 | ☑ | `src/regime_quant/data/roll.py`、`flags.py`；`audit_*.csv`；报告 §2–§4.6 |
| 2.3 | M/R/C 策略 L/H；滞回 1.28/0.5；min dwell | ☑ | `config.py` StateParams；`statevars.py`；报告 §3 |
| 2.4 | Θ_c 中心化；检验对象 D；H0–H13 | ☑ | `inference.py`；`hypotheses.csv`（H0–H8+occupancy）；H9→第4步；H10–H13 报告 §4.3–4.4 + H13 第1步 |
| 2.5 | 块自助（片段）；片段数；功效不足标注 | ☑ | `state_segments.csv`（29/19/11/33）；`power_real_dims.csv`；报告 §1、§5 |
| 2.6 | 非定义预测（OI/成交/H10/H11） | ☑* | `nondefining_signatures.csv`、`llorente_b2.csv`、H11 `fut_settle`；**缺口**：`fut_holding` 未取 → 席位签名无数字；未跑 `--all-days-extras` |
| 2.7 | trial_ledger + 流水线零分布 | ☑ | `trial_ledger.csv`（301）；`pipeline_null_theta_commodity.csv`；summary `p_pipeline=0.84` |
| 2.8 | v3 报告 §7.5 金融读法 C2/C3/C4 | ☑ | `docs/step2-result-report-v3.md` §1、§5 |

**Step 2 交付**：☑ `docs/step2-result-report-v3.md`

## 第 3 步（可预测性，kai §第3步）

| # | 项 | 通过 | 证据 |
|---|---|---|---|
| 3.1 | 真实数据规则基准延迟/驻留 | ☑ | `spells_commodity.csv`（δ^M 均值片段 93d、δ^R 23d）；报告 §5.5 |
| 3.2 | 低维滤波 HMM/HSMM §4.6 | ☑ | `step3.py`（Student-t + sticky sojourn）；`model_comparison_commodity.csv`（HMM-t vs HSMM-NB）；报告 §3 |
| 3.3 | 无 Viterbi/平滑用于交易 | ☑ | `step3.py` 注释+实现；`test_step34.py::test_increments_and_filter_are_causal` |
| 3.4 | 保证金作转移协变量（预注册） | ☑ | `summary_commodity.json` → `margin_covariate_R_chain`（β、LR、p）；报告 §1(5) |
| 3.5 | 平均驻留 ÷ 检测延迟；规则 vs 滤波 | ☑ | 合成：`switch_delays.csv`、`switch_delay_summary.csv`；混合读数：报告 §4、§5.5、`best_case_delay_commodity.csv` |
| 3.6 | 滚动重估标签对齐不稳定率 | ☑* | `filter_fits_commodity.csv`：`degenerate` 90.5%/95.2%；按均值排序 `gap<0` 翻转 0/21（报告 §5.1、S3-5） |
| 3.7 | step3 报告 tie 到 C4「来得及吗」 | ☑ | `docs/step3-result-report.md` §1(3)(6)、§6 |

**Step 3 交付**：☑ `docs/step3-result-report.md`；日志 `internal/step3-real-run-2026-11-24.md`

## 第 4 步（经济学，kai §第4步）

| # | 项 | 通过 | 证据 |
|---|---|---|---|
| 4.1 | 成本开；概率权+熵惩罚+不动区间 | ☑ | `step4.py` FILT-SOFT/PEN/BAND；`CostParams`；报告 §2 |
| 4.2 | 三档信息价值（无状态/滤波/真值） | ☑* | 合成：`planted_info_value.csv`（ORACLE）；真实仅①②，报告 §1(5)、§4 |
| 4.3 | κ 缩放 vs MOM–REV 重配 §4.5 | ☑ | `selection_decomposition_commodity.csv`；报告 §5.3–5.4、缩放账户表 |
| 4.4 | 基准 EW50 +VT；EWA 非平凡说明 | ☑ | `perf_commodity.csv`、`ewa_grid_commodity.csv`；报告 §1(3)(4)、§5.1 |
| 4.5 | step4 归因：概念/识别/成本 | ☑ | 报告 §1(2)(6)、§6（方向 vs 择时 vs 成本网格） |

**Step 4 交付**：☑ `docs/step4-result-report.md`；日志 `internal/step4-real-run-2026-11-24.md`

---

## 协调员记录

**签收（bc-d8a1a980，2026-11-25 06:10 北京）**：对照 `step1-4-quality-evidence-2026-11-24.md` 与四份 store 报告，**第 1–4 步交付验收通过**（顶刊体例、边界结论、框架未漂移、商品窗 ≥20y）。**有条件放行**：2.6 `fut_holding` / `--all-days-extras` 未跑须在论文/稳健性中明示；Step1 全量 45min 回归以 `acceptance.json` + 逐步位相同校验代替；行业/股指流水线零分布、HMM ν 敏感性未网格——不得据此夸大主结论。缺口补齐前不把 H10 席位签名写成实证结果。

---

## 工人勾选记录（bc-34cab32f；2026-11-24 自检）

- 第 1 步：☑ A1–A7 + pytest（当晚重跑，见上表）
- 第 2 步：☑（带 2.6 席位/`all-days-extras` 缺口）
- 第 3 步：☑（3.6 以退化占比作对齐不稳定代理，已声明）
- 第 4 步：☑（真实数据无 oracle 档，已声明）

**模型**：composer-2.5-fast。**仓库**：`cursor/step2-real-futures-2dd4` @ `0ae4360`。

---

## 非谈判项（用户 2026-11-24）

| # | 要求 | 通过 | 证据 |
|---|---|---|---|
| N1 | 主面板 ≥20y；短面板显式旗标 | ☑ | `coverage_panel.csv`；step2/3/4 报告 §2–§3；`internal/theory-and-20y-compliance-audit-2026-11-24.md` |
| N2 | 理论框：谁付钱、M/R/C、Θ_c on D、步序 2→3→4 | ☑ | 代码 `config.py`/`step2.py`/`step3.py`/`step4.py`；三份结果报告「框架锁定」段 |
| N3 | 冲突则修代码或书面偏离 | ☑ | 审计 §3 五条偏离；无未声明漂移 |
| N4 | 每报告含 20y 旗标 | ☑ | v3 §2 表；step3 §2 列；step4 §3 |

## 顶刊报告标准（2026-11-24）

| # | 要求 | 通过 | 证据 |
|---|---|---|---|
| J1 | 叙事+表（非纯 bullet） | ☑ | 三报告 **摘要** 段；主体为散文+表（体例对照见下） |
| J2 | 推断：CI、片段数、ledger、pipeline null | ☑ | v3 §3–4；`trial_ledger`；`p_pipeline` |
| J3 | 诚实层级（功效不足/边界） | ☑ | §7.5 读法贯穿 §1、§5–§6 |
| J4 | 复现（SHA、命令、无 token） | ☑ | 各报告 §6/§8；`0ae4360` |
| J5 | 主表前「谁付钱」+ falsify 句 | ☑ | v3 §4.1；step3 §5.1；step4 §5.1 |
| J6 | 审稿人自检（p-hack/peek/HMM） | ☑ | `internal/journal-reporting-referee-qa-2026-11-24.md`；v3 §5 末段 |