# Phase 2 existence test (step 2): synthetic-fallback

> **SYNTHETIC FALLBACK**: generated market with known truth, run through the real ingest/roll/flag/test path. A plumbing check, not evidence about Chinese futures.


- data: 2012-03-27 .. 2021-07-30, 16 products (RB, HC, I, CU, AL, ZN, AU, AG, SC, TA, M, Y, P, SR, CF, C); 2300 days with D
- flags: 94 limit-locked-proxy asset-days, 94 one-price, 0 stale, 1840 roll days, 0 |ret|>12% (data-error candidates)
- primary tests (Bonferroni family): 6; Kai dims are **DRAFT**, not Kai's formulas

## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)

| series | ann_ret | ann_vol | sharpe | sharpe_lo | sharpe_hi | max_dd |
|---|---|---|---|---|---|---|
| mom_net | 0.0139 | 0.0334 | 0.4174 | -0.1967 | 1.0807 | -0.0600 |
| rev_net | -0.0199 | 0.0310 | -0.6412 | -1.2256 | -0.0020 | -0.2074 |
| mom_gross | 0.0181 | 0.0334 | 0.5433 | 0.0222 | 1.1637 | -0.0564 |
| rev_gross | 0.0049 | 0.0310 | 0.1569 | -0.4911 | 0.7897 | -0.0653 |
| D_net | 20.2546 | 24.9387 | 0.8122 | 0.2270 | 1.4439 | -35.6165 |
| D_gross | 9.4267 | 24.9440 | 0.3779 | -0.2786 | 1.0133 | -42.1085 |

## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)

| proxy | expected_sign | diff | ci_lo | ci_hi | ci_adj_lo | ci_adj_hi | seg_high | seg_low | seg_diff | seg_ci_lo | seg_ci_hi | shift_p_two_sided | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr_short | 1 | 0.0704 | -0.1155 | 0.2570 | -0.1507 | 0.3136 | 17 | 15 | 0.0081 | -0.2761 | 0.2844 | 0.5097 | fail |
| vr_long | 1 | -0.1505 | -0.2993 | 0.0002 | -0.3577 | 0.0363 | 11 | 14 | -0.0581 | -0.1903 | 0.0900 | 0.0925 | fail |
| sys_level | -1 | -0.0456 | -0.1998 | 0.1256 | -0.2514 | 0.1794 | 19 | 18 | -0.0912 | -0.2926 | 0.0786 | 0.6022 | fail |
| sys_share | -1 | -0.0305 | -0.1909 | 0.1502 | -0.2426 | 0.2261 | 16 | 19 | -0.1240 | -0.2989 | 0.0516 | 0.7196 | fail |
| idio_level | 1 | -0.0746 | -0.2346 | 0.0795 | -0.2895 | 0.1698 | 16 | 17 | -0.1569 | -0.3711 | 0.0343 | 0.4248 | fail |
| idio_conc | 1 | -0.0448 | -0.2493 | 0.1304 | -0.2999 | 0.1924 | 17 | 14 | -0.0995 | -0.5323 | 0.1995 | 0.6077 | fail |

## Robustness: diff by variant

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | -0.0448 | -0.0448 | -0.0177 | -0.0477 | -0.0411 |
| idio_level | -0.0746 | -0.0746 | -0.0899 | -0.1315 | -0.0337 |
| sys_level | -0.0456 | -0.0456 | -0.0114 | -0.1720 | 0.0581 |
| sys_share | -0.0305 | -0.0305 | -0.0025 | -0.1459 | 0.0626 |
| vr_long | -0.1505 | -0.1505 | -0.1504 | -0.2057 | -0.1072 |
| vr_short | 0.0704 | 0.0704 | 0.0571 | 0.1003 | 0.0424 |

verdicts by variant:

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | fail | fail | fail | fail | fail |
| idio_level | fail | fail | fail | fail | fail |
| sys_level | fail | fail | fail | fail | fail |
| sys_share | fail | fail | fail | fail | fail |
| vr_long | fail | wrong-direction significant | wrong-direction significant | wrong-direction significant | fail |
| vr_short | fail | fail | fail | fail | fail |

## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)

| proxy | observed_diff | null_mean | null_sd | z | p_two_sided | p_expected_side | p_familywise_maxz |
|---|---|---|---|---|---|---|---|
| vr_short | 0.0704 | -0.0003 | 0.0973 | 0.7241 | 0.4851 | 0.2475 | 0.9406 |
| vr_long | -0.1505 | 0.0132 | 0.0952 | -1.5809 | 0.1089 | 0.9802 | 0.4653 |
| sys_level | -0.0456 | -0.0163 | 0.0838 | -0.5441 | 0.5743 | 0.3663 | 0.9901 |
| sys_share | -0.0305 | -0.0021 | 0.0928 | -0.3281 | 0.8020 | 0.3861 | 1.0000 |
| idio_level | -0.0746 | -0.0382 | 0.0926 | -0.8059 | 0.4455 | 0.6634 | 0.9208 |
| idio_conc | -0.0448 | -0.0092 | 0.0963 | -0.4655 | 0.5842 | 0.6832 | 1.0000 |

## Kai-dimension dependence (draft definitions)

logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual 1.89e-15); the three carry two degrees of freedom.

| dim | vif |
|---|---|
| sys_level | 1409.74 |
| sys_share | 1498.96 |
| idio_level | 116.45 |
| idio_conc | 1.02 |

## Roll quality by product

| product | included | first_date | last_date | n_contracts | n_rolls | rule_used | official_agreement | max_abs_unadj_roll_jump | liquid_from | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| RB | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0134 | 2012-03-26 |  |
| HC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9900 | 0.0139 | 2012-03-26 |  |
| I | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9868 | 0.0167 | 2012-03-26 |  |
| CU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9908 | 0.0128 | 2012-03-26 |  |
| AL | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0149 | 2012-03-26 |  |
| ZN | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0131 | 2012-03-26 |  |
| AU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0153 | 2012-03-26 |  |
| AG | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0153 | 2012-03-26 |  |
| SC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9896 | 0.0132 | 2012-03-26 |  |
| TA | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9884 | 0.0131 | 2012-03-26 |  |
| M | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9920 | 0.0166 | 2012-03-26 |  |
| Y | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9928 | 0.0134 | 2012-03-26 |  |
| P | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0148 | 2012-03-26 |  |
| SR | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0149 | 2012-03-26 |  |
| CF | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0165 | 2012-03-26 |  |
| C | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9940 | 0.0140 | 2012-03-26 |  |
