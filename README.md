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
