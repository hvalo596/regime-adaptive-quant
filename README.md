# regime-adaptive-quant

基于市场状态切换的量化策略自适应机制研究（期货；**中国期货先行，美国后置**）。

核心问题：能否通过识别"此刻谁在付钱"，在**动量**（收慢人的迟到费）与**短期反转**（收急人的加急费）之间做出有信息量的配置？
理论地基是 `state-construction.md`（5 个状态 = 慢人 × 急人 四象限 + 知情冲击叠加；3 个定义变量 $M,R,C$ + 2 个环境变量 $V,\Phi^\perp$；选择信号 $s_t=\delta^M_t-\delta^R_t$，主检验量 $\Theta=\mathbb E[s_tD_{t+1}]$）。

## 进度

| 步骤 | 状态 |
|---|---|
| 第 1 步：资产、回测引擎、合成世界、状态变量构造、假阳性校准 | 完成，见 `artifacts/step1/`（通过标准与数字见报告） |
| 第 2 步：真实中国期货上的状态存在性检验 | 进行中（见 Step 2 的 PR，叠在本 PR 之上） |
| 第 3 步及以后（HMM 等） | 未开始 |

早先的阶段 1/2（PR #1、#2：VR 与刑凯四维草案的三分位检验）已被本版取代；其产物仍留在 `artifacts/phase*`，仅供对照，结论不再沿用。

## 快速开始

```bash
pip install -e ".[dev]"
pytest -q                                                    # 单元测试 + 引擎对账 + 防偷看
python scripts/run_step1.py --out artifacts/step1 --scale 0.1   # 第 1 步（--scale 1.0 为完整版，约 45 分钟/4 核）
python scripts/summarize_step1.py artifacts/step1               # 验收判定 → acceptance.json、summary.md
```

真实数据（第 2 步）的抓取与运行脚本在第 2 步 PR 中。

## 代码结构（`src/regime_quant/`）

```
config.py        锁定的参数（M-B/M-A/R-A/R-B/R-B-gap、阈值、驻留）
rolling.py       向量化滚动工具（无前视）
statevars.py     §3 变量：标准化、留一法因子、M/R/R^gap、C 与 F、V 与 Φ⊥
statemachine.py  滞后带 + 最短驻留，象限与 s_t
backtest.py      向量化引擎、腿、状态组合（κ、剔除 F）、成本
eventengine.py   逐日流式引擎（与 backtest.py 不共用代码），逐日对账
pipeline.py      端到端：收益面板 → 变量 → 状态 → 回测
inference.py     平稳块自助、循环平移零分布、Θ 检验（中心化）
hypotheses.py    H5 事件检验、δ 关联检验、以及第 2 步 H 系列检验
world.py         §7 合成世界与无状态对照 N0/N0z/N1/N2/N2c/N2b/N3/N4
nullcal.py       偏差 b、标准误倍数、C 零分布（一次性校准后固定）
recovery.py      找回 AUC、识别延迟与 d* 公式
step1.py         第 1 步实验任务
data/            Tushare 客户端、缓存、自己做的换月、面板、标记
```

## 设计要点

- **点时间一致**：状态变量只用 t 日收盘及以前；仓位 t+1 才赚钱；`tests/test_engine.py` 篡改未来数据，断言所有变量、状态、权重不变。
- **收益一律同合约收盘到收盘**；换月日没有假跳空；结算价只用于对照。
- **两套回测实现**逐日对账（向量化 vs 逐日流式），差异 < 1e-10。
- **Θ 用中心化形式 Cov(s, D) 做判定**：只要 $E[s]\ne0$ 且 $E[D]\ne0$（例如动量有无条件溢价），未中心化的 $E[sD]$ 就会在没有任何状态的世界里为正，这是配置倾斜而不是择时。
- 与理论文档的偏离全部列在第 1 步报告里并带理由（$\mathcal F$ 的定义、$C$ 阈值的校准方式、Θ 的中心化、$N_{\rm eff}$ 的窗口、合成世界的体量中性参数化等）。
