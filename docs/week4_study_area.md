# Week 4: Rimae Bode Study Area & Data Foundation

> LunarSafeMap · updated 2026-09-18 · status: WAC + DEM foundation complete

## 1. Goal

Build the data foundation for the Rimae Bode candidate landing-site study:

1. Fix the study-area boundary (from Yang et al. 2026).
2. Download WAC imagery and the SLDEM2015 tile covering the area.
3. Crop + reproject everything to a uniform grid (`data/interim/week4/`).
4. Generate a study-area base map (`outputs/week4/`).
5. Record every product in `data/metadata/data_manifest.csv`.

## 2. Study Area

Paper: Yang, M., Huang, J., Iqbal, W. et al. "Geology of Rimae Bode region as
priority site candidate for China's first crewed lunar mission."
*Nature Astronomy* (2026). doi:10.1038/s41550-026-02790-0

| item | value |
|---|---|
| region | Rimae Bode (Sinus Aestuum – highlands boundary) |
| bbox (E, N) | 353°E–359°E, 8°N–13°N (i.e. 1°W–7°W) |
| center | 356°E, 10.5°N |
| candidate sites | 4 (Fig. 5); coordinates partly filled in `configs/landing_sites.csv` |

### Landmark craters (paper Supplementary Table 1)

| landmark | lon (°E) | lat (°N) |
|---|---|---|
| Bode C | 355.23 | 12.22 |
| fresh crater | 355.57 | 11.46 |

## 3. Data Products

| product | source | resolution | notes |
|---|---|---|---|
| LROC WAC mosaic | USGS Moon WMS, layer `LROC_WAC` | 100 m/px | 1819 × 1516 RGB GeoTIFF, study area |
| SLDEM2015 tile | `imbrium.mit.edu` (LOLA + Kaguya TC) | 512 ppd (~59 m) | 1,415,577,600 B, complete |
| LROC NAC EDR pair | PDS LROC (week 2–3) | 0.5–1.5 m/px | M181058717LE / M181073012LE |

### Why the WMS route for WAC

The LROC WAC global mosaic is ~100 GB as a whole; the USGS planetary WMS
(`/maps/earth/moon_simp_cyl.map`, layer `LROC_WAC`) returns just the study area
as a GeoTIFF in one request. Coordinates are selenographic lon/lat even though
the file is tagged EPSG:4326, so `scripts/preprocess_wac.py` re-assigns a lunar
sphere CRS (R = 1737.4 km).

## 4. Pipeline

```bash
# 1. WAC mosaic for the study area (~8 MB, one WMS request)
python scripts/download_wac.py --bbox "353 8 359 13" --res 100

# 2. SLDEM2015 tile (resume-safe, 1.32 GB)
bash scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015

# 3. crop SLDEM to study area, km -> m
python scripts/preprocess_week4.py --bbox "353 8 359 13"

# 4. give the WAC GeoTIFF a lunar CRS
python scripts/preprocess_wac.py

# 5. base map: hillshade + elevation + landmarks
python scripts/make_study_area_map.py

# 6. manifest with sha256 and completeness check
python scripts/build_data_manifest.py data/raw data/metadata/data_manifest.csv
```

## 5. Results (2026-09-18)

| item | value |
|---|---|
| study-area DEM | `data/interim/week4/sldem_rimae_bode.tif` |
| DEM size / grid | 3073 × 2561 px, 1/512° (~59 m), float32, metres |
| DEM elevation | min −2154.44 m, max +995.84 m, mean −800.94 m, std 308.59 m |
| study-area WAC | `data/interim/week4/wac_rimae_bode.tif` (1819 × 1516 px, 100 m/px, RGB) |
| base map | `outputs/week4/study_area_map.png` |

The DEM result was reproduced twice (before and after the file-system incident
on 2026-09-16) with identical statistics.

## 6. Data completeness (checked automatically)

`scripts/build_data_manifest.py` compares every product with the size declared
in its PDS label and prints `size=complete` / `size=PARTIAL x/y`:

| product | state |
|---|---|
| SLDEM2015_512_00N_30N_315_360_FLOAT | complete (1,415,577,600 B) |
| LROC NAC M181058717LE / M181073012LE | complete (264,467,400 B each) |
| WAC_LROC_353E_359E_8N_13N_100m | complete (8,282,338 B) |
| SLDEM2015_512_30S_00S_000_045_FLOAT | PARTIAL 27.7% (week-3 site, not needed) |

## 7. Remaining

- **NAC stereo pair over Rimae Bode** — `scripts/search_lroc.py` posts the LROC
  archive query, but the service (wms.lroc.asu.edu / data.lroc.im-ldi.com)
  answers with the search form instead of results, so the pair still has to be
  selected through the browser UI or by another archive route.
- **Candidate landing sites** — site 3 is derived (~6 km east of Bode C,
  355.43°E 12.22°N); sites 1, 2 and 4 are placeholders to be read off Fig. 5.
- Tile index: `outputs/week4/tile_index.csv` (30 tiles of 512 px / ~30.3 km, with elevation and slope statistics) via `scripts/build_tiles.py`.
- NAC download helper for the pair you pick in QuickMap: `scripts/fetch_nac.py`.
- Human-in-the-loop steps are listed in [manual_checklist_CN.md](manual_checklist_CN.md).