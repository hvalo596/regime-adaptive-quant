# Phase 1 synthetic run (auto-generated)

seed=1, n_days=6000, multi-seed n=20. All parameters are DRAFT (see README, TO_LOCK).
Synthetic data only: nothing here says anything about real markets.

## Benchmarks, 'regime' scenario (net of draft costs; Sharpe with 95% block-bootstrap CI)
```
            strategy  ann_ret  ann_vol  sharpe  sharpe_lo  sharpe_hi  max_dd
             mom_leg    0.030    0.039   0.775      0.390      1.174  -0.081
             rev_leg   -0.044    0.041  -1.067     -1.488     -0.666  -1.084
      ew_assets_long   -0.029    0.132  -0.220     -0.525      0.139  -0.939
            ew_blend   -0.007    0.027  -0.250     -0.620      0.102  -0.187
       inv_vol_blend   -0.006    0.027  -0.227     -0.589      0.127  -0.172
    vol_target_blend   -0.020    0.079  -0.250     -0.588      0.109  -0.539
   oracle_true_state    0.026    0.037   0.703      0.333      1.074  -0.128
mom_turnover_per_day    0.019      NaN     NaN        NaN        NaN     NaN
rev_turnover_per_day    0.142      NaN     NaN        NaN        NaN     NaN
```

## D = mom - rev (risk-standardised) by TRUE state (oracle conditioning, possible only on synthetic)
```
true_state  n_days  mean_D  ann_sharpe_D     scenario
      slow    1714   0.330         3.261       regime
    rushed    2030  -0.021        -0.182       regime
      calm    2176   0.169         1.850       regime
      none    5920   0.062         0.642   null_const
  vol_slow    1714   0.074         0.769 null_volonly
vol_rushed    2030   0.017         0.145 null_volonly
  vol_calm    2176   0.133         1.479 null_volonly
```

## Existence test on observable proxies, single seed (draft rule: CI lower bound > 0 and >=5 segments per extreme bin)
```
   proxy   diff  ci_lo  ci_hi  seg_high  seg_low  pass     scenario
vr_short  0.369  0.245  0.485        35       36  True       regime
 vr_long  0.294  0.145  0.414        17       30  True       regime
vr_short -0.023 -0.111  0.063        44       50 False   null_const
 vr_long -0.074 -0.178  0.011        29       37 False   null_const
vr_short -0.037 -0.133  0.051        51       50 False null_volonly
 vr_long  0.004 -0.096  0.116        27       34 False null_volonly
```

## Recovery of known states by observable proxies (AUC; 0.5 = chance)
```
        target     proxy   auc
  slow vs rest   vr_long 0.618
rushed vs rest -vr_short 0.760
```

## Multi-seed detection rate (20 seeds per scenario; trials per run = 2 proxies, 1 parameter set)
regime row = detection rate (C3 method works); null rows = false-positive rate (hallucination).
```
    scenario    proxy  n_seeds  pass_rate  mean_diff  mean_seg_high  mean_seg_low
  null_const  vr_long       20       0.00      0.001          30.45         32.95
  null_const vr_short       20       0.00     -0.012          44.75         46.80
null_volonly  vr_long       20       0.05      0.007          32.00         32.20
null_volonly vr_short       20       0.00     -0.006          47.40         48.50
      regime  vr_long       20       0.95      0.228          23.30         24.30
      regime vr_short       20       1.00      0.278          40.60         31.35
```

Figures: cumulative_regime.png, d_by_true_state.png, d_by_proxy_bin.png
