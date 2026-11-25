---
cursor:
  subagentId: "bc-e8346353-8925-5663-8ffd-c0dd192acde5"
---

# GitHub 文档同步记录（2026-11-24）

- 仓库：hvalo596/regime-adaptive-quant；分支 `cursor/docs-sync-cde5`（基于 `cursor/step2-real-futures-2dd4`）。
- PR：https://github.com/hvalo596/regime-adaptive-quant/pull/3 （base = `cursor/step2-real-futures-2dd4`，因第 1/2 步分支尚无到 main 的 PR；两步合并后改指 main）。
- 同步内容（19 个内容文件 + 2 个新写文件）：
  - `docs/A-idea/core`：research-core-tree、strategy-money-explained、project-context、regime-identification-why
  - `docs/A-idea/theory`：state-construction；`background`：kai-dims-and-experiment-steps；`meta`：preferences、thought-log
  - `docs/A-idea/archive`：step1-plan、step2-result-report、regime-identification-why-sonnet-v1（均被取代）
  - `docs/A-raw`：research-proposal.txt/.docx、kai-wechat-screenshot.png、tushare-access-check.md
  - `docs/B-experiment`：step1-plan-v2、step1-result-report、step1-paper-report、step2-result-report-v2
  - `docs/index.md`（由 project-library-index 改写，A.6/A.7 改成仓库布局）、`docs/README.md`（新写总导航）；根 README 增加 "文档" 小节。
  - 原有 `docs/phase2-*.md` 保持不动。
- 链接改写：`/cursor/stores/<id>/docs|internal/FOO` 与 `.../preferences.md` 一律改成按新布局计算的相对路径；每个 .md 文首加 `<!-- synced from Project Context 2026-11-24; ... -->`（有 frontmatter 的放在其后）。相对链接已脚本校验全部可达。正文中不带链接的 `internal/research-proposal.txt` 之类提法未改写。
- 安全：未含 token；已扫描长十六进制/密钥串，无命中。
- pytest 未跑（VM 未装 pytest，且仅文档改动）。
- Context 仍是 Agent 的权威来源；thought-log、preferences 之后会漂移，需再次同步。
