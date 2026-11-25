---
cursor:
  subagentId: "bc-6b7d1666-a554-5522-9f22-072ff9ef35e6"
---

# 螺纹钢（RB）专项时间线（2026-11-26）

> 代码/产物：`cursor/step2-real-futures-2dd4` @ `0ae4360`。本 VM **无** `data/raw`（[`summary`](/agent/repos/regime-adaptive-quant/artifacts/step2/summary.json) 注明 Tushare 缓存不入库），故 **日度池化标签、p^M/p^R 转换日** 无法从仓库复算；下列数字均来自已提交 CSV/JSON 或覆盖表日期算术。

## 1. 「二十年」口径 vs RB

| 项目 | RB | 商品池化面板 |
| --- | --- | --- |
| 数据源 | [`/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_products.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_products.csv) | [`/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_panel.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_panel.csv) |
| `raw_first_bar` | 2009-03-27 | — |
| `raw_last_bar` | 2026-11-24 | 2026-11-24（`last_date`） |
| `liquid_from` | 2009-06-25 | — |
| `first_return_in_panel` | **2009-06-26** | 全板首笔收益日 2000-04-10 |
| `n_rollable_days`（单品种可展期日） | **4290** | — |
| `included` | True（`drop_reason` 空） | 40/40 品种纳入 |
| 状态分析窗 | — | **2002-11-29**～**2026-11-24**；`analysis_days` **5825**；`analysis_span_years` **23.99**；`meets_min_years` **True** |
| 单品种自入板起的跨度 | **17.41 年**（2009-06-26→2026-11-24，覆盖表日期相减） | — |
| **RB 单独是否满 20 年？** | **否**（约 17.4 日历年） | 池化窗满 20 年（24y 级） |

**说明（面板 24y ≠ 每品种 24y）**：池化分析窗起自 2002-11-29，因 CU/RU/AL 等更早品种满足 250 日历史 + 流动性闩锁；RB 2009 年才入板，在 **2002–2009** 段内商品状态由**无 RB 的 cohort** 决定。[`roll_quality_commodity.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/roll_quality_commodity.csv) 对 RB：`n_days=4290`（单品种展期连续日），与池化 `5825` 分析日不是同一计数。

## 2. Step 2：四象限与 RB

**δ^M/δ^R 是面板池化还是分品种？**  
一步：**池化**。`mr_stat` 对每个交易日把**所有在场品种**的策略匹配自相关聚合为标量 \(\rho\)，再经 `tau_stat` → `hysteresis` 得 \(\delta^M,\delta^R\) 与四象限（[`statevars.py`](/agent/repos/regime-adaptive-quant/src/regime_quant/statevars.py) `mr_stat`/`loo_factor_regress`；[`pipeline.py`](/agent/repos/regime-adaptive-quant/src/regime_quant/pipeline.py) `run_state_pipeline`）。**不是** RB 单列状态。  
逐品种 **N=1** 另有一套 δ（[`per_product_theta.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/per_product_theta.csv)，`step2.py::per_product`）。

### 2.1 RB 相关的分析日界（覆盖表口径）

| 口径 | 首日 | 末日 | 天数 | 来源 |
| --- | --- | --- | ---: | --- |
| RB 入商品收益矩阵 | 2009-06-26 | 2026-11-24 | 4290（可展期日） | `coverage_products` + `roll_quality_commodity` |
| 商品池化 **valid** 状态日（全板） | 2002-11-29 | 2026-11-24 | 5825 | `coverage_panel` |
| RB 单品种 N=1 管线 valid | （未单独落盘起日） | — | **3970** | `per_product_theta` 行 `RB` |

**「RB 在场 ∧ 池化 valid」四象限计数与日界**：需要 `data/raw` 还原 `commodity.returns['RB'].notna() & run.valid`。**本交付未给出该计数**（见 §2.3）。

### 2.2 可引用的象限占比（两种口径，勿混用）

| 口径 | I | II | III | IV | 总日数 | 文件 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **池化 valid 日计数** | 1926 | 549 | 200 | 3149 | 5824（表内 ALL 5824） | [`state_means_commodity.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/state_means_commodity.csv) |
| **RB 单品种 N=1**（份额×`n_days` 取整） | 779 | 503 | 97 | 2591 | 3970 | [`per_product_theta.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/per_product_theta.csv)（`share_*`：0.196 / 0.127 / 0.024 / 0.653） |

池化象限为 **40 品种横截面**；N=1 为 **RB 自身收益** 驱动的 τ，与 Boss 要的「池化状态在 RB 上市期」不是同一对象。

### 2.3 状态 **片段**（≥10 日）

**产物 [`state_segments.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/state_segments.csv) 仅有池化汇总，无 `start_date`/`end_date`：**

| state | 池化 valid 日数 | ≥10 日片段数 | 均长（日） |
| --- | ---: | ---: | ---: |
| I | 1926 | 29 | 65.9 |
| II | 549 | 19 | 27.6 |
| III | 200 | 11 | 16.3 |
| IV | 3150 | 33 | 94.2 |

与 [`hypotheses.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/hypotheses.csv) occupancy 行一致（`segments_I`…`segments_IV` = 29/19/11/33）。

#### 2.3.1 日度复算（RB 在场 ∧ 池化 valid）

**2026-11-26 worker**（分支 `cursor/step2-real-futures-2dd4` @ `0ae4360`）：`TUSHARE_TOKEN` **未注入** `env`；`data/raw` **不存在**；`fetch_tushare_futures.py` 退出码 **3**；`rb-timeline-export.py` 退出码 **2**。个人 Secret 名 `TUSHARE` 在 app 侧可见但未绑定到本 VM shell。**本节约束下可报告行数均为 0**，表体待有缓存后重跑脚本。

| 字段 | 值 |
| --- | --- |
| RB valid 首日 | *待复算* |
| RB valid 末日 | *待复算* |
| RB valid 日数 | *待复算* |
| 池化 ≥10 日片段行数 | **0**（未产出） |

**≥10 日池化片段（带日期）** — 列：`start_date`, `end_date`, `state`, `length_days`, `rb_active_days_inside`

*（无数据行；完整 CSV 将由 [`internal/rb-timeline-export.py`](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/rb-timeline-export.py) 写入 `internal/rb-pooled-segments-ge10-2026-11-26.csv` 后整表粘贴于此。）*

复算说明：[`internal/rb-timeline-recompute-2026-11-26.md`](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/rb-timeline-recompute-2026-11-26.md)。

## 3. Step 3：HMM 与 RB 时代

**p^M / p^R**：对商品面板 **τ^M、τ^R 增量**做滚动 Student-t HMM（[`step34.py`](/agent/repos/regime-adaptive-quant/src/regime_quant/step34.py) `build_states` → `rolling_filter`），**不是** RB 价格序列。**评估窗**（[`summary_commodity.json`](/agent/repos/regime-adaptive-quant/artifacts/step3/summary_commodity.json)）：**2006-06-27**～**2026-11-23**，**4961** 日（20.41 年）；RB **2009-06-26** 才入板，故全窗指标 **混合了 RB 缺席期（约 2006–2009）与 RB 在场期**。

### 3.1 规则 vs 滤波（池化；[`spells_commodity.csv`](/agent/repos/regime-adaptive-quant/artifacts/step3/spells_commodity.csv)）

| 序列 | days_on | share_on | spells | spells_ge10d | mean_spell | switches_per_year |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rule δ^M (step 2) | 1588 | 0.320 | 17 | 17 | 93.4 | 1.73 |
| rule δ^R (step 2) | 703 | 0.142 | 31 | 26 | 22.7 | 3.15 |
| HMM-t P^M>0.5 | 870 | 0.175 | 4 | 2 | 217.5 | 0.41 |
| HMM-t P^R>0.5 | 4557 | 0.919 | 18 | 16 | 253.2 | 1.83 |

### 3.2 退化与规则—滤波一致性（RB 时代仍需读全窗）

| 指标 | 数值 | 文件 |
| --- | ---: | --- |
| `degenerate_share_M` | **0.905** | `summary_commodity.json` |
| `degenerate_share_R` | **0.952** | 同上 |
| `corr(δ^M, p^M)` | **0.037** | 同上 |
| `corr(δ^R, p^R)` | **0.083** | 同上 |

[`filter_fits_commodity.csv`](/agent/repos/regime-adaptive-quant/artifacts/step3/filter_fits_commodity.csv) 记录滚动重估（`refit_day_index` 为**面板行号**，非日期）；M 链 epoch 多标 `degenerate=True`，与 **90.5%** 退化占比一致。

### 3.3 p^M>0.5 / p^R>0.5 **上穿日**（2009-06-26 起，公共 eval 掩码）

**2026-11-26 worker**：同 §2.3.1，无 `data/raw`，日度 `p^M`/`p^R` 未在本 VM 重算。**上穿日计数均为 0（未产出）**。

| 序列 | 上穿日总数 | 首 15 日 | 末 15 日 |
| --- | ---: | --- | --- |
| p^M | **0** | *待复算* | *待复算* |
| p^R | **0** | *待复算* | *待复算* |

全表将自 `internal/rb-hmm-pM-upedges-from-2009-06-26.txt`、`internal/rb-hmm-pR-upedges-from-2009-06-26.txt` 粘贴；定義：`common = evaluate_all(...)` 掩码 ∧ 日期 ≥ 2009-06-26 ∧ `p>.5` 且前一日 ≤0.5 或缺失。

**RB 相关解读（仍来自已入库汇总，非本次日度表）**：eval 窗内 **91.9%** 日 `P^R>0.5`，慢链 `P^M>0.5` 仅 **17.5%**，M 链 **~90%** 重估退化，[`corr(δ^M,p^M)≈0.04`](/agent/repos/regime-adaptive-quant/artifacts/step3/summary_commodity.json) —— 滤波慢状态在 RB 时代几乎不提供独立信息。

## 4. Boss：「选货有问题吗？」（仅 RB，三条实质）

- **流动性门闩（非事后选股）**：RB `liquid_from=2009-06-25`，`first_return_in_panel=2009-06-26`，较 `raw_first_bar=2009-03-27` 晚约一季；全市场 **67573** 合约日 `amount` 用 vol×close×乘数填补（[`summary.json`](/agent/repos/regime-adaptive-quant/artifacts/step2/summary.json)）。闩锁阈值事前固定（`PanelParams`），不是按 RB 全样本表现反推纳入时点。
- **队列 / 20 年误区**：商品 **5825** 分析日、**23.99y** 来自 **CU/AL/RU…** 老品种；RB **17.4y** 面板史、**不满足**单品种 20y。把池化 H0/HMM 结论说成「螺纹钢二十年经验」会 **系统性高估 RB 样本长度**。RB 单品种 H0：`theta_c=-3.42e-05`，`p_shift=0.613`（[`per_product_theta.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/per_product_theta.csv)），**未检出**。
- **池化状态不是 RB 状态**：2002–2009 池化 δ 与 RB 无关；2009 后 δ 仍由最多 **~40** 品种横截面驱动（`live_products_mean≈23.4`，[`coverage_panel.csv`](/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_panel.csv)）。若交易标的仅是 RB，却使用商品池化 RULE/FILT 信号，属于 **标的—测量错配**，而非 RB 自身「有无慢/急人」的检验。

## 附录：本页引用的产物路径

- `/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_products.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/coverage_panel.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/roll_quality_commodity.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/state_segments.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/state_means_commodity.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/per_product_theta.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/hypotheses.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step2/summary.json`
- `/agent/repos/regime-adaptive-quant/artifacts/step3/summary_commodity.json`
- `/agent/repos/regime-adaptive-quant/artifacts/step3/spells_commodity.csv`
- `/agent/repos/regime-adaptive-quant/artifacts/step3/filter_fits_commodity.csv`
- `/agent/repos/regime-adaptive-quant/src/regime_quant/statevars.py`
- `/agent/repos/regime-adaptive-quant/src/regime_quant/pipeline.py`