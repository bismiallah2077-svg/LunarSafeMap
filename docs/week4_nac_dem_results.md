# Week 4 result: NAC stereo DEM over Rimae Bode

> LunarSafeMap · 2026-09-22

## Stereo pair

| | primary | partner |
|---|---|---|
| product | M1406995626LE | M1406988604LE |
| acquisition | 2022-05-12 11:52:39 | 2022-05-12 09:55:36 |
| orbit | 57969 | 57968 |
| slew | +16.10 deg | -6.14 deg |
| incidence | 47.7 deg | 48.7 deg |
| emission | 18.6 deg | 4.7 deg |
| resolution | 0.885 m/px | 0.849 m/px |
| volume | LROLRC_0051B / DATA/ESM4/2022132/NAC | same |

Convergence angle measured by ASP preprocessing: 22.85 / 22.94 / 23.01 deg
(25/50/75 percentiles), matching the 23.11 deg predicted from the metadata.

## Processing chain

```
lronac2isis -> spiceinit -> lronaccal -> cam2map  (ISIS 10.0.0, 1 m/px)
  -> parallel_stereo (asp_mgm, subpixel 9)  -> point2dem
```

`spiceinit` needed three hand-supplied kernels (ISIS only ships LRO kernels up
to ~2019) - see [lroc_spice_kernels.md](lroc_spice_kernels.md).

## Products

| file | size | grid |
|---|---|---|
| outputs/week4/nac_dem.tif | 29.7 MB | 2176 x 13866 px, 3.283 m/px |
| outputs/week4/nac_ortho.tif | 61.8 MB | same grid |
| outputs/week4/nac_intersection_err.tif | 22.5 MB | same grid |

The DEM covers a 7.1 x 45.5 km strip (the full stereo overlap), elevation
-1296.5 m to +848.8 m, mean -741.9 m.

| quality metric | value |
|---|---|
| valid pixels | 53.69 % |
| ASP intersection error | median 4.46 m, p90 6.19 m |

## Comparison with SLDEM2015

SLDEM was warped onto the NAC DEM grid (bilinear). Two comparisons were made:
at full resolution, and after block averaging both to the SLDEM sampling
(~59 m) to separate the resolution effect from real differences.

| metric | full resolution (3.28 m) | resolution matched (59 m) |
|---|---:|---:|
| common pixels | 16,198,623 | 49,990 |
| median offset | -0.832 m | -0.842 m |
| mean | +0.761 m | +0.669 m |
| std | 35.253 m | 33.199 m |
| RMSE (raw) | 35.261 m | 33.205 m |
| RMSE (de-trended) | 35.289 m | 33.233 m |
| MAE (de-trended) | 10.866 m | 10.698 m |
| p1 / p99 | -27.5 / +33.0 m | -27.3 / +33.0 m |

**The vertical datum agrees to better than 1 m** (median offset -0.83 m).  This
is the key difference from the week-3 experiment, where the ASP DEM was offset
by -264 m against LDEM_128.

### The difference is not a registration problem

A least-squares fit of the residual against the terrain gradient
(`z_nac - z_sldem ~ a dz/dx + b dz/dy + c`) gives a misregistration vector of
only (-5.6 m, +3.5 m), i.e. under two NAC pixels, and removing it makes the
RMSE slightly worse (35.261 -> 35.325 m).  Horizontal misregistration is
therefore excluded.

### The difference grows with terrain slope

| slope bin | pixels | mean slope | mean difference | MAE |
|---|---:|---:|---:|---:|
| 0-2 deg | 805,676 | 1.27 | +0.14 m | 4.05 m |
| 2-5 deg | 2,676,442 | 3.60 | +0.01 m | 4.78 m |
| 5-10 deg | 5,336,981 | 7.47 | -0.32 m | 7.10 m |
| 10-15 deg | 4,082,345 | 12.32 | +0.92 m | 11.71 m |
| 15-20 deg | 2,298,433 | 17.20 | -1.66 m | 16.20 m |
| 20-25 deg | 795,850 | 21.79 | -1.95 m | 20.06 m |
| 25-90 deg | 167,320 | 37.72 | +68.77 m | 87.93 m |

## Conclusions

1. The NAC DEM and SLDEM2015 share the same vertical datum (offset < 1 m), so
   the SPICE kernel chain used here is consistent.
2. Stereo matching itself is precise: intersection error median 4.5 m at
   0.85 m/px ground sampling.
3. The 35 m RMSE is not a registration artefact and is not removed by
   resolution matching - it is a **slope dependent** difference: 4 m MAE on
   terrain flatter than 5 deg, 20 m at 20-25 deg, and ~88 m on the steepest
   crater walls.
4. Consequence for the project: **slope-derived safety metrics taken from
   SLDEM2015 are unreliable exactly where they matter most** - on crater walls
   steeper than ~25 deg.  Week 5 must quantify this (compare slope fields at
   matched resolution and count threshold crossings).

## Reproduction

```bash
bash scripts/install_kernels_and_run.sh     # kernels + ISIS + ASP
bash scripts/analyze_nac_result.sh          # DEM vs SLDEM comparison
bash scripts/analyze_coregistration.sh      # registration + slope dependence
```