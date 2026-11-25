---
cursor:
  subagentId: "bc-6b7d1666-a554-5522-9f22-072ff9ef35e6"
---

# RB 日度片段 / HMM 转换日复算说明

Worker VM @ `0ae4360` **无** `data/raw`。下列表项仅在挂载 Tushare 缓存后可从代码复算（与 `artifacts/step2` 校准 JSON 一致）：

1. `RB.notna() & run.valid` 的首末日、四象限日计数  
2. ≥10 日 dated 片段（RB 连段 + 池化连段及段内 `rb_active_days`）  
3. 2009+ `p^M>0.5` / `p^R>0.5` 上穿日（前 30 / 后 30 / 总数）

最小路径（在已抓取 `data/raw` 的机器上）：

```bash
cd /agent/repos/regime-adaptive-quant
pip install -e .
python -c "
import json, numpy as np, pandas as pd
from pathlib import Path
from regime_quant.step2 import Ledger, analyze_panel, load_real
from regime_quant.step34 import build_states, signals
from regime_quant.step34_run import evaluate_all
from regime_quant.statemachine import segments
R=Path('.')
cal=json.loads((R/'artifacts/step2/calibration_commodity.json').read_text())
ret=load_real(R/'data/raw').panels['commodity'].returns
pr=analyze_panel('commodity', ret, cal, Ledger())
dates, valid, lab = ret.index, pr.run.valid, np.asarray(pr.labels, dtype=object)
rb=ret['RB'].notna().to_numpy() & valid
print('RB valid days', rb.sum(), dates[np.flatnonzero(rb)[0]].date(), dates[np.flatnonzero(rb)[-1]].date())
for k in 'I','II','III','IV': print(k, (lab[rb]==k).sum())
st=build_states(ret.to_numpy(float), cal)
common=evaluate_all(st, signals(st), ret.to_numpy(float))
for name,p in [('pM',st.pm),('pR',st.pr)]:
 m=common & np.isfinite(p) & (dates>=pd.Timestamp('2009-01-01'))
 cur=(p>.5)&m; trans=cur & ~np.r_[False,cur[:-1]]
 d=[str(dates[i].date()) for i in np.flatnonzero(trans)]
 print(name, 'transitions', len(d)); print(' first', d[:30]); print(' last', d[-30:])
"
```

输出应写回 [`docs/rb-specific-timeline-2026-11-26.md`](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/docs/rb-specific-timeline-2026-11-26.md) §2.1 / §2.3 / §3.3。

---

## 扩展导出脚本（2026-11-26）

完整脚本：[`internal/rb-timeline-export.py`](/cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/rb-timeline-export.py)。相对上文内联片段的增量：

1. **RB ∩ valid** 首末日 + 四象限日计数 → `rb-timeline-meta-2026-11-26.json`
2. **池化 valid 且 ≥10 日** 的**全部**连段（四象限合并一张表）列：`start_date`, `end_date`, `state`, `length_days`, `rb_active_days_inside` → `rb-pooled-segments-ge10-2026-11-26.csv`
3. **2009-06-26 起**（非 2009-01-01）且在 `evaluate_all` 公共掩码内的 `p^M`、`p^R` **上穿 0.5** 日全表 → `rb-hmm-pM-upedges-from-2009-06-26.txt`、`rb-hmm-pR-upedges-from-2009-06-26.txt`

```bash
cd /agent/repos/regime-adaptive-quant
export TUSHARE_TOKEN=...   # 或已有 data/raw 则不必
# 若无 data/raw：python scripts/fetch_tushare_futures.py --group commodity   # 或 --group all 走缓存
pip install -e .
python /cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/rb-timeline-export.py
```

将 CSV 与前 15 / 后 15 上穿日粘贴进交付页 §2.3 / §3.3。