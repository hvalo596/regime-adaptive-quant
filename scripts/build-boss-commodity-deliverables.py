#!/usr/bin/env python3
"""Build commodity-years table and pooled state segments (>=10d) for boss deliverables."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/agent/repos/regime-adaptive-quant")
STORE = Path("/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291")
COV = REPO / "artifacts/step2/coverage_products.csv"
COV_PANEL = REPO / "artifacts/step2/coverage_panel.csv"
RAW = REPO / "data/raw"
OUT_MD = STORE / "docs/commodity-years-and-pooled-switches-2026-11-26.md"
OUT_CSV = STORE / "docs/pooled-state-segments-ge10.csv"
SEGMENTS_SUMMARY = REPO / "artifacts/step2/state_segments.csv"


def commodity_years_table() -> pd.DataFrame:
    prod = pd.read_csv(COV)
    com = prod[prod.panel == "commodity"].copy()
    com["first_return_in_panel"] = pd.to_datetime(com["first_return_in_panel"])
    com["last"] = pd.to_datetime(com["raw_last_bar"])
    com["calendar_years"] = (com["last"] - com["first_return_in_panel"]).dt.days / 365.25
    com["meets_20y"] = np.where(com["calendar_years"] >= 20.0, "Y", "N")
    return com[["product", "first_return_in_panel", "last", "calendar_years", "meets_20y"]].rename(
        columns={"product": "symbol", "last": "last_in_panel"}
    )


def try_fetch() -> tuple[bool, str]:
    if RAW.is_dir() and any(RAW.iterdir()):
        return True, "data/raw present"
    tok = bool(os.environ.get("TUSHARE_TOKEN") or os.environ.get("TUSHARE"))
    if not tok:
        return False, "no TUSHARE_TOKEN/TUSHARE in env"
    cmd = [
        sys.executable,
        str(REPO / "scripts/fetch_tushare_futures.py"),
        "--group",
        "commodity",
    ]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        return False, f"fetch exit {p.returncode}: {p.stderr.strip()[:200]}"
    return RAW.is_dir(), "fetch ok"


def pooled_segments_df() -> tuple[pd.DataFrame | None, str]:
    sys.path.insert(0, str(REPO / "src"))
    from regime_quant.step2 import Ledger, analyze_panel, load_real  # noqa: E402
    from regime_quant.statemachine import segments  # noqa: E402

    if not RAW.is_dir():
        return None, "missing data/raw"
    cal = json.loads((REPO / "artifacts/step2/calibration_commodity.json").read_text())
    ret = load_real(RAW).panels["commodity"].returns
    pr = analyze_panel("commodity", ret, cal, Ledger())
    dates = ret.index
    valid = np.asarray(pr.run.valid, dtype=bool)
    lab = np.asarray(pr.labels, dtype=object)
    rows = []
    for state in ("I", "II", "III", "IV"):
        for a, b in segments(lab, state, 10):
            if not valid[a:b].all():
                continue
            rows.append(
                {
                    "start_date": dates[a].strftime("%Y-%m-%d"),
                    "end_date": dates[b - 1].strftime("%Y-%m-%d"),
                    "state": state,
                    "length_days": b - a,
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["start_date", "state"]).reset_index(drop=True)
    return df, "ok"


def md_table(df: pd.DataFrame) -> str:
    d = df.copy()
    d["first_return_in_panel"] = pd.to_datetime(d["first_return_in_panel"]).dt.strftime("%Y-%m-%d")
    d["last_in_panel"] = pd.to_datetime(d["last_in_panel"]).dt.strftime("%Y-%m-%d")
    d["calendar_years"] = d["calendar_years"].map(lambda x: f"{x:.2f}")
    cols = ["symbol", "first_return_in_panel", "last_in_panel", "calendar_years", "meets_20y"]
    hdr = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = ["| " + " | ".join(str(d.iloc[i][c]) for c in cols) + " |" for i in range(len(d))]
    return "\n".join([hdr, sep, *body])


def main() -> int:
    years = commodity_years_table()
    panel = pd.read_csv(COV_PANEL)
    cp = panel[panel.panel == "commodity"].iloc[0]

    raw_ok, fetch_note = try_fetch()
    seg_df, seg_note = pooled_segments_df()

    if seg_df is not None:
        seg_df.to_csv(OUT_CSV, index=False)
        seg_rows = len(seg_df)
    else:
        seg_rows = 0
        pd.DataFrame(columns=["start_date", "end_date", "state", "length_days"]).to_csv(OUT_CSV, index=False)

    summary = pd.read_csv(SEGMENTS_SUMMARY)
    n_y = int((years.meets_20y == "Y").sum())
    n_n = int((years.meets_20y == "N").sum())

    sample = ""
    if seg_df is not None and len(seg_df):
        cols = ["start_date", "end_date", "state", "length_days"]
        hdr = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * 4) + " |"
        rows = []
        for i in range(min(20, len(seg_df))):
            r = seg_df.iloc[i]
            rows.append(f"| {r.start_date} | {r.end_date} | {r.state} | {r.length_days} |")
        sample = "\n".join([hdr, sep, *rows])

    blocker = ""
    if seg_df is None:
        blocker = (
            f"\n\n> **阻塞**：池化带日期的片段需 `data/raw` 重算日度标签。"
            f" 本次 VM：`data/raw`={'有' if raw_ok else '无'}；凭据：{fetch_note}；导出：{seg_note}。"
            f" 汇总级片段计数仍见 `artifacts/step2/state_segments.csv`（无起止日）。\n"
        )

    md = f"""---
cursor:
  subagentId: "bc-b34e7051-09ba-5930-ba97-12b7c723c744"
---

# 商品年限与池化状态切换（2026-11-26）

数据源：`artifacts/step2/coverage_products.csv`、`coverage_panel.csv`；池化片段与 `state_segments.csv` 对照。分支 `cursor/step2-real-futures-2dd4`。

## 一、年限表（40 个商品品种）

**池化面板**（全品种）：分析窗 `{cp.analysis_first_day}`～`{cp.analysis_last_day}`，共 **{int(cp.analysis_days)}** 个分析日，约 **{float(cp.analysis_span_years):.2f}** 日历年，`meets_min_years`：**{cp.meets_min_years}**（门槛 20 年）。

**单品种口径**：自各品种 `first_return_in_panel` 至 `raw_last_bar` 的日历年；满 20 年记 **Y**，否则 **N**。满 20 年：**{n_y}** 个；不满：**{n_n}** 个。

{md_table(years)}

## 二、整盘切换日历（池化 valid 日，连段 ≥10 日）

| 象限 | valid 日数 | ≥10 日片段数 | 均长（日） |
| --- | ---: | ---: | ---: |
"""
    for _, r in summary.iterrows():
        md += f"| {r['state']} | {int(r['days'])} | {int(r['segments_ge10d'])} | {r['mean_length']:.1f} |\n"

    md += f"\n**已导出 dated 片段行数**：**{seg_rows}**（完整表：`docs/pooled-state-segments-ge10.csv`）。\n"
    md += blocker

    if sample:
        md += "\n### 前 20 段样例（按 start_date 排序）\n\n" + sample + "\n"
    elif seg_df is None:
        md += "\n### 前 20 段样例\n\n*（无日度数据，待 `data/raw` + 导出脚本复算后补齐。）*\n"

    md += f"""
## 复算

```bash
cd {REPO}
pip install -e .
# 若无 data/raw：export TUSHARE_TOKEN=...  # 或 Secret 名 TUSHARE
python scripts/fetch_tushare_futures.py --group commodity
python {STORE}/internal/build-boss-commodity-deliverables.py
```
"""
    OUT_MD.write_text(md)
    print(
        json.dumps(
            {
                "commodity_rows": len(years),
                "meets_20y_Y": n_y,
                "meets_20y_N": n_n,
                "pooled_segment_rows": seg_rows,
                "data_raw_ok": raw_ok,
                "fetch_note": fetch_note,
                "segment_note": seg_note,
            },
            indent=2,
        )
    )
    return 0 if seg_df is not None else 3


if __name__ == "__main__":
    raise SystemExit(main())