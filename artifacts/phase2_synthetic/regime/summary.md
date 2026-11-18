# Phase 2 existence test (step 2): synthetic-fallback

> **SYNTHETIC FALLBACK**: generated market with known truth, run through the real ingest/roll/flag/test path. A plumbing check, not evidence about Chinese futures.


- data: 2012-03-27 .. 2021-07-30, 16 products (RB, HC, I, CU, AL, ZN, AU, AG, SC, TA, M, Y, P, SR, CF, C); 2300 days with D
- flags: 96 limit-locked-proxy asset-days, 96 one-price, 0 stale, 1840 roll days, 0 |ret|>12% (data-error candidates)
- primary tests (Bonferroni family): 6; Kai dims are **DRAFT**, not Kai's formulas

## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)

| series | ann_ret | ann_vol | sharpe | sharpe_lo | sharpe_hi | max_dd |
|---|---|---|---|---|---|---|
| mom_net | 0.0385 | 0.0369 | 1.0443 | 0.3750 | 1.8632 | -0.0566 |
| rev_net | -0.0502 | 0.0364 | -1.3782 | -2.1029 | -0.6686 | -0.5396 |
| mom_gross | 0.0427 | 0.0369 | 1.1598 | 0.4969 | 1.8794 | -0.0545 |
| rev_gross | -0.0260 | 0.0364 | -0.7143 | -1.3491 | -0.0999 | -0.3757 |
| D_net | 52.4212 | 27.6194 | 1.8980 | 1.1660 | 2.5874 | -26.2484 |
| D_gross | 41.9124 | 27.6033 | 1.5184 | 0.9099 | 2.2753 | -31.3715 |

## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)

| proxy | expected_sign | diff | ci_lo | ci_hi | ci_adj_lo | ci_adj_hi | seg_high | seg_low | seg_diff | seg_ci_lo | seg_ci_hi | shift_p_two_sided | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr_short | 1 | 0.3751 | 0.2162 | 0.5262 | 0.1657 | 0.5714 | 17 | 7 | 0.2252 | 0.0024 | 0.4161 | 0.0110 | pass (adj) |
| vr_long | 1 | 0.2639 | 0.0870 | 0.4316 | 0.0510 | 0.4823 | 7 | 4 | 0.1048 | -0.1064 | 0.2609 | 0.1129 | fail |
| sys_level | -1 | -0.3834 | -0.5360 | -0.2206 | -0.5851 | -0.1756 | 6 | 14 | -0.3853 | -0.5426 | -0.2096 | 0.0090 | pass (adj) |
| sys_share | -1 | -0.3928 | -0.5384 | -0.2420 | -0.5915 | -0.1954 | 6 | 11 | -0.4032 | -0.5919 | -0.2143 | 0.0085 | pass (adj) |
| idio_level | 1 | -0.2538 | -0.4339 | -0.0783 | -0.4703 | -0.0390 | 7 | 10 | -0.3916 | -0.6949 | -0.1370 | 0.1109 | wrong-direction significant |
| idio_conc | 1 | -0.1135 | -0.2965 | 0.0734 | -0.3516 | 0.1228 | 19 | 16 | -0.0756 | -0.3314 | 0.1639 | 0.2639 | fail |

## Robustness: diff by variant

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | -0.1135 | -0.1135 | -0.1321 | -0.2852 | 0.0676 |
| idio_level | -0.2538 | -0.2538 | -0.1945 | -0.2843 | -0.2265 |
| sys_level | -0.3834 | -0.3834 | -0.3160 | -0.3899 | -0.3625 |
| sys_share | -0.3928 | -0.3928 | -0.3183 | -0.3802 | -0.3841 |
| vr_long | 0.2639 | 0.2639 | 0.1987 | 0.1177 | 0.3512 |
| vr_short | 0.3751 | 0.3751 | 0.3273 | 0.2376 | 0.4187 |

verdicts by variant:

| proxy | block_10 | block_60 | excl_limit_adjacent | first_half | second_half |
|---|---|---|---|---|---|
| idio_conc | fail | fail | fail | wrong-direction significant | fail |
| idio_level | wrong-direction significant | wrong-direction significant | wrong-direction significant | wrong-direction significant | fail |
| sys_level | pass (adj) | pass (adj) | pass (adj) | pass (adj) | fail |
| sys_share | pass (adj) | pass (adj) | pass (adj) | fail | fail |
| vr_long | fail | fail | fail | fail | fail |
| vr_short | pass (adj) | pass (adj) | pass (adj) | pass (unadj only) | fail |

## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)

| proxy | observed_diff | null_mean | null_sd | z | p_two_sided | p_expected_side | p_familywise_maxz |
|---|---|---|---|---|---|---|---|
| vr_short | 0.3751 | 0.1746 | 0.1217 | 3.0823 | 0.0495 | 0.0495 | 0.0990 |
| vr_long | 0.2639 | 0.1048 | 0.1449 | 1.8209 | 0.1386 | 0.1287 | 0.5347 |
| sys_level | -0.3834 | -0.1806 | 0.1333 | -2.8760 | 0.0693 | 0.0693 | 0.1584 |
| sys_share | -0.3928 | -0.1828 | 0.1345 | -2.9196 | 0.0495 | 0.0495 | 0.1485 |
| idio_level | -0.2538 | -0.1362 | 0.1228 | -2.0671 | 0.1683 | 0.8416 | 0.4653 |
| idio_conc | -0.1135 | -0.0385 | 0.1050 | -1.0819 | 0.2871 | 0.7723 | 0.8614 |

## Kai-dimension dependence (draft definitions)

logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual 2.00e-15); the three carry two degrees of freedom.

| dim | vif |
|---|---|
| sys_level | 983.87 |
| sys_share | 534.50 |
| idio_level | 95.11 |
| idio_conc | 1.03 |

## Roll quality by product

| product | included | first_date | last_date | n_contracts | n_rolls | rule_used | official_agreement | max_abs_unadj_roll_jump | liquid_from | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| RB | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0131 | 2012-03-26 |  |
| HC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9900 | 0.0144 | 2012-03-26 |  |
| I | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9868 | 0.0170 | 2012-03-26 |  |
| CU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9908 | 0.0128 | 2012-03-26 |  |
| AL | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0148 | 2012-03-26 |  |
| ZN | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0135 | 2012-03-26 |  |
| AU | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0152 | 2012-03-26 |  |
| AG | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9888 | 0.0150 | 2012-03-26 |  |
| SC | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9896 | 0.0125 | 2012-03-26 |  |
| TA | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9884 | 0.0134 | 2012-03-26 |  |
| M | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9920 | 0.0164 | 2012-03-26 |  |
| Y | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9928 | 0.0134 | 2012-03-26 |  |
| P | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0147 | 2012-03-26 |  |
| SR | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9892 | 0.0148 | 2012-03-26 |  |
| CF | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9904 | 0.0160 | 2012-03-26 |  |
| C | True | 2012-01-02 | 2021-07-30 | 127 | 115 | official | 0.9940 | 0.0139 | 2012-03-26 |  |
