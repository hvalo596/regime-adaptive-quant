# 文档总导航：市场状态切换的量化策略自适应研究

本目录把项目文档按两大块整理。**块 B 的代码不在这里**：代码在仓库根目录的 `src/`、`scripts/`、`tests/`，产物在 `artifacts/`（见根目录 [README](../README.md)）。

## 两块的关系

| 块 | 内容 | 位置 |
|---|---|---|
| **块 A：思想与方案** | 为什么做、赚谁的钱、状态怎么定义、背景资料、偏好与思想记录、被取代的旧文档 | [`A-idea/`](./A-idea/)、原始资料 [`A-raw/`](./A-raw/) |
| **块 B：实验与代码** | 实验方案、结果报告（仍是文档）；对应的代码和产物在仓库根目录 | [`B-experiment/`](./B-experiment/)；代码 `../src/`、`../scripts/`、`../tests/`、`../artifacts/` |

## 目录结构

```
docs/
  README.md        本文件
  index.md         项目文库索引：每个文件的状态与一句话；块 B 的代码目录树、测试表、产物词汇表、理论章节→代码映射
  A-idea/
    core/          核心思想：research-core-tree、strategy-money-explained、project-context、regime-identification-why
    theory/        state-construction（理论地基，已批准）
    background/    kai-dims-and-experiment-steps（刑凯四维与实验步骤背景）
    meta/          preferences、thought-log（项目偏好与思想源泉记录）
    archive/       被取代的旧文档：step1-plan、step2-result-report、regime-identification-why-sonnet-v1
  A-raw/           原始资料：研究方案（txt/docx）、刑凯微信截图、Tushare 权限检查（不含 token）
  B-experiment/    step1-plan-v2、step1-result-report、step1-paper-report、step2-result-report-v2
  phase2-*.md      旧阶段 2 文档（原样保留，结论不再沿用）
```

## 建议阅读顺序

1. 想先看全貌：[B-experiment/step1-paper-report.md](./B-experiment/step1-paper-report.md)（第 1 步论文式报告）。
2. 想理解"为什么这么做"：[core/strategy-money-explained](./A-idea/core/strategy-money-explained.md)（白话）→ [core/research-core-tree](./A-idea/core/research-core-tree.md)（核心思想树）→ [core/regime-identification-why](./A-idea/core/regime-identification-why.md)（核心论证）。
3. 想看状态怎么定义与检验：[theory/state-construction](./A-idea/theory/state-construction.md)。
4. 想看实验：[step1-plan-v2](./B-experiment/step1-plan-v2.md) → [step1-result-report](./B-experiment/step1-result-report.md) → [step2-result-report-v2](./B-experiment/step2-result-report-v2.md)。
5. 想找某段代码或数字的出处：[index.md](./index.md) 的块 B 与"理论章节 → 代码模块"映射表。

## Context 与 GitHub 的双副本关系

- 这些文档最初维护在 Cursor Project 的 Context（Agent Store）里；本目录是 2026-11-24 同步到 GitHub 的副本，方便在仓库中浏览、引用和随代码版本管理。
- 同步时：文件内容原样复制，只把指向 Context 绝对路径的链接改写为仓库内相对路径，并在文首加一行 `synced from Project Context` 注释。
- **Context 里的版本对 Agent 仍可能是权威来源**（尤其是持续更新的 `thought-log.md`、`preferences.md`）；这里的副本是快照，之后两边可能出现差异，以日期和提交为准。
- 被取代的文档放在 `A-idea/archive/`，仅供对照，不再引用其结论。
- 仓库不含任何密钥：Tushare token 只通过环境变量 `TUSHARE_TOKEN` 提供，不落盘。
