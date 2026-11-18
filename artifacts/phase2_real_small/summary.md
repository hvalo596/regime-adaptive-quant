# Phase 2 existence test (step 2): tushare


- data: 2015-04-08 .. 2026-11-17, 8 products (RB, CU, AU, M, SR, TA, I, AL); 2684 days with D
- flags: 4 limit-locked-proxy asset-days, 4 one-price, 0 stale, 501 roll days, 1 |ret|>12% (data-error candidates)
- primary tests (Bonferroni family): 6; Kai dims are **DRAFT**, not Kai's formulas

## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)

| series | ann_ret | ann_vol | sharpe | sharpe_lo | sharpe_hi | max_dd |
|---|---|---|---|---|---|---|
| mom_net | 0.0123 | 0.0418 | 0.2940 | -0.2430 | 0.8323 | -0.0868 |
| rev_net | -0.0384 | 0.0412 | -0.9331 | -1.3951 | -0.4557 | -0.4261 |
| mom_gross | 0.0163 | 0.0418 | 0.3888 | -0.1910 | 0.9146 | -0.0747 |
| rev_gross | -0.0134 | 0.0412 | -0.3254 | -0.8305 | 0.2105 | -0.1654 |
| D_net | 22.9866 | 26.4316 | 0.8697 | 0.2992 | 1.3594 | -36.7911 |
| D_gross | 14.0899 | 26.4286 | 0.5331 | -0.0673 | 1.1249 | -48.6460 |

## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)

| proxy | expected_sign | diff | ci_lo | ci_hi | ci_adj_lo | ci_adj_hi | seg_high | seg_low | seg_diff | seg_ci_lo | seg_ci_hi | shift_p_two_sided | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr_short | 1 | 0.0359 | -0.1116 | 0.1903 | -0.1630 | 0.2408 | 32 | 23 | 0.0085 | -0.1333 | 0.1615 | 0.6732 | fail |
| vr_long | 1 | 0.0441 | -0.1288 | 0.2062 | -0.1787 | 0.2882 | 11 | 23 | 0.1099 | -0.1063 | 0.3224 | 0.6222 | fail |
| sys_level | -1 | -0.2058 | -0.3472 | -0.0769 | -0.3973 | -0.0218 | 10 | 13 | -0.3182 | -0.4957 | -0.1454 | 0.0005 | pass (adj) |
| sys_share | -1 | -0.1300 | -0.2630 | 0.0038 | -0.3069 | 0.0651 | 9 | 15 | -0.1156 | -0.3749 | 0.1243 | 0.1109 | fail |
| idio_level | 1 | -0.2487 | -0.4209 | -0.0897 | -0.4737 | -0.0373 | 8 | 14 | -0.4048 | -0.6567 | -0.1992 | 0.0005 | wrong-direction significant |
| idio_conc | 1 | -0.1064 | -0.2797 | 0.0638 | -0.3325 | 0.1146 | 19 | 12 | -0.1916 | -0.4780 | 0.0604 | 0.1969 | fail |

## Robustness: diff by variant

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | -0.1064 | -0.1064 | -0.1074 | -0.1893 | -0.0284 |
| idio_level | -0.2487 | -0.2487 | -0.2466 | -0.1793 | -0.3063 |
| sys_level | -0.2058 | -0.2058 | -0.2028 | -0.2412 | -0.1892 |
| sys_share | -0.1300 | -0.1300 | -0.1293 | -0.2045 | -0.0590 |
| vr_long | 0.0441 | 0.0441 | 0.0474 | -0.0572 | 0.1210 |
| vr_short | 0.0359 | 0.0359 | 0.0426 | 0.0826 | 0.0011 |

verdicts by variant:

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | fail | fail | fail | fail | fail |
| idio_level | wrong-direction significant | wrong-direction significant | wrong-direction significant | fail | wrong-direction significant |
| sys_level | pass (adj) | pass (adj) | pass (adj) | fail | fail |
| sys_share | fail | pass (unadj only) | fail | fail | fail |
| vr_long | fail | fail | fail | fail | fail |
| vr_short | fail | fail | fail | fail | fail |

## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)

| proxy | observed_diff | null_mean | null_sd | z | p_two_sided | p_expected_side | p_familywise_maxz |
|---|---|---|---|---|---|---|---|
| vr_short | 0.0359 | 0.0014 | 0.1035 | 0.3468 | 0.7426 | 0.3663 | 1.0000 |
| vr_long | 0.0441 | -0.0198 | 0.0990 | 0.4461 | 0.6931 | 0.2772 | 1.0000 |
| sys_level | -0.2058 | -0.0825 | 0.0996 | -2.0657 | 0.1188 | 0.1188 | 0.3168 |
| sys_share | -0.1300 | -0.0460 | 0.0995 | -1.3072 | 0.2772 | 0.2277 | 0.8317 |
| idio_level | -0.2487 | -0.0894 | 0.0895 | -2.7787 | 0.0495 | 0.9604 | 0.0792 |
| idio_conc | -0.1064 | -0.0122 | 0.0948 | -1.1221 | 0.2673 | 0.8218 | 0.8713 |

## Step 3 (rule baseline): recognition delay vs segment duration (reference = centered-smoothed proxy, ex-post)

| proxy | bin | n_segments | mean_duration | mean_delay | share_missed | duration_over_delay | causal_flips_per_year |
|---|---|---|---|---|---|---|---|
| vr_short | high | 19 | 46.58 | 0.89 | 0.00 | 46.58 | 32.58 |
| vr_short | low | 19 | 40.37 | 0.47 | 0.00 | 40.37 | 32.58 |
| vr_long | high | 15 | 49.47 | 3.36 | 0.07 | 14.73 | 13.60 |
| vr_long | low | 12 | 69.67 | 0.00 | 0.00 | 69.67 | 13.60 |
| sys_level | high | 7 | 118.14 | 1.57 | 0.00 | 75.18 | 7.24 |
| sys_level | low | 10 | 90.90 | 0.20 | 0.00 | 90.90 | 7.24 |
| sys_share | high | 8 | 96.38 | 7.29 | 0.12 | 13.23 | 12.17 |
| sys_share | low | 11 | 83.00 | 0.09 | 0.00 | 83.00 | 12.17 |
| idio_level | high | 8 | 107.12 | 0.00 | 0.00 | 107.12 | 8.95 |
| idio_level | low | 9 | 94.78 | 0.00 | 0.00 | 94.78 | 8.95 |
| idio_conc | high | 12 | 76.25 | 0.00 | 0.00 | 76.25 | 14.88 |
| idio_conc | low | 10 | 75.20 | 2.89 | 0.10 | 26.03 | 14.88 |

## Kai-dimension dependence (draft definitions)

logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual 2.00e-15); the three carry two degrees of freedom.

| dim | vif |
|---|---|
| sys_level | 781.10 |
| sys_share | 388.30 |
| idio_level | 320.71 |
| idio_conc | 2.39 |

## Roll quality by product

| product | included | first_date | last_date | n_contracts | n_rolls | rule_used | official_agreement | max_abs_unadj_roll_jump | liquid_from | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| RB | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9730 | 0.0975 | 2015-04-07 |  |
| CU | True | 2015-01-05 | 2026-11-17 | 155 | 141 | official | 0.8981 | 0.0147 | 2015-04-07 |  |
| AU | True | 2015-01-05 | 2026-11-17 | 151 | 42 | official | 0.8866 | 0.0163 | 2015-04-07 |  |
| M | True | 2015-01-05 | 2026-11-17 | 103 | 35 | official | 0.9515 | 0.1395 | 2015-04-07 |  |
| SR | True | 2015-01-05 | 2026-11-17 | 78 | 37 | official | 0.9577 | 0.0656 | 2015-04-07 |  |
| TA | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9726 | 0.0533 | 2015-04-07 |  |
| I | True | 2015-01-05 | 2026-11-17 | 155 | 35 | official | 0.9788 | 0.1485 | 2015-04-07 |  |
| AL | True | 2015-01-05 | 2026-11-17 | 155 | 141 | official | 0.8759 | 0.0226 | 2015-04-07 |  |
