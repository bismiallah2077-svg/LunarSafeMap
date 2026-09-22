# LunarSafeMap

LunarSafeMap is an undergraduate research project for learning and reproducing planetary remote sensing and deep-space mapping workflows, targeting lunar landing-site terrain safety and scientific value assessment (Rimae Bode, Nature Astronomy 2026).

## Current Progress

### Week 1-2: Environment & Planetary Data

- WSL2 Ubuntu 24.04 + conda environments (`asp`, `lunarsafe`)
- NASA Ames Stereo Pipeline 3.7.0 + ISIS 10.0.0 + GDAL 3.12
- Downloaded LROC NAC stereo pair M181058717LE / M181073012LE (2012-01-13) from PDS
- Imported to ISIS (`lronac2isis`), initialized geometry (`spiceinit`), calibrated (`lronaccal`)
- Generated `data/metadata/data_manifest.csv` (product ID, time, SHA-256, source URL)

### Week 3: Stereo DEM + First Error Analysis

- Reprojected overlap crops (SimpleCylindrical, 4 m/px)
- Generated point cloud, DEM, orthoimage and triangulation error map with ASP
- Compared ASP DEM against LDEM_128 reference
- **Result**: systematic vertical offset ≈ −264 m (datum mismatch); detrended RMSE ≈ 23 m
- See [docs/reproduction.md](docs/reproduction.md) for the full report

### Week 4: Rimae Bode study area + first NAC stereo DEM

**Study area & data foundation**

- Study area fixed from Yang et al. 2026: 8°N–13°N, 353°E–359°E
- LROC WAC mosaic for the area (100 m/px) from the USGS Moon WMS — [scripts/download_wac.py](scripts/download_wac.py)
- SLDEM2015 tile (512 ppd, ~59 m/px, 1.42 GB) downloaded complete — [scripts/download_sldem.sh](scripts/download_sldem.sh)
- Study-area DEM crop + km→m (3073 × 2561 px) — [scripts/preprocess_week4.py](scripts/preprocess_week4.py)
- Lunar CRS for the WMS GeoTIFF — [scripts/preprocess_wac.py](scripts/preprocess_wac.py)
- Base map with landmark craters — [scripts/make_study_area_map.py](scripts/make_study_area_map.py)
- Data manifest with size verification against the PDS labels — [scripts/build_data_manifest.py](scripts/build_data_manifest.py)

**Stereo pair found and processed**

- Pair: M1406988604LE + M1406995626LE (2022-05-12, orbits 57968/57969,
  convergence 23.1°) — found with [scripts/find_stereo_pairs.py](scripts/find_stereo_pairs.py)
  and validated with [scripts/stereo_check.py](scripts/stereo_check.py)
- Pipeline: ISIS import/calibrate/project → ASP `parallel_stereo` + `point2dem` —
  [scripts/run_nac_pair_rimae_bode.sh](scripts/run_nac_pair_rimae_bode.sh)
- SPIKE kernels for recent LROC data have to be supplied by hand:
  [docs/lroc_spice_kernels.md](docs/lroc_spice_kernels.md)
- **DEM**: 2176 × 13866 px at 3.28 m/px, 7 × 45 km strip, intersection error
  median 4.46 m
- **vs SLDEM2015**: vertical datum agrees to < 1 m (median offset −0.83 m);
  RMSE 35.3 m overall, but only 4 m MAE on terrain flatter than 5°, rising to
  ~88 m on crater walls steeper than 25° — see
  [docs/week4_nac_dem_results.md](docs/week4_nac_dem_results.md)

### Week 5: Terrain metrics, slope safety and uncertainty

- Slope / roughness / relief at 20, 60 and 200 m support, from both the NAC DEM
  (3.28 m/px) and SLDEM2015 (59 m/px) — [scripts/week5_terrain_metrics.py](scripts/week5_terrain_metrics.py)
- Slope fields agree at matched resolution (median difference −0.05°, MAE 1.58°),
  but SLDEM **misses 11.4 / 16.9 / 31.1 %** of the terrain steeper than
  10 / 15 / 20° — the safety-relevant conclusion of the week
- First risk map (slope ≥ 15° or roughness ≥ 2 m) with a threshold sweep —
  [scripts/week5_risk_map.py](scripts/week5_risk_map.py)
- Spatial error structure: along-track and across-swath profiles, residual map,
  residual vs intersection error — [scripts/week5_error_spatial.py](scripts/week5_error_spatial.py)
- **Result**: at 60 m support, SLDEM calls 60 % of the scene safe but only 37 %
  when restricted to the NAC footprint; coarse DEMs over-estimate safe area
- See [docs/progress_review_weeks1_6.md](docs/progress_review_weeks1_6.md) for the
  plan-vs-actual review

### Week 6: Automatic crater detection (PyTorch U-Net baseline)

- Labels: **Robbins (2018)** global catalogue (1,296,796 craters) — 9,457 craters
  in the training box, 535 in the study area — [scripts/week6_build_crater_labels.py](scripts/week6_build_crater_labels.py)
- Model: U-Net, 1,286,417 parameters, CPU training (12 epochs ≈ 11 min),
  BCE + Dice loss, per-tile robust standardisation —
  [scripts/week6_train_unet.py](scripts/week6_train_unet.py)
- **Geographic split** (no random tiles): south of 14°N trains, north of 14°N
  validates, Rimae Bode is the untouched test set
- **Pixel level**: test IoU 0.298, F1 0.460 (validation IoU 0.266) — the model
  transfers to unseen terrain
- **Detection level**: F1 0.488 overall; **8/8 craters ≥ 5 km, zero false
  positives**; 1–2 km craters are the bottleneck (R 0.512) —
  [scripts/week6_mask_to_catalog.py](scripts/week6_mask_to_catalog.py)
- Output catalogue with longitude, latitude and diameter:
  `outputs/week6/craters_detected.geojson` (632 features)
- **Feature ablation** (same seed, same 400 tiles, only the input channels change):
  DEM F1 0.460 → DEM+slope 0.462 → **DEM+slope+shade 0.548**; slope alone only
  shifts the trade-off (precision 0.368→0.447, recall 0.613→0.478), while
  hillshade lifts precision to 0.628 and cuts spurious detections from 347 to 81
  (detection-level F1 0.488 → 0.542) — [scripts/week6_ablation.sh](scripts/week6_ablation.sh)
- Methods, formulas and the 8 debugging lessons:
  [docs/week6_crater_detection.md](docs/week6_crater_detection.md)
## Environments

### Python geospatial environment

```bash
conda activate lunarsafe
```

Used for raster processing, GIS, terrain analysis, and later machine learning.

### ASP environment

```bash
conda activate asp
export ISISDATA=/home/zwx/miniconda3/envs/asp/data
```

Verified versions: ASP 3.7.0, ISIS 10.0.0, GDAL 3.12.

## Reproduce

Week 2–3 (already completed):

```bash
bash scripts/run_week2_3.sh
```

Outputs land in `outputs/week23/`; error statistics in `dem_error_summary.csv` and `error_vs_covariates.csv`.

Week 4 (study-area foundation):

```bash
python scripts/download_wac.py --bbox "353 8 359 13" --res 100
bash scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015
python scripts/preprocess_week4.py --bbox "353 8 359 13"
python scripts/preprocess_wac.py
python scripts/make_study_area_map.py
python scripts/build_data_manifest.py data/raw data/metadata/data_manifest.csv
```

## Data Policy

Large planetary data products are not committed to Git. Raw data, intermediate products, ASP outputs, and model weights stay outside the repository; provenance is recorded in `data/metadata/data_manifest.csv`.
