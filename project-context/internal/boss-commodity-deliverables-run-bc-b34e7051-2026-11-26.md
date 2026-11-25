---
cursor:
  subagentId: "bc-b34e7051-09ba-5930-ba97-12b7c723c744"
---

# Boss 交付物导出 — worker 结果

- 时间（上海）：2026-11-26
- 仓库：`/agent/repos/regime-adaptive-quant`，分支 `cursor/step2-real-futures-2dd4` @ `0ae4360`
- 凭据：`TUSHARE_TOKEN` / `TUSHARE` 在 shell **均未设置**；`list-available-secrets` 有个人 secret `TUSHARE`（`bound: false` → 后 bound 到 app，**不进 worker env**）
- `data/raw`：**不存在**
- Fetch：未调用（无凭据）；探针 `fetch_tushare_futures.py --products RB` → MissingTokenError
- 年限表：**40** 行；`meets_20y`：**10** Y / **30** N
- 池化 dated 片段 CSV：**0** 行（仅表头）；汇总级 `state_segments.csv` 仍有效（29+19+11+33 段，无日期）

## 产出

| 路径 | 状态 |
| --- | --- |
| `docs/commodity-years-and-pooled-switches-2026-11-26.md` | 年限表 + 汇总切换表 + 阻塞说明 |
| `docs/pooled-state-segments-ge10.csv` | 表头占位，待 `data/raw` |
| `internal/build-boss-commodity-deliverables.py` | 一键复算 |
| `scripts/export_pooled_state_segments.py`（repo） | 片段导出 |
| `src/regime_quant/data/tushare_client.py` | 可读 `TUSHARE` 别名 |

## 解除阻塞

在 worker shell 注入 `TUSHARE_TOKEN`（或 `export TUSHARE=...`）后：

```bash
cd /agent/repos/regime-adaptive-quant
pip install -e .
python scripts/fetch_tushare_futures.py --group commodity
python /cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/build-boss-commodity-deliverables.py
```

预期片段行数约 **92**（与 `state_segments.csv` 四象限 `segments_ge10d` 之和一致）。