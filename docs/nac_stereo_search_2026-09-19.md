# NAC stereo search over Rimae Bode - findings (2026-09-19)

## Result: stereo pair found

| | primary | partner |
|---|---|---|
| product | **M1406995626LE** | **M1406988604LE** |
| acquisition | 2022-05-12 11:52:39 | 2022-05-12 09:55:36 |
| orbit | 57969 | 57968 (previous orbit) |
| slew angle | +16.10 deg | -6.14 deg |
| incidence | 47.73 deg | 48.70 deg |
| emission | 18.62 deg | 4.72 deg |
| resolution | 0.885 m/px | 0.849 m/px |
| centre | 9.88N 354.81E | 9.88N 354.80E |
| volume | LROLRC_0051B / DATA/ESM4/2022132/NAC | same |

**Convergence angle 23.11 deg**, centre separation 0.3 km, overlap
0.25 x 1.50 deg (~7.6 x 45 km) - a good stereo pair for DEM extraction
(verified with `scripts/stereo_check.py`).

Note: `M1406995626LC` is the CDR version of the *same* acquisition, not a
stereo partner (convergence 0.00 deg).

## How it was found

1. Scripted access to the LROC image search is blocked (the service needs a
   browser session); the browser search around the target point returns only
   the single NAC acquisition, which is correct - NAC coverage at a given
   point is usually one pass.
2. The LROC volume index files are downloadable:

       https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/<VOLUME>/INDEX/INDEX.TAB

   83-column CSV (INDEX.LBL defines the columns). 103 volumes exist in the
   EDR collection, ~2.9 GB of index in total.
3. `scripts/find_stereo_pairs.py` downloads/loads those indexes and searches
   for NAC pairs intersecting a region, ranking them by convergence angle.

## Two traps hit on the way

* **Truncated index downloads.** The first batch was fetched with a 25 s
  timeout; LROLRC_0051B came down as 2.3 MB instead of 16.3 MB and the
  analysis wrongly concluded "no stereo pairs". `fetch_index_safe.py` now
  resumes with Range and verifies the size against Content-Length.
* **0/360 meridian wrap.** A strip straddling longitude 0 looked 360 deg wide
  and "overlapped" everything, producing false pairs. `find_stereo_pairs.py`
  now unwraps longitudes before comparing bounding boxes.

## Other candidates in the study area

The same run listed 15 pairs with 12-35 deg convergence. Besides the pair
above, the June 2022 images (`M1409326660`, `M1409333683`, `M1409340707`)
form pairs at 22-23 deg convergence but with incidence 75-77 deg (very
oblique illumination), so they are second choice.

## Next steps

1. Download the pair (2 x 264 MB) - in progress, staged in
   `downloads/lroc_nac_rimae_bode/`.
2. Copy into `data/raw/lroc_nac_rimae_bode/` in the WSL repo, add both products
   to `data/metadata/data_manifest.csv`.
3. Run the ISIS chain (`lronac2isis -> spiceinit -> lronaccal -> crop -> cam2map`)
   on both, then `parallel_stereo -> point2dem` (ASP) over the overlap.
4. Compare the resulting DEM against SLDEM2015 for the same window and report
   mean/RMSE, following the week-3 method (`scripts/compare_dem.py`).