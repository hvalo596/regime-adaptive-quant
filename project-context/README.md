# Project Context（课题上下文镜像）

本目录是从 Cursor Project **「市场状态切换的量化策略自适应研究」** 同步下来的**只读上下文包**：讨论记录、分步报告、内部质检与运行笔记、汇报偏好等。与仓库里的**可运行代码**分开存放，便于在 GitHub 上浏览与归档，而不混入 `src/` / `scripts/` 的实现逻辑。

## 怎么用

1. **先看分类索引**：[docs/archive/00-分类总索引.md](docs/archive/00-分类总索引.md)（理论 / 讨论 / 实证产出 / 归档清单）。
2. **老板向结论**：[docs/experiment-boss-brief-2026-11-25.md](docs/experiment-boss-brief-2026-11-25.md)、[preferences.md](preferences.md)。
3. **Step 1–4 对外报告**：`docs/step*-result-report*.md`；内部跑数证据在 `internal/step*-real-run-*.md`。
4. **一键打包说明**：[docs/PACKAGE-README-2026-11-26.md](docs/PACKAGE-README-2026-11-26.md)（不含 zip，仓库内不附带 Project store 的 bundle）。

部分 Markdown 里仍保留指向 Cursor Project store 的绝对路径链接（历史写法）；在本仓库中请以 **`project-context/` 下的相对路径** 为准。

## 与代码分支的关系

- 本快照基于开发分支 **`cursor/step2-real-futures-2dd4`**（中国期货 Step 2 真数据链及相关脚本）。
- 同步分支：**`cursor/sync-project-context-2026-11-26`**。

## 实证 CSV / JSON 在哪里

**回测与校准的数值产物不在此目录**，仍在仓库根目录：

| 内容 | 路径 |
|------|------|
| Step 2 状态机与校准 | `artifacts/step2/` |
| Step 3 事件与 spell | `artifacts/step3/` |
| Step 4 绩效与对照 | `artifacts/step4/` |

`project-context/docs/pooled-state-segments-ge10.csv` 等为**说明性导出表**（无 token 环境下可能仅表头）；完整复现请在本机具备 `data/raw` 或 `TUSHARE_TOKEN` 后运行 `scripts/export_pooled_state_segments.py` 等脚本。

## 目录结构

- `docs/` — 对外可读文档、论文稿、archive 索引与子清单。
- `internal/` — 协调与工人运行记录、质检、辅助脚本副本（与 `scripts/` 中同名工具以仓库 `scripts/` 为准）。
- `preferences.md` — ieki 的汇报与推进偏好。

## 安全说明

同步时已排除 Project store 中的 zip bundle；仓库内**不含** Tushare 或其它 API 凭据。勿在此目录提交 token。