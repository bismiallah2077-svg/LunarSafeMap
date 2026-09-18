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

### Week 4 (in progress): Rimae Bode Study Area

- Study area fixed from Yang et al. 2026: 8°N–13°N, 353°E–359°E
- SLDEM2015 tile `SLDEM2015_512_00N_30N_315_360_FLOAT` (512 ppd, ~60 m/px) downloading with resume support
- Resumable downloader: [scripts/download_sldem.sh](scripts/download_sldem.sh)
- Study-area crop + km→m conversion: [scripts/preprocess_week4.py](scripts/preprocess_week4.py)
- Base map: [scripts/make_study_area_map.py](scripts/make_study_area_map.py)
- Manifest builder (attached + detached PDS3 labels): [scripts/build_data_manifest.py](scripts/build_data_manifest.py)
- See [docs/week4_study_area.md](docs/week4_study_area.md) for details

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

Week 4 (once the SLDEM tile is downloaded):

```bash
bash scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015
python scripts/preprocess_week4.py --bbox "353 8 359 13"
python scripts/make_study_area_map.py
python scripts/build_data_manifest.py data/raw data/metadata/data_manifest.csv
```

## Data Policy

Large planetary data products are not committed to Git. Raw data, intermediate products, ASP outputs, and model weights stay outside the repository; provenance is recorded in `data/metadata/data_manifest.csv`.
