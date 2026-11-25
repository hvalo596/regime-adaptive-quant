---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 非谈判项合规审计（2026-11-24）

依据用户 2026-11-24 重复指令 + 协调员质检清单。仓库 `cursor/step2-real-futures-2dd4` @ `0ae4360`。

## 1. 数据窗口（≥20 日历年）

| 层级 | 面板 | `analysis_span_years` / 评估跨度 | `meets_min_years` | 报告位置 |
|---|---|---|---|---|
| 第 2 步主推断 | 商品 | **24.0** | True | v3 §2 表；`coverage_panel.csv` |
| 第 2 步对照 | 股指 | 10.3 | **False**（标注） | v3 §2、§5 |
| 第 2 步对照 | 国债 | 6.9 | **False**（TL 等 2023 年起） | v3 §2、§5 |
| 第 3–4 步主推断 | 商品（滤波/回测） | **20.4**（750d 训练窗后） | 是（≥20） | step3 §2 表；step4 §3 |
| 第 3–4 步对照 | 行业/股指/国债 | 6.8–16.0 | 否（原因列明） | step3 §2 表 |

**抓取默认值**：`fetch_tushare_futures.py --years 20`（起算 20040102）；`run_step2.py --min-years 20` 默认 20，短窗写入 `summary.json` 的 `span_warning`（当前无触发）。

**未做缩短窗**：无 demo/子样本 p 值优化；`amount` 回填是恢复流动性规则而非缩窗。

## 2. 理论框（不漂移）

| 原则 | 实现/报告 | 偏离声明 |
|---|---|---|
| 状态 = 谁付钱（慢/急）+ Ⅲ 知情 overlay | δ^M×δ^R 象限 + C/ℱ | 无 |
| M/R 在策略 L/H；V、Φ⊥ 仅环境 | `config.py` MOM_MAIN/REV_MAIN；H8 三分位 | 无 |
| 检验对象：风险标准化 **D**；主检验 **Θ_c** | `step2.py` `theta_test`；v3 明确 raw Θ 非择时 | 无 |
| 第 2 步无 HMM 做存在性 | step2 无 `step3` 导入 | 无 |
| 第 3 步仅滤波概率、无 Viterbi 交易 | `step3.py` docstring + `forward_filter` | 无 |
| 第 4 步三档信息价值 + §4.5 拆分 | `planted_info_value.csv`；`selection_decomposition_*` | 真实无 oracle 档（已声明） |
| 金融读法 step1-paper §7.5 | v3 §1、§5；step3 §6；step4 §6 | 无 |

**权威文档**：运行未改写 `state-construction.md` / `kai-dims-and-experiment-steps.md` / `regime-identification-why.md`；报告内链引用。

## 3. 已登记实现偏离（非静默）

1. **商品第 3–4 步评估起点 2006-06**（非 2002-11）：理论允许的 750d 训练 + 滤波因果性；step3 §2 表与 step2 24y 池化窗口并列说明。
2. **H11 保证金事件 2021+**：`fut_settle` API 历史起点，v3 §4.4。
3. **dwell÷延迟（真实）**：拟合退化，用合成直接测 + 混合读数，step3 §5.5、S3-6。
4. **C 阈值未用真实数据重标定零分布**：v3 §5 H5。
5. **协调员清单缺口**：`fut_holding`、可选 `--all-days-extras`（见 `quality-checklist-2026-11-24.md` 2.6*）。

## 4. 报告内 20y 旗标

- `step2-result-report-v3.md`：§2 表 + `meets_min_years` 叙述  
- `step3-result-report.md`：§2「是否 ≥20 年」列  
- `step4-result-report.md`：§3 段落 + 指向 step3  

**协调员附件**：`internal/quality-checklist-2026-11-24.md`（逐 bullet）；本文件（非谈判项专审）。