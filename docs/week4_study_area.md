# Week 4: Rimae Bode Study Area & Data Foundation

> LunarSafeMap · 2026-08-17 · status: in progress

## 1. Goal

Build the data foundation for the Rimae Bode candidate landing-site study:

1. Fix the study-area boundary (from Yang et al. 2026).
2. Download the SLDEM2015 tile covering the area (resumable, hashed).
3. Crop + reproject to a uniform grid (`data/interim/week4/`).
4. Generate a study-area base map (`outputs/week4/`).
5. Record every product in `data/metadata/data_manifest.csv`.

## 2. Study Area

Paper: Yang, M., Huang, J., Iqbal, W. et al. "Geology of Rimae Bode region as
priority site candidate for China's first crewed lunar mission."
*Nature Astronomy* (2026). doi:10.1038/s41550-026-02790-0

| item | value |
|---|---|
| region | Rimae Bode (Mare Vaporum – highlands boundary) |
| bbox (E, N) | 353°E–359°E, 8°N–13°N (i.e. 1°W–7°W) |
| center | 356°E, 10.5°N |
| candidate sites | 4 (landing sites 1–4, paper Fig. 5; coords TBD in `configs/landing_sites.csv`) |

## 3. Data Product: SLDEM2015

| item | value |
|---|---|
| product | SLDEM2015_512_00N_30N_315_360_FLOAT |
| source | http://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG/ |
| instrument | LOLA + Kaguya TC (coregistered) |
| resolution | 512 px/deg (~60 m at equator) |
| projection | simple cylindrical, pixel-registered, sphere R=1737.4 km |
| units | km (float32) in IMG; converted to m in GeoTIFF |
| grid | 15360 × 23040 px, 0–30°N, 315–360°E |

## 4. Pipeline

```bash
# 1. download (resume-safe, ~1.32 GB)
bash scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015

# 2. wrap raw IMG in georeferenced VRT, crop study area, km -> m
python scripts/preprocess_week4.py --bbox "353 8 359 13"

# 3. base map: hillshade + elevation + bbox (+ candidate points when filled)
python scripts/make_study_area_map.py

# 4. manifest with sha256
python scripts/build_data_manifest.py data/raw data/metadata/data_manifest.csv
```

## 5. Outputs

- `data/interim/week4/sldem_rimae_bode.tif` (m, float32, ~60 m/px, DEFLATE)
- `outputs/week4/study_area_map.png` (base map)
- `outputs/week4/sldem_study_area_stats.csv`, `study_area_elevation_stats.csv`
- `data/metadata/data_manifest.csv` (ID, type, source, time, res, CRS, size, sha256)

## 6. Remaining this week

- Select and download LROC WAC mosaic / EDR tiles covering the study area.
- Select LROC NAC stereo pairs over Rimae Bode for the ASP workflow.
- Fill `configs/landing_sites.csv` with the four paper candidate points.
- Tile index (`build_tiles.py`) and preprocessing for WAC + NAC.
