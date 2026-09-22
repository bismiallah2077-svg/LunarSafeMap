#!/usr/bin/env python3
"""Numerical self test for scripts/week5_risk_map.py.

GDAL is stubbed out so the classification rule, the area statistics and the
multi-scale metric machinery can be checked against synthetic fields whose
answer is known analytically.

Run with:  python tests/test_week5_risk.py
"""
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np

MOD = Path(__file__).resolve().parents[1] / "scripts" / "week5_risk_map.py"

osgeo = types.ModuleType("osgeo")
gdal = types.ModuleType("osgeo.gdal")
for name in ("UseExceptions", "Warp"):
    setattr(gdal, name, lambda *a, **k: None)
gdal.Open = lambda *a, **k: None
gdal.GetDriverByName = lambda *a, **k: None
gdal.GDT_Byte = 1
osgeo.gdal = gdal
sys.modules["osgeo"] = osgeo
sys.modules["osgeo.gdal"] = gdal

spec = importlib.util.spec_from_file_location("wrm", str(MOD))
wrm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrm)

fails = []


def check(name, got, want, tol=1e-6):
    ok = abs(float(got) - float(want)) <= tol
    print("  {:56s} got {:9.4f}  want {:9.4f}  {}".format(name, got, want, "OK" if ok else "FAIL"))
    if not ok:
        fails.append(name)


print("== 1. classification rule ==")
shape = (10, 10)
flat_slope = np.full(shape, 2.0)
flat_rough = np.full(shape, 0.5)
valid = np.ones(shape, dtype=bool)
cls = wrm.classify(flat_slope, flat_rough, valid, slope_thr=15.0, rough_thr=5.0)
check("flat and smooth -> all safe", float((cls == wrm.CLASS_SAFE).sum()), 100.0, 0.5)

steep = np.full(shape, 20.0)
cls = wrm.classify(steep, flat_rough, valid, slope_thr=15.0)
check("slope 20 deg vs 15 deg limit -> all danger",
      float((cls == wrm.CLASS_DANGER).sum()), 100.0, 0.5)

mid = np.full(shape, 12.0)
cls = wrm.classify(mid, flat_rough, valid, slope_thr=15.0, caution_frac=0.75)
check("slope 12 deg -> caution band", float((cls == wrm.CLASS_CAUTION).sum()), 100.0, 0.5)

cls = wrm.classify(flat_slope, np.full(shape, 6.0), valid, rough_thr=5.0)
check("roughness 6 m vs 5 m limit -> danger",
      float((cls == wrm.CLASS_DANGER).sum()), 100.0, 0.5)

v2 = valid.copy()
v2[:5, :] = False
cls = wrm.classify(flat_slope, flat_rough, v2)
check("invalid half -> nodata", float((cls == wrm.CLASS_NODATA).sum()), 50.0, 0.5)

print("")
print("== 2. area fractions ==")
arr = np.array([[0, 0, 0, 1, 1, 2, 255, 255]], dtype=np.uint8)
f = wrm.fractions(arr)
check("safe %", f["safe_pct"], 50.0, 0.01)
check("caution %", f["caution_pct"], 33.33, 0.01)
check("danger %", f["danger_pct"], 16.67, 0.01)
check("counted pixels", f["n"], 6.0, 0.01)

print("")
print("== 3. block_mean preserves a constant and tracks validity ==")
const = np.full((400, 400), 7.0, dtype="float32")
vv = np.ones_like(const, dtype=bool)
bm, frac = wrm.block_mean(const, vv, 20)
check("block mean of a constant", float(np.nanmean(bm)), 7.0, 1e-5)
check("valid fraction", float(np.nanmean(frac)), 1.0, 1e-5)
vv2 = vv.copy()
vv2[:200, :] = False
bm2, frac2 = wrm.block_mean(const, vv2, 20)
check("half-valid blocks", float(np.nanmean(frac2)), 0.5, 0.01)

print("")
print("== 4. multi-scale slope on a tilted plane ==")
ny, nx = 600, 600
px = 3.283
xx = np.arange(nx) * px
tilt = 12.0
z = np.tile((xx * np.tan(np.radians(tilt))).astype("float32"), (ny, 1))
val = np.ones_like(z, dtype=bool)
for support in (20.0, 60.0):
    slope, rough, eff, good, rwin = wrm.metrics(z, val, px, support)
    check("tilt 12 deg at {:.0f} m support".format(support),
          float(np.nanmean(slope[good])), tilt, 0.2)
    check("roughness of a plane at {:.0f} m".format(support),
          float(np.nanmean(rough[good])), 0.0, 0.02)   # float32 precision

print("")
print("== 5. end to end: a 20 deg half-scene must be half danger ==")
# a wide scene keeps the step boundary a small fraction of the area
z2 = np.zeros((400, 3600), dtype="float32")
xx2 = np.arange(3600) * px
z2[:, 1800:] = (xx2[:1800] * np.tan(np.radians(20.0))).astype("float32")
val2 = np.ones_like(z2, dtype=bool)
slope2, rough2, eff2, good2, _rw2 = wrm.metrics(z2, val2, px, 60.0)
cls2 = wrm.classify(slope2, rough2, good2, slope_thr=15.0, rough_thr=100.0)
f2 = wrm.fractions(cls2)
check("danger fraction (expect ~50 %)", f2["danger_pct"], 50.0, 2.5)

print("")
print("== 6. residual roughness responds to noise, not to tilt ==")
rng = np.random.default_rng(0)
plane = np.tile((np.arange(600) * px * np.tan(np.radians(10.0))).astype("float32"), (600, 1))
val6 = np.ones_like(plane, dtype=bool)
_, r_plane, _, _, _ = wrm.metrics(plane, val6, px, 20.0)
check("tilted plane roughness ~ 0", float(np.nanmean(r_plane)), 0.0, 0.02)
noisy = plane + rng.normal(0.0, 1.0, plane.shape).astype("float32")
_, r_noisy, _, _, _ = wrm.metrics(noisy, val6, px, 20.0)
check("1 m noise -> roughness ~ 1 m", float(np.nanmean(r_noisy)), 1.0, 0.35)

print("")
print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
