---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 第 4 步运行日志 2026-11-24

> 与第 3 步同一次 `run_step34.py` 写出 `artifacts/step4/`；合成信息价值见 [step34-real-run-2026-11-24.md](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/step34-real-run-2026-11-24.md)。

## 午后主运行

- **命令**：同上（`panel_report` 内联写出 step4 表）；附 `scripts/step4_extras.py`、`scripts/summarize_step34.py`。
- **成本与 +VT**：基本 1× 换手成本；所有主族比较在波动率匹配（+VT）下进行。
- **核心数字（商品，FILT-PEN+VT vs EW50+VT）**：滤波夏普 −0.59 vs EW50+VT 0.16，差 −0.74（Holm=1）；规则 RULE+VT 0.02；MOM+VT 1.12；择时账户滤波约 +0.2%/年。
- **产物**：`artifacts/step4/perf_*`、`comparisons_*`、`selection_decomposition_*`、`sharpe_levels_commodity.csv` 等。

## 晚间链式复验（2026-11-24 20:42+ UTC）

- 随第 3 步同跑 `run_step34.py --skip-synth`（20:43–20:52 UTC）；`comparisons_commodity.csv` 与午后一致（FILT-PEN+VT 夏普 −0.59 vs EW50+VT 0.16）。