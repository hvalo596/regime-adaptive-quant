---
cursor:
  subagentId: "bc-56e21e5e-7070-5514-a67c-94d023f05695"
---

# RB 日度片段 / HMM 上穿日复算 — 本次 worker 结果

- 时间（上海）：2026-11-26
- 仓库：`/agent/repos/regime-adaptive-quant`，`cursor/step2-real-futures-2dd4` @ `0ae4360224b1bbcb17aceb9cd28e843efa08bd56`
- `TUSHARE_TOKEN`：`env` 中 **无**（`list-available-secrets` 显示个人 secret 名 `TUSHARE`，`servesApp: true`，`bound: false`）
- `data/raw`：**不存在**
- Fetch：`python3 scripts/fetch_tushare_futures.py --products RB,CU,AL,RU,A,M --start-date 20040102` → exit **3**（MissingTokenError）
- Export：`python3 .../internal/rb-timeline-export.py` → exit **2**（missing data/raw）

**行数**：池化 dated 片段 **0**；p^M 上穿 **0**；p^R 上穿 **0**。

交付：`docs/rb-specific-timeline-2026-11-26.md` §2.3.1 / §3.3 已改为本次阻塞说明（非完整表体）。扩展脚本见 `internal/rb-timeline-export.py`；说明见 `internal/rb-timeline-recompute-2026-11-26.md` 末段。

**解除阻塞**：在 worker shell 注入 `TUSHARE_TOKEN`（或挂载含 `data/raw` 的快照），`fetch` 商品组（缓存则秒级 skip），再跑 export 并把 CSV/txt 整表写回交付页。