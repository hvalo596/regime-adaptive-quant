---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# Step 2 真实数据运行日志 2026-11-24

- 机器：4 核 / 15 GB，Python 3.12.3，numpy 2.5.5、pandas 3.1.1、scipy 1.18.1、numba 0.68.1（virtualenv `/agent/venv`）。
- 仓库 `hvalo596/regime-adaptive-quant`，分支 `cursor/step2-real-futures-2dd4`，最终提交 `9420835`（已推送）。PR 创建 403（GitHub 集成无权限），compare 链接见 v3 报告。
- **TUSHARE_TOKEN**：13:12–13:19 UTC 三次检查为 MISSING；13:17 经 parent 对话授权，用户明确允许本次会话在 VM 里通过 `export` 使用 token（本次运行仅在两个 tmux 会话的环境变量里；长度检查 OK）。token 未写入仓库、store、产物或日志（对 `src scripts tests artifacts README` 做过字符串扫描，无命中）。注意：token 也出现在聊天里，用户已接受风险；报告里不重复提醒。
- 时间线（UTC）：
  1. 13:20 起 `fetch_tushare_futures.py --group all --start-date 20040102`：7445 个合约，7514 次调用，约 110 分钟（约 70 次/分钟，受网络而非 150/分钟限速约束）→ 15:05 完成，data/raw 59 MB。
  2. 15:12–15:23 `run_step2.py --min-years 20`（第一次）：商品分析窗口 19.5 年，未达 20 年，且 `H6/H8` 等判定词有一处措辞错（负的区间被写成"含 0"），已修。
  3. 诊断：分析起点被"同时存活 ≥5 个品种"约束，2004 年以前数据只有 CU AL RU A M；补取这 5 个品种自 2000-01-01（删除 49 个被截断的缓存合约与 5 个映射再取，241 次调用，约 4 分钟）。
  4. 补取后分析起点仍是 2007-05（与流动性阈值无关，3000 万元/日同样），原因：Tushare `amount` 在早年（SHFE 约 2008 年以前）为 NaN，流动性闩锁把 CU、AL 推迟到 2008-04。加了 `fill_missing_amount`（vol×close×乘数/1e4，乘数取 `fut_basic.multiplier`，缺则 `per_unit`；共填 67 573 个合约日）。
  5. 探测 `fut_settle`：API 历史自 2021-01-04；按交易日×交易所全期约 7250 次调用不可行，改按合约（`ts_code`）取，官方映射主力合约自 2021 起共 1635 个，约 25 分钟（`--margin-contracts`）。`fut_holding` 全期按日按所约 5 万次调用 ≈ 11 小时，未取。
  6. 16:20–16:34 最终两次运行（并行）：`run_step2.py --out artifacts/step2 --min-years 20` 与 `--out artifacts/step2_liq3e7 --min-amount-wan 3000`，各约 14 分钟；商品窗口 23.99 年 / 24.11 年，均 ≥20 年。
- 代码改动（相对 `005049b`）：`fill_missing_amount`；`fetch_settle_contracts` 与 `--margin-contracts`；`margin_events_from_settle` 改为只看持有合约的保证金率同合约环比上调；`state_means_commodity.csv`；判定词修正（H1/H2/H6/H8）；审计新增"前收与前结算差 >10%"标签；`run_step2.py --min-amount-wan`；覆盖表。42 个测试通过。
- 产物：`artifacts/step2/`、`artifacts/step2_liq3e7/`（各约 180 KB，含 coverage_*、hypotheses、theta_by_panel、per_product_theta、state_means_commodity、state_segments、power_real_dims、pipeline_null_theta、nondefining_signatures、llorente_b2、h10/h11/h12、alt_channels、risk_premium_control、roll_spread、audit_*、trial_ledger、summary.json）。原始数据 `data/raw` 不入库（gitignore）。
- 未做：`fut_holding` 席位签名；H9（第 4 步）；任何 HMM。

## 晚间复验（2026-11-24 20:23–20:38 UTC）

- **凭据**：用户经 coordinator 授权本会话导出 `TUSHARE_TOKEN`（SET，len=56）。对仓库 / store / scratch 日志扫描无长十六进制串落盘。说明：parent 队列里 MCP URL 的 query token **被截断** 时 Tushare 返回 `40101`（token 不对）；用完整凭据后 `trade_cal` 探针 5 行通过。
- **抓取**：`fetch_tushare_futures.py --group all`（默认 ≥20y 窗口自 20040102）→ 7445 合约全部 `skipped_cached`，`api_calls=5`，`fetched_at=2026-11-24T20:23:31Z`，约 15 秒。
- **Step 2**：`run_step2.py --raw-dir data/raw --out artifacts/step2 --min-years 20` → 20:27:37–20:38:11 UTC；`summary.json` 与午后运行一致（商品跨度 23.99y，`meets_min_years=true`，$\Theta_c=-7.69\times10^{-5}$，流水线 $p=0.84$，301 条 trial）。
- **git**：`0ae4360`，工作区无改动，无需新提交。
- **MCP 配置（用户澄清）**：协调器下发的 `mcpServers.tushareMcp` 仅作会话凭据来源；**未**写入 repo/store/日志。批量历史仍走 `http://api.tushare.pro` + `scripts/fetch_tushare_futures.py`（非 MCP 客户端）。注意：若 JSON 里 `url` 的 `token=` 查询参数被 relay **截断**（典型长度约 40 而非 56），HTTP API 报 `40101`；本会话批量跑通使用的是完整 query 参数映射到 `TUSHARE_TOKEN` 后的一次复验（见上节时间戳）。
