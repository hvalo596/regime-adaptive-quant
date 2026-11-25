---
cursor:
  subagentId: "bc-34cab32f-c26e-5020-b3f5-60ba0a612dd4"
---

# 第 3、4 步运行日志 2026-11-24

- 机器：4 核 / 15 GB，Python 3.12.3，numpy 2.5.5、pandas 3.1.1、scipy 1.18.1、numba 0.68.1。仓库 `hvalo596/regime-adaptive-quant`，分支 `cursor/step2-real-futures-2dd4`，最终提交 `0ae4360`（已推送；PR 创建 403，compare 链接 https://github.com/hvalo596/regime-adaptive-quant/pull/new/cursor/step2-real-futures-2dd4）。
- 数据：第 2 步缓存 `data/raw`（不入库）；校准 `artifacts/step2/calibration_commodity.json`。TUSHARE_TOKEN 在本阶段不需要，也未设置（`env` 中无）。
- 代码演进（均为发现问题后的诊断驱动）：
  1. 首版每日一个观测、方差 κ/N_eff：拟合的平均持续期 7–15 日、AUC 随种子在 0.36–0.87 之间摇摆 → 改为块均值观测（k=L+H，精确方差）。
  2. 真实数据上未归一化的 z 在波动爆发里产生由极端日构成的离群状态 → z 自归一化。
  3. 优化器在真实数据上出现 LR<0（嵌套模型）→ 8 个起点并从 β=0 的解出发。
  4. 状态按均值排序时，退化拟合把"基线"标成"在场"（滤波 s 平均 −0.5～−0.74）→ 记录退化占比，加入事后的"退化守卫"变体（不进主检验族）。
  5. 首次完整合成运行因线程过订阅（load 11）极慢，且 2500 日合成世界在 min_train=750、观测门槛 93 时慢人链没有任何滤波输出（eval_days=0）→ OMP/OPENBLAS/NUMBA 线程设为 1；观测门槛改为 25；重跑合成部分（真实面板结果不受影响：已核对两版真实输出一致）。
- 实际命令：
  `python scripts/run_step34.py --raw-dir data/raw --out3 artifacts/step3 --out4 artifacts/step4`（真实面板部分约 25 分钟，含 4 分钟载入）；
  合成部分 `python scripts/run_step34.py --synth-only --skip-pipeline-null --mask-pkl <pickle> ...`（无状态流水线零分布 120 个、真实缺失模式，约 36 分钟；无状态世界 5×60、植入 6×60、切换 6×30，约 52 分钟）；
  `python scripts/step4_extras.py ...`、`python scripts/summarize_step34.py ...`、`python scripts/check_regression_vs_step1.py <worktree>`。
- 回归（共用代码改动后）：`check_regression_vs_step1.py` 在两个世界上比较旧（第 1 步分支）与新流水线的 tau_M、tau_R、s、D、C、毛收益、V：全部逐位相同；`run_step1.py --scale 0.15` + summarize：A1、A3–A6 通过，A2（M-A 的 P(τ≥1.28) 3.9%，只有 6 次空模拟）与 A7（M-B 0.1 档比值 0.53，23 次切换）因小样本失败，A1 数字与原运行逐位相同；未重跑 45 分钟的全量。
- 测试：`pytest -q`：53 个通过（新增 11 个：滤波对暴力枚举、NaN 观测日、HMM 找回、增量与滤波无前视、块方差、BOCPD、熵与带宽、恒等式与 EWA/TP60/学习倾斜无前视、择时拆分、配对夏普差的拒绝率）。
- 产物：`artifacts/step3/`（1.4 MB）、`artifacts/step4/`（0.2 MB）。
- 已知未做：HMM 的 ν 与先验的敏感性网格；行业/股指面板的流水线零分布；国债面板（样本不足）；第 2 步的保证金事件之外的外生协变量；M-A/R-B-gap 参数的第 3、4 步重复。
