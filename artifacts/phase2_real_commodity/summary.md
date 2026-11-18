# Phase 2 existence test (step 2): tushare


- data: 2015-04-08 .. 2026-11-17, 40 products (RB, HC, SS, I, J, JM, CU, AL, ZN, PB, NI, SN, AU, AG, SC, FU, BU, TA, MA, PP, L, V, EG, EB, PG, SA, FG, RU, M, Y, P, A, C, CS, JD, SR, CF, RM, OI, AP); 2684 days with D
- flags: 54 limit-locked-proxy asset-days, 72 one-price, 1 stale, 2185 roll days, 28 |ret|>12% (data-error candidates)
- primary tests (Bonferroni family): 6; Kai dims are **DRAFT**, not Kai's formulas

## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)

| series | ann_ret | ann_vol | sharpe | sharpe_lo | sharpe_hi | max_dd |
|---|---|---|---|---|---|---|
| mom_net | 0.0128 | 0.0330 | 0.3881 | -0.1682 | 0.9597 | -0.0713 |
| rev_net | -0.0308 | 0.0315 | -0.9783 | -1.4028 | -0.5310 | -0.3432 |
| mom_gross | 0.0166 | 0.0330 | 0.5013 | -0.0854 | 1.0775 | -0.0611 |
| rev_gross | -0.0064 | 0.0315 | -0.2035 | -0.6983 | 0.3211 | -0.1157 |
| D_net | 25.6267 | 26.4016 | 0.9707 | 0.4218 | 1.4982 | -38.2397 |
| D_gross | 13.7573 | 26.3940 | 0.5212 | -0.0522 | 1.0761 | -57.0791 |

## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)

| proxy | expected_sign | diff | ci_lo | ci_hi | ci_adj_lo | ci_adj_hi | seg_high | seg_low | seg_diff | seg_ci_lo | seg_ci_hi | shift_p_two_sided | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr_short | 1 | -0.1181 | -0.2789 | 0.0457 | -0.3364 | 0.1073 | 30 | 19 | -0.0411 | -0.2164 | 0.1678 | 0.1559 | fail |
| vr_long | 1 | -0.0528 | -0.2149 | 0.0959 | -0.2625 | 0.1673 | 15 | 23 | -0.0974 | -0.2580 | 0.0579 | 0.4983 | fail |
| sys_level | -1 | -0.0398 | -0.1904 | 0.1169 | -0.2321 | 0.1879 | 9 | 10 | -0.2300 | -0.6145 | 0.0438 | 0.7206 | fail |
| sys_share | -1 | -0.1499 | -0.3025 | 0.0153 | -0.3314 | 0.0563 | 11 | 12 | -0.2083 | -0.4168 | -0.0187 | 0.0695 | fail |
| idio_level | 1 | 0.0127 | -0.1782 | 0.1717 | -0.2183 | 0.2350 | 7 | 9 | -0.1286 | -0.3505 | 0.0542 | 0.9010 | fail |
| idio_conc | 1 | 0.0611 | -0.1451 | 0.2477 | -0.2298 | 0.2978 | 18 | 9 | 0.2346 | -0.0042 | 0.5136 | 0.4993 | fail |

## Robustness: diff by variant

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | 0.0611 | 0.0611 | 0.0506 | -0.1711 | 0.2951 |
| idio_level | 0.0127 | 0.0127 | 0.0252 | 0.0559 | -0.0220 |
| sys_level | -0.0398 | -0.0398 | -0.0211 | -0.0689 | -0.0196 |
| sys_share | -0.1499 | -0.1499 | -0.1563 | -0.1725 | -0.1247 |
| vr_long | -0.0528 | -0.0528 | -0.0384 | -0.0276 | -0.0735 |
| vr_short | -0.1181 | -0.1181 | -0.1299 | -0.0859 | -0.1518 |

verdicts by variant:

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | fail | fail | fail | fail | fail |
| idio_level | fail | fail | fail | fail | fail |
| sys_level | fail | fail | fail | fail | fail |
| sys_share | fail | pass (unadj only) | pass (unadj only) | fail | fail |
| vr_long | fail | fail | fail | fail | fail |
| vr_short | fail | fail | fail | fail | fail |

## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)

| proxy | observed_diff | null_mean | null_sd | z | p_two_sided | p_expected_side | p_familywise_maxz |
|---|---|---|---|---|---|---|---|
| vr_short | -0.1181 | -0.0140 | 0.0915 | -1.2907 | 0.1881 | 0.8812 | 0.7228 |
| vr_long | -0.0528 | -0.0219 | 0.1012 | -0.5217 | 0.6139 | 0.5743 | 0.9901 |
| sys_level | -0.0398 | -0.0652 | 0.0938 | -0.4247 | 0.7129 | 0.6139 | 1.0000 |
| sys_share | -0.1499 | -0.0560 | 0.1004 | -1.4926 | 0.2178 | 0.1881 | 0.5941 |
| idio_level | 0.0127 | -0.0517 | 0.0845 | 0.1504 | 0.8812 | 0.1782 | 1.0000 |
| idio_conc | 0.0611 | -0.0024 | 0.0981 | 0.6224 | 0.5347 | 0.2475 | 0.9901 |

## Step 3 (rule baseline): recognition delay vs segment duration (reference = centered-smoothed proxy, ex-post)

| proxy | bin | n_segments | mean_duration | mean_delay | share_missed | duration_over_delay | causal_flips_per_year |
|---|---|---|---|---|---|---|---|
| vr_short | high | 22 | 39.27 | 0.23 | 0.00 | 39.27 | 34.79 |
| vr_short | low | 17 | 42.88 | 1.65 | 0.00 | 26.04 | 34.79 |
| vr_long | high | 16 | 49.44 | 0.75 | 0.00 | 49.44 | 11.44 |
| vr_long | low | 15 | 54.20 | 0.00 | 0.00 | 54.20 | 11.44 |
| sys_level | high | 8 | 105.12 | 0.25 | 0.00 | 105.12 | 8.35 |
| sys_level | low | 7 | 129.00 | 1.14 | 0.00 | 112.88 | 8.35 |
| sys_share | high | 9 | 82.78 | 4.50 | 0.11 | 18.40 | 15.49 |
| sys_share | low | 14 | 65.36 | 0.43 | 0.00 | 65.36 | 15.49 |
| idio_level | high | 5 | 174.20 | 0.00 | 0.00 | 174.20 | 5.23 |
| idio_level | low | 8 | 91.75 | 7.12 | 0.00 | 12.88 | 5.23 |
| idio_conc | high | 12 | 76.08 | 0.00 | 0.00 | 76.08 | 13.68 |
| idio_conc | low | 10 | 71.20 | 9.22 | 0.10 | 7.72 | 13.68 |

## Kai-dimension dependence (draft definitions)

logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual 2.00e-15); the three carry two degrees of freedom.

| dim | vif |
|---|---|
| sys_level | 410.02 |
| sys_share | 186.62 |
| idio_level | 196.93 |
| idio_conc | 1.15 |

## Roll quality by product

| product | included | first_date | last_date | n_contracts | n_rolls | rule_used | official_agreement | max_abs_unadj_roll_jump | liquid_from | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| RB | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9730 | 0.0975 | 2015-04-07 |  |
| HC | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9802 | 0.0735 | 2015-04-07 |  |
| SS | True | 2019-09-25 | 2026-11-17 | 94 | 75 | official | 0.8289 | 0.0544 | 2019-12-25 |  |
| I | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9788 | 0.1485 | 2015-04-07 |  |
| J | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9782 | 0.1677 | 2015-04-07 |  |
| JM | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9799 | 0.1651 | 2015-04-07 |  |
| CU | True | 2015-01-05 | 2026-11-17 | 155 | 141 | official | 0.8981 | 0.0147 | 2015-04-07 |  |
| AL | True | 2015-01-05 | 2026-11-17 | 155 | 141 | official | 0.8759 | 0.0226 | 2015-04-07 |  |
| ZN | True | 2015-01-05 | 2026-11-17 | 155 | 141 | official | 0.8800 | 0.0272 | 2015-04-07 |  |
| PB | True | 2015-01-05 | 2026-11-17 | 155 | 142 | official | 0.8953 | 0.0265 | 2015-04-07 |  |
| NI | True | 2015-03-27 | 2026-11-17 | 149 | 95 | official | 0.8951 | 0.0399 | 2015-06-24 |  |
| SN | True | 2015-03-27 | 2026-11-17 | 149 | 93 | official | 0.9014 | 0.0314 | 2015-06-24 |  |
| AU | True | 2015-01-05 | 2026-11-17 | 151 | 42 | official | 0.8866 | 0.0163 | 2015-04-07 |  |
| AG | True | 2015-01-05 | 2026-11-17 | 155 | 39 | official | 0.9164 | 0.0325 | 2015-04-07 |  |
| SC | True | 2018-03-26 | 2026-11-17 | 119 | 97 | official | 0.8241 | 0.0842 | 2018-06-25 |  |
| FU | True | 2015-01-05 | 2026-11-17 | 150 | 39 | oi | 0.6903 | 0.2425 | 2018-08-24 |  |
| BU | True | 2015-01-05 | 2026-11-17 | 159 | 54 | official | 0.9095 | 0.1776 | 2015-04-07 |  |
| TA | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9726 | 0.0533 | 2015-04-07 |  |
| MA | True | 2015-01-05 | 2026-11-17 | 150 | 37 | official | 0.9650 | 0.1009 | 2015-04-07 |  |
| PP | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9684 | 0.1026 | 2015-04-07 |  |
| L | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9719 | 0.0831 | 2015-04-07 |  |
| V | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9726 | 0.0626 | 2015-04-07 |  |
| EG | True | 2018-12-10 | 2026-11-17 | 101 | 25 | official | 0.9527 | 0.0822 | 2019-03-13 |  |
| EB | True | 2019-09-26 | 2026-11-17 | 91 | 72 | official | 0.8456 | 0.0626 | 2019-12-26 |  |
| PG | True | 2020-03-30 | 2026-11-17 | 84 | 69 | oi | 0.7756 | 0.1236 | 2020-06-30 |  |
| SA | True | 2019-12-06 | 2026-11-17 | 91 | 20 | official | 0.9745 | 0.2009 | 2020-03-10 |  |
| FG | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9736 | 0.1426 | 2015-04-07 |  |
| RU | True | 2015-01-05 | 2026-11-17 | 130 | 35 | official | 0.9723 | 0.2381 | 2015-04-07 |  |
| M | True | 2015-01-05 | 2026-11-17 | 103 | 35 | official | 0.9515 | 0.1395 | 2015-04-07 |  |
| Y | True | 2015-01-05 | 2026-11-17 | 103 | 35 | official | 0.9542 | 0.0713 | 2015-04-07 |  |
| P | True | 2015-01-05 | 2026-11-17 | 155 | 36 | official | 0.9681 | 0.1172 | 2015-04-07 |  |
| A | True | 2015-01-05 | 2026-11-17 | 78 | 46 | official | 0.9521 | 0.1070 | 2015-04-07 |  |
| C | True | 2015-01-05 | 2026-11-17 | 78 | 45 | official | 0.9480 | 0.1360 | 2015-04-07 |  |
| CS | True | 2015-01-05 | 2026-11-17 | 77 | 51 | official | 0.9438 | 0.1314 | 2015-04-07 |  |
| JD | True | 2015-01-05 | 2026-11-17 | 150 | 59 | official | 0.9189 | 0.3633 | 2015-04-07 |  |
| SR | True | 2015-01-05 | 2026-11-17 | 78 | 37 | official | 0.9577 | 0.0656 | 2015-04-07 |  |
| CF | True | 2015-01-05 | 2026-11-17 | 78 | 35 | official | 0.9730 | 0.0650 | 2015-04-07 |  |
| RM | True | 2015-01-05 | 2026-11-17 | 91 | 37 | official | 0.9417 | 0.1766 | 2015-04-07 |  |
| OI | True | 2015-01-05 | 2026-11-17 | 78 | 36 | official | 0.9438 | 0.0671 | 2015-04-07 |  |
| AP | True | 2017-12-22 | 2026-11-17 | 66 | 26 | official | 0.9722 | 0.3542 | 2018-03-26 |  |
