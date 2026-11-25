# 课题交付包说明（2026-11-26）

本压缩包内容来自本 Project 的 Context（Agent Store），为对话与工人产出的**文档、方案、报告、脚本与运行记录**；**不含** Tushare 原始 `data/raw` 与体量巨大的 `artifacts/step2|3|4/` CSV（在 GitHub 代码库分支上，需本地跑数或克隆后拉取）。

**分类入口（解压后先看）**：[`docs/archive/00-分类总索引.md`](archive/00-分类总索引.md) — 四类：①初始理论 ②讨论与你的原文 ③团队产出 ④代码数值产物。

## 一、你给的原始方案

| 文件 | 说明 |
|------|------|
| `internal/research-proposal.txt` | 初始技术路线（六步实验文档）原文 |
| `internal/research-proposal.docx` | 同上 Word 版 |

## 二、理论地基（草案/预注册）

| 文件 | 说明 |
|------|------|
| `docs/state-construction.md` | 状态如何构建（五状态、池化 M/R、检验接口） |
| `docs/regime-identification-why.md` | 慢人/急人、C1–C4 核心论证 |
| `docs/kai-dims-and-experiment-steps.md` | 四维与实验步骤对应 |
| `docs/strategy-money-explained.md` | 白话：赚谁的钱 |
| `docs/research-core-tree.md` | 研究结构树 |
| `docs/project-context.md` | 项目背景与决策记录 |

## 三、Step 1–4 结果报告（实证主链）

| 文件 | 说明 |
|------|------|
| `docs/step1-paper-report.md` | 第 1 步：合成世界测量校准（顶刊体例） |
| `docs/step1-result-report.md` | 第 1 步早期报告 |
| `docs/step1-plan.md` / `step1-plan-v2.md` | 第 1 步计划 |
| `docs/step2-result-report-v3.md` | **第 2 步主报告**（24 年商品、Θ_c） |
| `docs/step2-result-report-v2.md` / `step2-result-report.md` | 早期第 2 步 |
| `docs/step3-result-report.md` | 第 3 步 HMM/识别 |
| `docs/step4-result-report.md` | 第 4 步经济价值 |
| `docs/rb-specific-timeline-2026-11-26.md` | 螺纹钢专项时间线（含片段缺口说明） |

## 四、给老板的可读汇总与论文稿

| 文件 | 说明 |
|------|------|
| `docs/experiment-boss-brief-2026-11-25.md` | 按初始方案六步：原文 + 无数字结论 |
| `docs/experiment-walkthrough-plain-2026-11-25.md` | 白话逐步走读 |
| `docs/manuscript-who-pays-china-futures-2026-11-25.md` | 顶刊体例实证稿（中国期货） |
| `docs/working-paper-china-futures-empirical-2026-11-25.md` | Working paper 简版 |
| `docs/empirical-results-china-futures-2026-11-25.md` | 实证结果汇编 |
| `docs/theory-empirics-integration-2026-11-25.md` | 理论与实证衔接 |

## 五、内部运行记录与质检（非对外正文）

| 文件 | 说明 |
|------|------|
| `internal/step2-real-run-2026-11-24.md` 等 | 各步真实数据运行日志 |
| `internal/theory-and-20y-compliance-audit-2026-11-24.md` | 20 年与理论框合规审计 |
| `internal/quality-checklist-2026-11-24.md` | 质量清单 |
| `internal/journal-reporting-referee-qa-2026-11-24.md` | 审稿人 Q&A |
| `docs/thought-log.md` | 对话与决策补记 |
| `preferences.md` | 汇报偏好（老板白话、不堆 p 值） |

## 六、工具脚本（store 内）

| 文件 | 说明 |
|------|------|
| `internal/rb-timeline-export.py` | 导出池化状态 ≥10 日片段日期（需 data/raw） |
| `internal/rb-timeline-recompute-2026-11-26.md` | 复算说明 |

## 七、代码与数值产物（**不在此 zip**）

- 仓库：`https://github.com/hvalo596/regime-adaptive-quant`
- 建议分支：`cursor/step2-real-futures-2dd4`（含 step2 主结果提交）
- 路径：`artifacts/step2/`、`artifacts/step3/`、`artifacts/step4/`（`coverage_products.csv`、`state_segments.csv`、trial_ledger 等）
- 原始行情：`data/raw/`（gitignore，需 `TUSHARE_TOKEN` 本地 `fetch`）

## 八、打包时未完成的条目（若在下载之后补齐）

- `docs/commodity-years-and-pooled-switches-2026-11-26.md`：40 品种各多少年 + 整盘切换日历（worker 导出中）
- `docs/pooled-state-segments-ge10.csv`：池化状态片段起止日

解压后建议从 `docs/experiment-boss-brief-2026-11-25.md` 或 `docs/PACKAGE-README-2026-11-26.md`（本文件）开始阅读。