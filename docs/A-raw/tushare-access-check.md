---
cursor:
  subagentId: "bc-497ae948-162e-5e13-b674-647bcc188b4d"
---
<!-- synced from Project Context 2026-11-24; canonical for agents may remain Context -->

# Tushare 期货接口权限与数据可得性检查

检查日期：2026-11-18（数据最新到 2026-11-17 / 映射到 2026-11-18）。token 仅在 shell 会话内使用，未写入任何文件；本文不含 token。

## 结论（先看这里）

- **token 有效**。期货日线、主力/连续映射、合约基础信息、持仓排名、仓单、结算参数、交易日历全部可用，**没有任何一个期货日频接口报积分/权限错误**。
- **被积分/权限挡住的只有分钟级**：`ft_mins`、`rt_fut_min` 报"没有接口访问权限"；`rt_fut_dk` 报"请指定正确的接口名"（本账号/版本无此接口）。
- **海外/国际期货：没有对应接口**。`fut_daily` 传 `exchange=CME` 返回 0 行；未发现国际期货行情接口。但外汇 `fx_daily`、全球指数 `index_global`、美股 `us_daily`、上金所 `sge_daily` 可用（非期货，可作外部参照）。
- **足够构建展期调整的连续序列**：股指（IF/IH/IC/IM）、国债（TS/TF/T/TL）、主要商品（RB/CU/AU/M/I/SR/TA/SC/SI 等）。逐合约日线 + 合约元数据（上市/退市/最后交易日）+ 官方映射齐全，OHLC、结算价、成交量、持仓量均有。限制与注意点见下文"坑"。

## 逐接口结果

| 接口 | 状态 | 行数/范围 | 字段 | 备注 |
|---|---|---|---|---|
| `fut_basic`（fut_type=1 普通合约） | 可用 | CFFEX 696（上市自 20100416）；SHFE 3632（自 19950417）；DCE 3320（自 19990104）；CZCE 2934（自 19990104 起）；INE 488（自 20180326）；GFEX 147（自 20221222） | ts_code, symbol, exchange, name, fut_code, multiplier, trade_unit, per_unit, quote_unit, quote_unit_desc, d_mode_desc, list_date, delist_date, d_month, last_ddate | 含已退市合约，一次返回无截断 |
| `fut_basic`（fut_type=2 连续合约） | 可用 | CFFEX 36；SHFE 40；DCE 52；CZCE 67；INE 12；GFEX 10 | 同上 | 如 `IF.CFX`、`IML.CFX`、`IML1.CFX`、`TSL.CFX`、`SC.INE`、`SCL.INE` 等（主力、L 加权/连续等） |
| `fut_daily` | 可用 | 见下表；单次最多 2000 行，需按日期分页 | ts_code, trade_date, pre_close, pre_settle, open, high, low, close, settle, change1, change2, vol, amount, oi, oi_chg | 支持按 ts_code（单合约/连续码）或按 trade_date(+exchange) 拉取 |
| `fut_mapping` | 可用 | 见下表；单次最多 5000 行 | ts_code, trade_date, mapping_ts_code | 到 20261118（含当日） |
| `fut_holding` | 可用 | 2010-04-16：2250 行；2024-11-15 全市场 ≥4000 行（触顶 4000）；2005-06-07 有 561 行；2002-01-04 / 2000-01-04 为 0 | trade_date, symbol, broker, vol, vol_chg, long_hld, long_chg, short_hld, short_chg | 无 exchange 列；按 exchange 过滤：CFFEX 754、SHFE 2519、DCE 1775、CZCE 3139、GFEX 142、INE 0（20241115）；单次上限 4000 行，全市场需分交易所/合约拉 |
| `fut_wsr`（仓单） | 可用 | 20241115 全市场 1312 行；SHFE 377；20150105 427；20080104 31；20070104 为 0 | trade_date, symbol, fut_name, warehouse, pre_vol, vol, vol_chg, unit | 必须指定 trade_date 或 symbol（只给 start/end 报"参数校验失败, trade_date,symbol参数不能都为空"）；symbol 要用品种代码如 `CU`，中文"铜"返回 0；单次上限 1500 行；最早约 2008 |
| `trade_cal` | 可用 | CFFEX 自 20060908；SHFE 自 19910528；DCE 自 19930301；CZCE 自 19901012；INE 自 20170523；GFEX 自 20221222；均到 20261231 | exchange, cal_date, is_open, pretrade_date | 各交易所日历独立 |
| `fut_settle`（结算参数） | 可用 | 20241115 SHFE 214 行 | ts_code, trade_date, settle, trading_fee_rate, trading_fee, delivery_fee, b/s_hedging_margin_rate, long/short_margin_rate | 含保证金率、手续费，可用于成本/保证金建模 |
| `fut_weekly_monthly` | 可用 | IF.CFX 周线 851 行，20100416 起 | 18 列 | 周/月线汇总 |
| `fut_weekly_detail` | 返回 0 行（无权限错误） | 0 | 17 列 | 参数 `prd=CU`、2024-01~10 无数据，可能参数不对，未深究 |
| `ft_mins`（期货历史分钟） | **权限错误** | - | - | 原文：`抱歉，您没有接口(ft_mins)访问权限，权限的具体详情访问：https://tushare.pro/document/1?doc_id=108。`（单合约、连续码两种都试过） |
| `rt_fut_min`（实时分钟） | **权限错误** | - | - | 原文：`抱歉，您没有接口(rt_fut_min)访问权限，...` |
| `rt_fut_dk` | 接口名不存在 | - | - | `请指定正确的接口名` |
| 海外期货（`fut_daily` exchange=CME） | 无数据 | 0 行 | - | 没找到国际期货接口 |
| `fx_daily`（XAUUSD.FXCM） | 可用 | 316 行（2024 全年） | 11 列 | 非期货，外汇/黄金参照；`fx_obasic` 69 个品种 |
| `index_global`（SPX） | 可用 | 252 行 | 11 列 | 全球指数 |
| `us_daily`、`sge_daily`、`index_daily`（000300.SH）、`fund_daily`（510300.SH） | 可用 | 11 / 52 / 242 / 11 行 | - | 可作现货/ETF 基差参照 |

## fut_daily / fut_mapping 日期覆盖（连续码，均无报错）

| 品种 | fut_daily 起止 | 行数 | fut_mapping 起止 | 映射合约数 |
|---|---|---|---|---|
| IF.CFX | 20100416–20261117 | 4028 | 20100416–20261118 | 183 |
| IH.CFX | 20150416–20261117 | 2817 | 20150416–20261118 | 124 |
| IC.CFX | 20150416–20261117 | 2817 | 20150416–20261118 | 126 |
| IM.CFX | 20220722–20261117 | 1047 | 20220722–20261118 | 35 |
| TS.CFX | 20180817–20261117 | 1999 | 20180817–20261118 | 33 |
| TF.CFX | 20130906–20261117 | 3205 | 20130906–20261118 | 53 |
| T.CFX | 20150320–20261117 | 2835 | 20150320–20261118 | 46 |
| TL.CFX | 20150320–20261117（见"坑"） | 2835 | 20150320–20261118 | 46 |
| RB.SHF | 20090327–20261117 | 4286 | 20090327–20261118 | 57 |
| CU.SHF | 19950417–20261117 | 7674 | 19950417–20261118 | 376 |
| AU.SHF | 20080109–20261117 | 4581 | 20080109–20261118 | 57 |
| M.DCE | 20000717–20261117 | 6394 | 20000717–20261118 | 87 |
| I.DCE | 20131018–20261117 | 3182 | 20131018–20261118 | 39 |
| SR.ZCE | 20060106–20261117 | 5069 | 20060106–20261118 | 68 |
| TA.ZCE | 20061218–20261117 | 4838 | 20061218–20261118 | 71 |
| SC.INE | 20180326–20261117 | 2098 | 20180326–20261118 | 98 |
| SI.GFE | 20221222–20261117 | 944 | 20221222–20261118 | 28 |

注：SC 原油上期能源所代码后缀是 `.INE`，工业硅/碳酸锂等广期所后缀是 `.GFE`，郑商所 `.ZCE`，上期所 `.SHF`，大商所 `.DCE`，中金所 `.CFX`。

单合约日线（按 ts_code）示例：IF2412.CFX 164 行（20240422–20241220）、IF1005.CFX 25 行（20100416 起）、T1512.CFX 181 行（20150320 起）、RB1001.SHF 200 行（20090327 起）、CU0001.SHF 143 行（19990618 起）、SC1809.INE 110 行（20180326 起）。`M0001.DCE` 返回 0（该合约代码可能不存在，应以 fut_basic 列表为准）。

按交易日拉全市场 `fut_daily`：19950103 为 0；19990104 为 39 行；20000104 为 39；20060104 为 121；20100416 为 280；20241115 分交易所 CFFEX 64 / SHFE 250 / DCE 255 / CZCE 284 / INE 77 / GFEX 28。

## 展期可行性验证（2023–2024 抽样，IF/RB/T/M）

对 fut_basic 列出的当期合约逐个拉 `fut_daily` 后与官方映射比较：

| 品种 | 合约数 | 逐合约日线行数 | 映射=最大持仓合约占比 | 映射切换次数 | 连续码 close == 映射合约 close |
|---|---|---|---|---|---|
| IF | 28 | 1936 | 39.5% | 24（每月一次） | 100% |
| RB | 36 | 5808 | 95.9% | 7 | 100% |
| T | 11 | 1452 | 97.1% | 9 | 100% |
| M | 24 | 3872 | 91.9% | 7 | 100% |

含义：
- 连续码 `XX.EXC` 的日线就是"当日映射合约"的**未调整**拼接价，存在展期跳空（RB/M 单日最大跳 6%/14%，IF 8.7%）。要做**展期调整**必须自己用逐合约日线，不能直接用连续码。
- **股指期货的官方映射实际是每月换到当月/近月合约**（映射=最大持仓仅 39.5%），不是主力合约。想要主力或次主力连续，需要自己按持仓量/成交量规则用逐合约数据重建。商品、国债映射则基本等于最大持仓合约（92–97%）。
- 逐合约数据完整无缺，字段含 pre_settle、settle、oi，足以按"比例/差值后复权"做展期调整，并能用 last_ddate、delist_date 约束换月规则。

## 频率限制（实测）

- `trade_cal`、`fut_holding`、`fut_wsr`、`fut_basic`：**200 次/分钟**。原文：`抱歉，您访问接口(fut_holding)频率超限(200次/分钟)，具体频次详情：https://tushare.pro/document/1?doc_id=108。`（12 线程并发 900 次 trade_cal，700 次被限；顺序约 2 次/秒时 260 次无报错）
- `fut_daily`、`fut_mapping`：10 线程 260 次/分钟内**未触发限制**（上限未测出，至少 >260 次/分钟）。
- 单次行数上限：`fut_daily` 2000；`fut_mapping` 5000；`fut_holding` 4000；`fut_wsr` 1500；`fut_basic` 未见截断。长历史需按日期窗口向前分页（以最小 trade_date-1 为下一页 end_date）。
- 单次调用耗时约 0.7–1.6 秒。拉全部合约逐日数据（数千合约）按 200 次/分钟估算，只需几十分钟量级，可行。

## 坑 / 数据质量提示

1. **TL.CFX（30 年期国债）在上市前就有数据且与 T.CFX 完全相同**：fut_basic 中 TL 最早上市 20230421，但 `TL.CFX` 的 fut_daily/fut_mapping 从 20150320 开始，2023H1 收盘价序列与 `T.CFX` 一致，映射到 `T2612.CFX`。即 TL 连续码被污染/错配，**不要用 TL.CFX 连续码，应用 fut_basic 的 fut_code=TL 真实合约自建**（20230421 起）。
2. `T/TS/TL` 连续码 settle 有 3 行空值；`IFL.CFX`、`RBL.SHF`（L 码，加权/连续）有少量空 settle/oi（IFL 2 行、RBL oi 30 行）。`oi_chg` 在连续码上为空。
3. 连续码映射覆盖到当日 20261118，但 fut_daily 只到 20261117（当日日线盘后才有）。
4. 国债期货 T 自 2015-03-20、TF 自 2013-09-06、TS 自 2018-08-17；IM 自 2022-07-22；SC 自 2018-03-26；SI 自 2022-12-22。更早历史无法获取（国债期货 2013 年才重启，股指期货 2010 年才上市，属于品种本身历史）。
5. 数据史长：CU 自 1995、M 自 2000（DCE 合约元数据 1999 起）、CZCE 品种 2006 起连续码、RB 自 2009、AU 自 2008。老合约（1990 年代）在 `fut_daily` 按日期拉取为 0 或很少，需按单合约核对。
6. INE 在 `fut_holding` 20241115 返回 0（持仓排名可能不覆盖 INE 或需其他参数）；`fut_wsr` 早于约 2008 无数据，中文 symbol 查不到。
7. 无分钟线、无国际期货：若研究需要日内特征或海外商品期货（WTI、COMEX 等）作外部因子，需另找数据源，或用 `fx_daily`/`index_global`/`sge_daily` 作为替代代理。

## 复现要点（不含 token）

`pro = ts.pro_api(os.environ['TUSHARE_TOKEN'])` 后用 `pro.query(接口名, ...)`。拉历史：`start_date='19900101'`，`end_date` 取上一页最小日期前一天；对 `fut_daily` 在 2000 行时继续翻页。逐合约重建流程：`fut_basic(exchange, fut_type='1')` → 逐 `ts_code` 的 `fut_daily` → 自定义换月规则（持仓量/成交量、last_ddate 前若干日）→ 比例或差值后复权。临时脚本在 `/tmp/tsc/`（不在仓库内，不含 token）。
