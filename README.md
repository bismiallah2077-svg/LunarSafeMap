# LunarSafeMap

LunarSafeMap is an undergraduate research project for learning and reproducing planetary remote sensing and deep-space mapping workflows, targeting lunar landing-site terrain safety and scientific value assessment (Rimae Bode, Nature Astronomy 2026).

## Current Progress

### Week 1–2: Environment & Planetary Data

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

```bash
bash scripts/run_week2_3.sh
```

Outputs land in `outputs/week23/`; error statistics in `dem_error_summary.csv` and `error_vs_covariates.csv`.

## Data Policy

Large planetary data products are not committed to Git. Raw data, intermediate products, ASP outputs, and model weights stay outside the repository; provenance is recorded in `data/metadata/data_manifest.csv`.
