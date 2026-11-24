---
cursor:
  subagentId: "bc-e70d2a86-dce1-5c1c-a99f-9ae3e1c7973b"
---
<!-- synced from Project Context 2026-11-24; canonical for agents may remain Context -->

# 项目文库索引：市场状态切换的量化策略自适应研究

> 更新：2026-11-24。分两块：**块 A**是思想与方案文档（Context 与本目录双副本）；**块 B**是 GitHub 仓库里的代码与产物。末尾的映射表把理论章节对到代码模块。
> 本文件是 Project Context 中 `project-library-index.md` 的仓库版：块 A/B 文档链接已改为仓库内相对路径；Context 里原路径的文件已按下方目录布局落到 `docs/` 子目录（见 [README](./README.md)）。块 B 代码仍在仓库根目录的 `src/`、`scripts/`、`tests/`、`artifacts/`，不在 `docs/` 下复制。
> 仓库：[hvalo596/regime-adaptive-quant](https://github.com/hvalo596/regime-adaptive-quant)（私有）。

**阅读顺序建议**：想看全貌 → [第 1 步论文式报告](B-experiment/step1-paper-report.md)；想知道"为什么这么做" → 块 A 的"核心思想"与"状态理论"；想找某段代码或某个数字的出处 → 块 B 和末尾映射表。

---

# 块 A：思想与方案（Context 文档）

## A.0 状态标记图例

- **现行**：当前依据的文档。
- **被取代**：已有更新版本，保留原文仅供对照，不再引用其结论。
- 文件内部带 `cursor.subagentId` 的是由某个工作线程写入的报告，没有的是协调者/用户直接维护的文档。

## A.1 核心思想（为什么做、赚谁的钱、怎么推）

| 文件 | 状态 | 一句话 |
|---|---|---|
| [research-core-tree.md](A-idea/core/research-core-tree.md) | 现行 | 研究核心思想树：根问题"钱从哪里来"，综合实验方案、ieki 的思想与刑凯老师建议，状态是"谁在亏钱给我"的可观测代理 |
| [strategy-money-explained.md](A-idea/core/strategy-money-explained.md) | 现行 | 白话版：两种策略各赚谁的钱、怕什么、实验文档在干嘛（情景为示意例子，非实证） |
| [regime-identification-why.md](A-idea/core/regime-identification-why.md) | 现行（Opus 加固版） | 核心论证四问：为什么可行（C1–C4 四条件）、如何来做、怎么样解释、为什么这样做可以 |
| [A-idea/archive/regime-identification-why-sonnet-v1.md](A-idea/archive/regime-identification-why-sonnet-v1.md) | 被取代（由上一行的加固版取代） | 同一主题的 Sonnet 初版，保留作对照 |

## A.2 状态理论（状态怎么定义、变量怎么算、怎么检验）

| 文件 | 状态 | 一句话 |
|---|---|---|
| [kai-dims-and-experiment-steps.md](A-idea/background/kai-dims-and-experiment-steps.md) | 现行（背景） | 刑凯四维与实验 0–6 步为什么这样分类、为什么必须这样做；D 节有待确认问题；四维公式为重建草案，非 Kai 原定义 |
| [state-construction.md](A-idea/theory/state-construction.md) | **现行（理论地基，已批准）** | 5 个状态（四象限 + 知情叠加）、5 个变量（$M,R,C,V,\Phi^\perp$）、状态机与回测接口、合成世界（§7）、可证伪假设 H0–H13（§8） |

## A.3 实验步骤（方案、结果、报告）

| 文件 | 状态 | 一句话 |
|---|---|---|
| [step1-plan.md](A-idea/archive/step1-plan.md) | **被取代**（→ step1-plan-v2.md） | 2026-11-18 旧方案：围绕 6 个 VR/刑凯代理指标的"幻觉率/功效"，与已批准的理论不一致；文件未改动 |
| [step1-plan-v2.md](B-experiment/step1-plan-v2.md) | 现行 | 按状态构建理论重写的第 1 步方案：范围、锁定参数、A1–A8 通过标准 |
| [step1-result-report.md](B-experiment/step1-result-report.md) | 现行（数字出处） | 第 1 步结果：A1–A7 全部通过，全部数字表，偏离清单 D1–D11，局限 |
| [step1-paper-report.md](B-experiment/step1-paper-report.md) | 现行（论文式整理，2026-11-24 按实证论文文体重写） | 第 1 步论文式报告：摘要、识别框架、计量构造、合成实验设计、结果与解读、讨论（有效性、功效、外部效度、实现偏离、第 2 步读法）、附录 |
| [step1-paper-report-2026-11-24-checklist-style.md](A-idea/archive/step1-paper-report-2026-11-24-checklist-style.md) | **被取代**（→ step1-paper-report.md） | 同日首版论文式报告，条目式文体；数字与现行版一致 |
| [step2-result-report.md](A-idea/archive/step2-result-report.md) | **被取代**（→ step2-result-report-v2.md） | 2026-11-18 旧第 2 步白话报告（PR #2 分支，6 个孤立指标三分位检验，真实数据结果为否定）；其理论口径已被废弃，否定结论不代表"状态不存在" |
| [step2-result-report-v2.md](B-experiment/step2-result-report-v2.md) | 现行 | 2026-11-21 第 2 步 v2：真实数据运行被阻塞（环境无 `TUSHARE_TOKEN`），代码、测试与合成回退验证已完成 |

## A.4 对话记录

| 文件 | 状态 | 一句话 |
|---|---|---|
| [thought-log.md](A-idea/meta/thought-log.md) | 现行（持续更新） | 思想源泉记录：每次对话记下用户原文与时间、主要矛盾与核心要点，文首是两层抽象的思维导图 |

## A.5 项目元数据、原始资料与检查

| 文件 | 状态 | 一句话 |
|---|---|---|
| [preferences.md](A-idea/meta/preferences.md) | 现行 | 项目偏好：每次对话更新 thought-log、金融本质优先、严格按步推进、中国期货先行等 |
| [project-context.md](A-idea/core/project-context.md) | 现行 | 项目背景：目标、已定事项（仓库、语言、数据、期货研究对象）、课题核心（回测与统计检验以状态理论为地基）与待定事项 |
| [A-raw/research-proposal.docx](A-raw/research-proposal.docx) | 现行（原始资料） | 研究方案原文（Word） |
| [A-raw/research-proposal.txt](A-raw/research-proposal.txt) | 现行（原始资料） | 研究方案原文纯文本版，便于检索 |
| [A-raw/kai-wechat-screenshot.png](A-raw/kai-wechat-screenshot.png) | 现行（原始资料） | 刑凯老师微信建议截图（A 股高维 HMM 参数灾难、四个近似正交维度） |
| [A-raw/tushare-access-check.md](A-raw/tushare-access-check.md) | 现行（检查记录，2026-11-18） | Tushare 期货接口权限与数据可得性检查：日线、映射、持仓排名、结算参数等可用；token 未落盘 |
| [index.md](./index.md) | 现行 | 本文件：项目文库两块索引 |

## A.6 仓库内文件全清单（块 A/B 内容文件 19 个，另有本索引与 README）

| 目录 | 文件 |
|---|---|
| `A-idea/core/` | research-core-tree、strategy-money-explained、project-context、regime-identification-why |
| `A-idea/theory/` | state-construction |
| `A-idea/background/` | kai-dims-and-experiment-steps |
| `A-idea/meta/` | preferences、thought-log |
| `A-idea/archive/` | step1-plan（被取代）、step2-result-report（被取代）、regime-identification-why-sonnet-v1（被取代）、step1-paper-report-2026-11-24-checklist-style（被取代） |
| `A-raw/` | research-proposal.txt、research-proposal.docx、kai-wechat-screenshot.png、tushare-access-check.md |
| `B-experiment/` | step1-plan-v2、step1-result-report、step1-paper-report、step2-result-report-v2 |
| `docs/` 根 | README.md（总导航）、index.md（本文件）、phase2-china-futures-step2.md 与 phase2-step2-stop-memo.md（旧阶段 2 文档，原样保留） |

## A.7 被取代关系速查

| 旧文件 | 新文件 | 取代原因 |
|---|---|---|
| [A-idea/archive/step1-plan.md](./A-idea/archive/step1-plan.md)（2026-11-18） | [B-experiment/step1-plan-v2.md](./B-experiment/step1-plan-v2.md)（2026-11-21） | 旧方案围绕 6 个孤立指标的幻觉率/功效，与已批准的状态构建理论不一致 |
| [A-idea/archive/step2-result-report.md](./A-idea/archive/step2-result-report.md)（2026-11-18） | [B-experiment/step2-result-report-v2.md](./B-experiment/step2-result-report-v2.md)（2026-11-21） | 旧报告是 6 个指标三分位的否定性结果，理论口径已换；v2 在新理论下重做，真实数据运行因缺 token 被阻塞 |
| [A-idea/archive/regime-identification-why-sonnet-v1.md](./A-idea/archive/regime-identification-why-sonnet-v1.md) | [A-idea/core/regime-identification-why.md](./A-idea/core/regime-identification-why.md) | Sonnet 初版 → Opus 加固版 |
| [A-idea/archive/step1-paper-report-2026-11-24-checklist-style.md](./A-idea/archive/step1-paper-report-2026-11-24-checklist-style.md)（2026-11-24） | [B-experiment/step1-paper-report.md](./B-experiment/step1-paper-report.md)（2026-11-24） | 首版为条目/表格堆叠文体；现行版按实证论文文体重写，数字不变 |

---

# 块 B：代码与产物落地（GitHub + artifacts）

## B.1 仓库与分支

- 仓库：[hvalo596/regime-adaptive-quant](https://github.com/hvalo596/regime-adaptive-quant)（私有，Python）。`main` 目前只有一次初始提交。
- 分支与 PR（2026-11-24 以 `gh pr list` 核对）：

| 分支 | 用途 | 最新提交 | PR |
|---|---|---|---|
| [`cursor/step1-state-construction-2dd4`](https://github.com/hvalo596/regime-adaptive-quant/tree/cursor/step1-state-construction-2dd4) | **第 1 步**：状态变量、状态机、两套回测引擎、合成世界、校准与验收 | `0c5d3b2` Step 1: full acceptance run (A1-A7 pass)… | 未发现 PR |
| [`cursor/step2-real-futures-2dd4`](https://github.com/hvalo596/regime-adaptive-quant/tree/cursor/step2-real-futures-2dd4) | **第 2 步**：真实中国期货数据层、H 系列检验、非定义签名、合成回退验证；叠在第 1 步分支之上 | `94857c1` Step 2: synthetic-fallback validation artifacts… | 未发现 PR |
| [`cursor/phase1-synthetic-backtest-5524`](https://github.com/hvalo596/regime-adaptive-quant/tree/cursor/phase1-synthetic-backtest-5524) | 旧阶段 1（合成市场 + 点时间回测骨架） | — | [PR #1](https://github.com/hvalo596/regime-adaptive-quant/pull/1)（旧理论，已被第 1 步版取代） |
| [`cursor/phase2-china-futures-step2-4a4c`](https://github.com/hvalo596/regime-adaptive-quant/tree/cursor/phase2-china-futures-step2-4a4c) | 旧阶段 2（Tushare 接入与 VR/刑凯草案三分位检验） | — | [PR #2](https://github.com/hvalo596/regime-adaptive-quant/pull/2)（旧理论，已被取代） |

分支关系：phase1 → phase2 → step1（含 phase 产物，`artifacts/phase*` 仅供对照）→ step2。第 1 步分支的 README 写明"早先阶段 1/2（PR #1、#2）已被本版取代"。

## B.2 `src/regime_quant/` 目录树（第 1 步分支；标 ★ 的是第 2 步新增）

```
src/regime_quant/
├── __init__.py
├── config.py          锁定参数：LegSpec（M-B/M-A/R-A/R-B/R-B-gap/M-C）、StateParams、CostParams、InferenceParams；kappa_LH、pairs_in_window、min_dwell
├── rolling.py         无前视的向量化滚动工具（roll_sum/roll_mean/ewma_sum/expanding_window_mean/shift）
├── statevars.py       §3 变量：standardise、loo_factor_regress、mean_sq_corr、mr_stat/tau_stat（M,R,R^gap）、
│                      concentration/flag_sets/informed_indicator/exclusion_mask（C、F、K_I）、environment（V、Φ、Φ⊥、z）
├── statemachine.py    hysteresis（双阈值+最短驻留）、selection_signal（s=δM−δR）、quadrant_labels、segments
├── backtest.py        向量化引擎：sign_signal、leg_position、build_leg（腿层面波动缩放）、run_weights（成本）、state_weights（κ、剔除 F）
├── eventengine.py     逐日流式引擎（不与 backtest.py 共用代码）与 reconcile 对账
├── pipeline.py        run_state_pipeline：收益面板 → 变量 → 状态 → 回测（合成与真实数据共用）
├── inference.py       平稳块自助、循环平移、theta_test（中心化 Cov）、mean_diff_test
├── hypotheses.py      h5_event_test、delta_association（以及第 2 步的 H 系列）
├── world.py           §7 合成世界：kernel/rho_theory 闭式、solve_states、WorldSpec、generate（regime/N0z/N0/N1/N2/N2c/N2b/N3/N4/informed）
├── nullcal.py         calibrate（偏差 b、标准误倍数）、calibrate_c_null（C 零分布）、save/load
├── recovery.py        auc、recovery_summary、crossing_delays、d_star
├── step1.py           第 1 步实验任务（sim_task、delay_task、cp_interval、working_bias_check）
├── signals.py         ⚠ 阶段 1 遗留，引用已不存在的 config.StrategyParams，第 1 步流水线不使用
├── step2.py ★         第 2 步数据集、面板/板块/分品种分析、H 检验电池
├── step2_run.py ★     第 2 步运行入口逻辑
├── nondefining.py ★   非定义变量签名（持仓量、AV、Amihud、Llorente b2、席位、保证金）§5
├── altchannels.py ★   替代通道检验（结算价、涨跌停、价差反弹、风险溢价、波动）§6
├── audit.py ★         数据审计（极端日、夜盘、指数受限期）
└── data/
    ├── tushare_client.py   Tushare Pro 客户端（token 取自环境变量，不落盘；transport 可注入）
    ├── store.py            原始数据缓存（csv.gz）与抓取编排
    ├── roll.py             自己做换月：同合约收盘到收盘的连续序列
    ├── panel.py            组装品种×日收益面板与标记面板
    ├── universe.py         品种与板块标签（草案）
    ├── flags.py            一价日、涨跌停代理、换月日、夜盘起始、指数受限期等标记
    ├── activity.py ★       品种活跃度、carry 代理
    └── fake_tushare.py ★   由合成世界生成的假 Tushare 数据，供离线回退与测试
```

规模：第 1 步分支 `src/regime_quant` 约 3400 行（含阶段 1/2 遗留的数据层与 `signals.py`）。

## B.3 `scripts/` 与 `tests/` 对应理论章节

### scripts/

| 脚本 | 作用 | 对应理论/方案 |
|---|---|---|
| `scripts/run_step1.py` | 第 1 步全部实验：一次性校准、$\tau$ 核对、闭式对照、无状态对照、功效、延迟、知情叠加；`--scale` 缩放规模（1.0 约 45 分钟/4 核） | 方案 v2 §4–5；理论 §7.5、§8（H13） |
| `scripts/summarize_step1.py` | 读 `artifacts/step1/*.csv`，跑引擎检查，判定 A1–A7，写 `acceptance.json` 与 `summary.md` | 方案 v2 §4 |
| `scripts/fetch_tushare_futures.py` ★ | 抓取 Tushare 期货数据 | 理论 §3.1（第 2 步） |
| `scripts/run_step2.py` ★、`scripts/run_step2_validation.py` ★ | 第 2 步真实数据运行与合成回退验证 | 理论 §5、§6、§8 |

### tests/（第 1 步分支 19 个测试）

| 测试 | 检查内容 | 对应 |
|---|---|---|
| `tests/test_engine.py::test_vectorised_equals_event_driven`、`test_reconcile_other_specs` | 向量化与流式引擎逐日一致（含其它参数组合） | A1；理论 §4.5 |
| `test_selection_identity` | 恒等式 $P-\tfrac12(x^M+x^R)=\tfrac12 sD$ | A1；理论 §4.5 |
| `test_no_lookahead_full_pipeline` | 篡改未来数据，全流水线 $t$ 及以前不变 | A1；P4/点时间一致 |
| `test_costs_scale_with_turnover` | 成本随换手缩放 | 理论 §4.5 |
| `tests/test_statevars.py::test_kappa_values_match_doc`、`test_pairs_and_dwell` | $\kappa$ 数值、配对数与最短驻留 | 理论 §3.3、§4.2 |
| `test_standardise_uses_only_the_past` | 标准化分母只用 $t-1$ 及以前 | 理论 §3.1 |
| `test_mr_stat_bias_is_negative_and_scales_like_sqrt_LH_over_T`、`test_mr_stat_detects_planted_autocorrelation` | 偏差 $b\approx-\sqrt{LH}/T$、能检出植入的自相关 | 理论 §3.3；A2 |
| `test_hysteresis_semantics`、`test_segments` | 滞后带与片段语义 | 理论 §4.2 |
| `test_flag_set_single_event_is_feasible_for_wide_panel`、`test_exclusion_mask_window`、`test_null_c_threshold_decreases_with_n` | $\mathcal F$ 在宽面板上可行、剔除窗口、$C$ 零阈值随 $N$ 递减 | 理论 §3.5、§4.4；偏离 D2/D3 |
| `test_rolling_ols_matches_numpy` | 滚动 OLS 与 numpy 一致 | 理论 §3.6（$\Phi^\perp$） |
| `test_closed_form_matches_simulation`、`test_solve_states_hits_planted_effects` | 闭式解与模拟吻合、状态参数达到植入效应 | 理论 §7.3；A2 |
| `test_theta_test_centering_removes_pure_tilt` | $\Theta$ 中心化去掉纯配置倾斜 | 偏离 D1；理论 §0.4 |

第 2 步新增 `tests/test_data.py`、`tests/test_step2.py`（数据层、第 2 步检验电池）。运行：`pytest -q`。

## B.4 `artifacts/step1/` 文件词汇表（第 1 步分支）

| 文件 | 内容 | 支撑报告章节 |
|---|---|---|
| `summary.md` | 自动汇总：A1–A7 判定与假阳性率表（所有组合 × 规则） | 结果报告 §1、§3.3 |
| `acceptance.json` | A1–A7 逐条验收数值（对账最大差、AUC、各世界假阳性及区间等） | 结果报告 §1 |
| `acceptance_inputs.json` | 各类模拟次数：`n_null`=400、`n_pow`=150、`n_delay`=80、`n_inf`=100 | 论文 §5.2 |
| `engine_checks.json` | A1 的对账、防偷看与恒等式检查 | 结果报告 §1（A1） |
| `calibration.json` | 一次性校准常数：偏差 $b$、标准误倍数、$C$ 零阈值（按 $N$） | 结果报告 §3.1 |
| `calibration_check.csv` | 5 个参数在空世界的 $\tau$ 均值、标准差、$P(\tau\ge1.28)$ | 结果报告 §3.1（A2） |
| `closed_form_vs_sample.csv` | 单一象限世界样本 $\rho$ 与 §7.3 闭式解对照 | 结果报告 §3.2 |
| `null_summary.csv` | 无状态对照汇总（组合 × 规则 × 世界的假阳性率与区间） | 结果报告 §3.3（A4、A5） |
| `null_controls_raw.csv` | 无状态对照逐次模拟原始记录（约 4 MB） | 同上（可重算） |
| `null_descriptives.csv` | 无状态世界的描述统计（含 $\Theta_c$ 均值等） | 结果报告 §6 局限 5 |
| `association_systematic.csv` | A6：$\delta$ 与 $z(V)$、$z(\Phi^\perp)$、$C$ 的标准化均值差 | 结果报告 §1（A6）、D8 |
| `association_pipeline_null.csv`、`association_thresholds.json` | A6 的循环平移/流水线级零分布与阈值（仅报告） | 结果报告 D8 |
| `power_summary.csv`、`power_raw.csv` | 各效应档位的检出率、AUC、象限准确率（原始约 3 MB） | 结果报告 §3.4（A3、A8） |
| `delay_summary.csv` | 识别延迟、已检出/切换次数、$d^*$ 与窗口版预测、比值 | 结果报告 §3.5（A7） |
| `informed_summary.csv`、`informed_raw.csv` | 知情叠加：命中、延迟、标记精度、H5 差与拒绝率 | 结果报告 §3.6 |
| `working_bias.csv` | N4 世界收盘价 vs 结算价的滞后 1 自相关与 R-B 的 $\rho$ | 结果报告 §3.3（Working 对照） |

其它产物目录（旧阶段，仅供对照）：`artifacts/phase1/`、`artifacts/phase2_*`（真实/合成/敏感性/参数网格）、`artifacts/trial_ledger_cumulative.csv`（累计试验账本）。第 2 步分支另有 `artifacts/step2_synthetic/{null_N0z, planted_effect010_docdwell, planted_effect015_longdwell, informed_z4}/`（合成回退验证，每目录含 hypotheses、theta_by_panel、trial_ledger 等）。仓库 `docs/` 另有旧阶段文档 `phase2-china-futures-step2.md`、`phase2-step2-stop-memo.md`。

复现：
```bash
pip install -e ".[dev]"
pytest -q
python scripts/run_step1.py --out artifacts/step1 --scale 1.0
python scripts/summarize_step1.py artifacts/step1
```

## B.5 块 A → 块 B 映射：理论章节 → 代码模块

| 理论章节（[state-construction.md](A-idea/theory/state-construction.md)） | 内容 | 代码模块（`src/regime_quant/`） | 验证它的测试 / 产物 / 结果报告章节 |
|---|---|---|---|
| §3.1 收益、标准化、面板 | $\tilde r$、截断、60 日波动 | `statevars.standardise`、`vol_exante`；`data/roll.py`、`data/panel.py` | `test_standardise_uses_only_the_past` |
| §3.2 共同因子 | 留一法等权因子、60 日回归、残差 | `statevars.loo_factor_regress` | 偏离 D6 |
| §3.3 $M_t$ | $\rho^{(L,H)}$、VR 恒等式、$\kappa$、$N_{eff}$、偏差 | `statevars.mr_stat`、`tau_stat`；`config.kappa_LH`；`nullcal.calibrate` | `test_kappa_values_match_doc`、`test_mr_stat_*`；`calibration*.{json,csv}`；报告 §3.1 |
| §3.4 $R_t$、$R^{gap}_t$ | 反转痕迹与跳一日版 | `statevars.mr_stat`（`gap` 参数） | `working_bias.csv`；报告 §3.3 |
| §3.5 $C_t$、$\mathcal F_t$ | 集中度、$h_0$、标记集、零阈值 | `statevars.concentration`、`flag_sets`、`informed_indicator`、`null_c_threshold`；`nullcal.calibrate_c_null` | `test_flag_set_*`、`test_null_c_threshold_*`；`informed_summary.csv`；偏离 D2、D3 |
| §3.6 $V_t$、$\Phi^\perp_t$ | 环境变量与正交化、滚动 z | `statevars.environment`、`scalar_rolling_ols`、`rolling_z` | `test_rolling_ols_matches_numpy`；`association_systematic.csv` |
| §4.1–4.2 状态机 | $\tau$、双阈值、最短驻留 | `statemachine.hysteresis`、`selection_signal`、`quadrant_labels`；`config.min_dwell` | `test_hysteresis_semantics`、`test_pairs_and_dwell` |
| §4.3 识别时效下界 | $d^*$、窗口规则 | `recovery.d_star`、`crossing_delays` | `delay_summary.csv`；报告 §3.5（A7） |
| §4.4 知情叠加判定 | $I_t$、$K_I$ 剔除 | `statevars.informed_indicator`、`exclusion_mask`；`backtest.state_weights` | `test_exclusion_mask_window` |
| §4.5 回测映射与主检验量 | 腿、$s_t$、权重、$\kappa$、成本、恒等式、$\Theta$ | `backtest.*`、`eventengine.*`、`pipeline.run_state_pipeline`；`inference.theta_test` | `test_engine.py`；`engine_checks.json`；`test_theta_test_centering_*`；报告 §1（A1）、D1 |
| §4.6 概率化版本 | 半马尔可夫 HMM（第 3 步） | 尚未实现 | — |
| §5 非定义变量的预测 | 持仓、AV、Amihud、Llorente、席位、保证金 | `nondefining.py` ★（第 2 步） | 第 2 步 v2 报告 |
| §6 替代解释 | 结算价、涨跌停、价差反弹、风险溢价、波动 | `altchannels.py` ★；`data/flags.py`；N3、N4 世界 | `working_bias.csv`；报告 §3.3 |
| §7.1–7.2 合成世界与半马尔可夫 | 慢人/急人/做市/知情、状态切换 | `world.generate`、`WorldSpec`、`_semi_markov`、`_core` | `power_summary.csv`、`delay_summary.csv` |
| §7.3 闭式解 | $\gamma^{慢},\gamma^{急}$、$\rho(\theta)$、状态 Ⅲ 条件 | `world.kernel`、`rho_theory`、`solve_states` | `test_closed_form_matches_simulation`；`closed_form_vs_sample.csv`；偏离 D11 |
| §7.5 无状态对照 N0–N4（外加 N0z、N2c） | 误报率 ≤ 5% | `world.generate(kind=…)`；`step1.sim_task`；`scripts/run_step1.py` | `null_summary.csv`、`acceptance.json`；报告 §3.3（A4、A5、A6） |
| §8 假设 H0–H13（第 1 步：H5、H13） | 块自助 + 循环平移 + 流水线零分布 | `inference.*`、`hypotheses.h5_event_test`、`delta_association` | `null_summary.csv`、`informed_summary.csv`；报告 §3.6 |
| 方案 v2 §4 通过标准 A1–A8 | 验收判定 | `scripts/summarize_step1.py`、`step1.py` | `acceptance.json`、`summary.md` |
| 理论外：推断参数、成本、锁定参数 | 阈值、块长、成本、策略参数 | `config.py` | 论文 §5.2 |
