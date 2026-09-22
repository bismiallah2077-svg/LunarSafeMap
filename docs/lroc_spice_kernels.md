# LROC SPICE kernel setup for ISIS (what actually works)

> LunarSafeMap · 2026-09-22 · written after getting 2022 LROC NAC images
> through `spiceinit` on ISIS 10.0.0

## The problem

`spiceinit` needs three kinds of kernels for an LROC NAC cube:

| role | what it describes | frame |
|---|---|---|
| SPK | spacecraft orbit / position | -85 |
| CK  | spacecraft bus **attitude** | -85000 `LRO_SC_BUS` |
| CK (extra) | LROC camera orientation relative to the bus | -85600 `LRO_LROCNACL` |

The LRO kernel database shipped with ISIS only covers roughly 2011-2019, so
recent images fail with

```
Error = "Spice file does not exist [.../kernels/spk/fdf29r_...bsp]"
Error = "The ck rotation from frame -85000 can not be found ..."
```

`spiceinit web=yes` is meant to fetch the kernels automatically, but the
hosted service (`https://astrogeology.usgs.gov/apis/ale/v0.9.1/spiceserver/`)
answers `{"error":"Bad Request"}` for LROC queries, and the ISIS Qt client does
not use the WSL proxy anyway.  Supplying the kernels locally is the reliable
route.

## The file families (verified by reading the kernel headers)

| NAIF file | contents | size | source |
|---|---|---|---|
| `lrorg_YYYYDDD_YYYYDDD_v01.bsp` | reconstructed **orbit** | ~7 MB / 90 d | `pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/spk/` |
| `lrosc_YYYYDDD_YYYYDDD_v01.bc` | definitive **spacecraft attitude** | ~500 MB / 10 d | same volume, `ck/` |
| `lrolc_YYYYDDD_YYYYDDD_v01.bc` | temperature corrected **LROC camera** attitude | ~15 MB / 30 d | `pub/naif/LRO/kernels/ck/` |

Do **not** pick these, they are other instruments:

| file | actually contains |
|---|---|
| `lrodv_*` | Diviner (DLRE) pointing, frames -85204/-85202 |
| `lrohg_*` | High Gain Antenna, frame -85020 |
| `lrosa_*` | Solar Array, frame -85030 |

## Working command

```bash
LRO=$ISISDATA/lro/kernels

spiceinit from=cube.cub \
  SPK="$LRO/spk/lrorg_2022074_2022166_v01.bsp" \
  CK="$LRO/ck/lrosc_2022131_2022141_v01.bc" \
  EXTRA="$LRO/ck/lrolc_2022120_2022152_v01.bc"
```

Two details that cost several iterations:

1. **`CK=` takes a list but the command line syntax needs parentheses**
   (`CK=(a.bc,b.bc)`, and the parentheses must be escaped in bash).  Passing
   `CK="a.bc,b.bc"` silently treats it as a single file name containing a
   comma - the error message shows the two paths joined by a comma.  Using
   `EXTRA=` for the second kernel avoids the problem completely.
2. **Match the time coverage.**  `lrosc` files are 10 day chunks, `lrolc` and
   `lrorg` are 30-90 day chunks, so check that the acquisition date lies
   inside the `YYYYDDD_YYYYDDD` range (DOY = day of year).

## Verifying a download

```bash
ls -l $LRO/spk/lrorg_*.bsp $LRO/ck/lrosc_*.bc
ckbrief $LRO/ck/lrosc_2022131_2022141_v01.bc | head -20   # segments and frames
```

`ckbrief` prints one line per segment with the frame ID; look for -85000.

## Results obtained with this setup (2022-05-12 pair)

| check | value |
|---|---|
| convergence angle from ASP preprocessing | 22.85 / 22.94 / 23.01 deg (25/50/75%) |
| DEM vs SLDEM2015 median offset | -0.83 m |
| DEM vs SLDEM2015 RMSE | 35.3 m (33.2 m at matched resolution) |
| ASP intersection error | median 4.46 m, p90 6.19 m |

## A Python gotcha worth remembering

```python
ref = gdal.Open(path).GetRasterBand(1).ReadAsArray()   # can fail randomly
ref_ds = gdal.Open(path)                               # keep the dataset alive
ref = ref_ds.GetRasterBand(1).ReadAsArray()
```

The dataset returned by a temporary expression can be garbage collected before
the band is read, which surfaces as
`TypeError: in method 'Band_XSize_get', argument 1 of type 'GDALRasterBandShadow *'`.