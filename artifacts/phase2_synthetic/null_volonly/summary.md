# Phase 2 existence test (step 2): synthetic-fallback

> **SYNTHETIC FALLBACK**: generated market with known truth, run through the real ingest/roll/flag/test path. A plumbing check, not evidence about Chinese futures.


- data: 2012-03-27 .. 2021-07-30, 16 products (RB, HC, I, CU, AL, ZN, AU, AG, SC, TA, M, Y, P, SR, CF, C); 2300 days with D
- flags: 96 limit-locked-proxy asset-days, 96 one-price, 0 stale, 1840 roll days, 0 |ret|>12% (data-error candidates)
- primary tests (Bonferroni family): 6; Kai dims are **DRAFT**, not Kai's formulas

## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)

| series | ann_ret | ann_vol | sharpe | sharpe_lo | sharpe_hi | max_dd |
|---|---|---|---|---|---|---|
| mom_net | 0.0160 | 0.0374 | 0.4279 | -0.1335 | 1.0549 | -0.0814 |
| rev_net | -0.0237 | 0.0370 | -0.6414 | -1.2140 | -0.0681 | -0.2630 |
| mom_gross | 0.0204 | 0.0374 | 0.5447 | 0.0013 | 1.1218 | -0.0716 |
| rev_gross | 0.0010 | 0.0370 | 0.0283 | -0.5407 | 0.5843 | -0.1389 |
| D_net | 26.2310 | 27.4881 | 0.9543 | 0.3313 | 1.6003 | -33.5913 |
| D_gross | 15.6433 | 27.4793 | 0.5693 | -0.0343 | 1.2204 | -56.4825 |

## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)

| proxy | expected_sign | diff | ci_lo | ci_hi | ci_adj_lo | ci_adj_hi | seg_high | seg_low | seg_diff | seg_ci_lo | seg_ci_hi | shift_p_two_sided | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr_short | 1 | 0.1861 | 0.0159 | 0.3699 | -0.0578 | 0.4412 | 23 | 9 | 0.1146 | -0.0694 | 0.2982 | 0.1039 | pass (unadj only) |
| vr_long | 1 | -0.1016 | -0.3076 | 0.0832 | -0.3453 | 0.1598 | 12 | 6 | -0.1513 | -0.3713 | 0.0677 | 0.3613 | fail |
| sys_level | -1 | -0.1902 | -0.3525 | -0.0501 | -0.3866 | 0.0227 | 6 | 13 | -0.1915 | -0.2992 | -0.0765 | 0.1169 | pass (unadj only) |
| sys_share | -1 | -0.1830 | -0.3412 | -0.0472 | -0.3773 | -0.0017 | 7 | 12 | -0.2827 | -0.4928 | -0.1005 | 0.1149 | pass (adj) |
| idio_level | 1 | -0.1690 | -0.3173 | -0.0077 | -0.3598 | 0.0439 | 7 | 11 | -0.2466 | -0.5441 | -0.0140 | 0.1679 | wrong-direction significant |
| idio_conc | 1 | 0.0131 | -0.1718 | 0.2044 | -0.2804 | 0.2455 | 20 | 16 | 0.0314 | -0.1657 | 0.2120 | 0.8926 | fail |

## Robustness: diff by variant

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | 0.0131 | 0.0131 | -0.0139 | -0.1701 | 0.1822 |
| idio_level | -0.1690 | -0.1690 | -0.1149 | -0.1822 | -0.1448 |
| sys_level | -0.1902 | -0.1902 | -0.1233 | -0.1962 | -0.1788 |
| sys_share | -0.1830 | -0.1830 | -0.1041 | -0.1669 | -0.1890 |
| vr_long | -0.1016 | -0.1016 | -0.1048 | -0.1441 | -0.1587 |
| vr_short | 0.1861 | 0.1861 | 0.1267 | 0.0686 | 0.2630 |

verdicts by variant:

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | fail | fail | fail | fail | fail |
| idio_level | wrong-direction significant | wrong-direction significant | fail | fail | fail |
| sys_level | pass (unadj only) | pass (adj) | fail | pass (unadj only) | fail |
| sys_share | pass (unadj only) | pass (unadj only) | fail | fail | fail |
| vr_long | fail | fail | fail | fail | fail |
| vr_short | pass (unadj only) | fail | fail | fail | fail |

## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)

| proxy | observed_diff | null_mean | null_sd | z | p_two_sided | p_expected_side | p_familywise_maxz |
|---|---|---|---|---|---|---|---|
| vr_short | 0.1861 | 0.0335 | 0.0903 | 2.0616 | 0.0396 | 0.0396 | 0.1881 |
| vr_long | -0.1016 | 0.0123 | 0.1001 | -1.0150 | 0.2871 | 0.9010 | 0.8218 |
| sys_level | -0.1902 | -0.0551 | 0.1019 | -1.8659 | 0.0891 | 0.0792 | 0.2970 |
| sys_share | -0.1830 | -0.0475 | 0.1008 | -1.8157 | 0.1188 | 0.1089 | 0.3168 |
| idio_level | -0.1690 | -0.0741 | 0.0988 | -1.7107 | 0.1980 | 0.8119 | 0.3960 |
| idio_conc | 0.0131 | -0.0238 | 0.1069 | 0.1230 | 0.8614 | 0.3861 | 1.0000 |

## Kai-dimension dependence (draft definitions)

logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual 2.00e-15); the three carry two degrees of freedom.

| dim | vif |
|---|---|
| sys_level | 973.94 |
| sys_share | 519.02 |
| idio_level | 94.18 |
| idio_conc | 1.06 |

## Roll quality by product

| product | included | first_date | last_date | n_contracts | n_rolls | rule_used | official_agreement | max_abs_unadj_roll_jump | liquid_from | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| RB | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0131 | 2012-03-26 |  |
| HC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9900 | 0.0143 | 2012-03-26 |  |
| I | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9868 | 0.0170 | 2012-03-26 |  |
| CU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9908 | 0.0128 | 2012-03-26 |  |
| AL | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0148 | 2012-03-26 |  |
| ZN | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0134 | 2012-03-26 |  |
| AU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0152 | 2012-03-26 |  |
| AG | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0151 | 2012-03-26 |  |
| SC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9896 | 0.0125 | 2012-03-26 |  |
| TA | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9884 | 0.0134 | 2012-03-26 |  |
| M | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9920 | 0.0163 | 2012-03-26 |  |
| Y | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9928 | 0.0134 | 2012-03-26 |  |
| P | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0146 | 2012-03-26 |  |
| SR | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0148 | 2012-03-26 |  |
| CF | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0160 | 2012-03-26 |  |
| C | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9940 | 0.0139 | 2012-03-26 |  |
