---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 顶刊式报告标准与审稿人自检（Steps 2–4）

对照：`docs/step1-paper-report.md` 体例；用户 2026-11-24 过夜交付要求。

## 报告体例对照

| 环节 | Step 2 v3 | Step 3 | Step 4 |
|---|---|---|---|
| 研究问题 | §1 经济读法 + 引言式摘要（见报告「摘要」） | §1 + 摘要 | §1 + 摘要 |
| 识别策略 | §3 方法 | §3 方法 | §2 设计 |
| 数据（20y） | §2 + 合规块 | §2 表 | §3 |
| 主要结果 | §4 表（含片段数） | §5 | §5 |
| 经济含义 | §1、§4.2–4.3 | §6 | §6 |
| 稳健性 | §4.5–4.6、敏感性 liq3e7 | §4 合成 | §4 合成、成本网格 |
| 局限 | §5 | §7 | §7 |
| 复现 | §6（SHA、命令、路径） | §8 | §8 |

**推断要素**：点估计 + 块自助 CI（§4 各表）；片段数在 `state_segments` / occupancy 行与 §4.2；`trial_ledger.csv`（301）；`p_pipeline`（0.84）在 v3 §1。

**诚实层级**（regime-identification-why + step1-paper §7.5）：本链结论定位于 **功效不足 / 边界（C2–C4 断裂）**，未声称机制一致或准因果。

## 审稿人自检（p-hacking / peeking / same-barrel / unmotivated HMM）

| 风险 | 判定 | 披露位置 |
|---|---|---|
| **p-hacking** | 低–中（已控） | 主检验 Θ_c 事前 1 个；301 条入 ledger，Holm/二项报告；逐品种 1/40 不夸大。副组合/板块**展示不判定**。仍拒绝：若只看最小 p 会夸大 → v3 §5、§4.1 读法 |
| **Peeking / 偷看** | 低 | 状态变量只用 ≤t 信息；`tests/test_step34.py` 因果篡改；第 2 步无 HMM |
| **Same-barrelling** | 已披露 | M/R 与 D 同尺度 LEG；块长 40 与 L+H 块均值（step3）显式；重叠 MA 用块均值 z 消解 |
| **Unmotivated HMM** | 已辩护+披露 | 第 3 步才上 HMM；事前 §4.6（两链、Student-t、sojourn 下限、≤12 参 spirit）；真实 BIC 偏好单状态、90%+ 退化 → **不能**把 HMM 当存在性证据。step3 §5.1、§7 S3-* |
| **HMM 交易决策** | 低 | 仅滤波概率；无 Viterbi 仓位 |
| **配置倾斜当择时** | 已修正 | Θ vs Θ_c；step4 择时/倾斜拆分 |

**总评**：审稿人可能因**功效不足与负结果**要求更强外生识别，但不应以 p-hacking 或未动机 HMM **单独**拒稿——前提是读本报告的边界段与 H13（第 1 步假阳性率）。

## 交付物路径

- 报告：`docs/step2-result-report-v3.md`、`step3-result-report.md`、`step4-result-report.md`（含新增摘要与表前「谁付钱」句）
- 协调员：`internal/quality-checklist-2026-11-24.md` §顶刊报告标准
- 证据：`internal/step1-4-quality-evidence-2026-11-24.md`