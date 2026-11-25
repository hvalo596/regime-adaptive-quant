---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 第 3 步运行日志 2026-11-24

> 合成验证与线程环境见 [step34-real-run-2026-11-24.md](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/step34-real-run-2026-11-24.md)。

## 午后主运行

- **命令**：`python scripts/run_step34.py --raw-dir data/raw --out3 artifacts/step3 --out4 artifacts/step4`（真实面板约 25 分钟）+ 合成部分 `--synth-only`（另约 90 分钟）。
- **校准**：`artifacts/step2/calibration_commodity.json`（与第 2 步商品面板同日）。
- **评估窗口（商品）**：2006-06-27 至 2026-11-23，4961 日，**20.4 年**。
- **核心数字**：退化占比慢人 90.5%、急人 95.2%；滤波主信号 $\Theta_c=+1.8\times10^{-5}$（流水线 $p=0.40$）；慢人链 $LR=13.9$（$p=0.066$）；保证金协变量 $p=0.68$。
- **产物**：`artifacts/step3/`（`filter_fits_*`、`theta_signals_*`、`spells_*`、`model_comparison_*`、`bocpd_*` 等）。

## 晚间链式复验（2026-11-24 20:42+ UTC）

- 第 2 步复验完成后，按用户「2→3→4 不断链」指令：在 tmux `overnight-step34` 重跑 **仅真实面板** `--skip-synth`（20:43:57–20:51:48 UTC，约 8 分钟；日志 `/agent/scratch/overnight_step34_real.log`，`STEP34_REAL_EXIT=0`）。`summary_commodity.json` 与午后一致（退化 90.5%/95.2%，$\Theta_c$ 滤波 +1.8e-5，保证金 $p=0.68$）。
- **不做**：`fut_holding` 全历史；行业/股指/国债的流水线零分布重复。