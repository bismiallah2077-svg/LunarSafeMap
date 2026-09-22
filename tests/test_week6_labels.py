#!/usr/bin/env python3
"""Numerical self test for scripts/week6_build_crater_labels.py.

Checks the catalogue parsing, the region test (including a box that crosses
0/360) and the rasterisation of a crater disc, whose area can be predicted
analytically on a lon/lat grid.

Run with:  python tests/test_week6_labels.py
"""
import importlib.util
import math
import sys
import types
from pathlib import Path

import numpy as np

MOD = Path(__file__).resolve().parents[1] / "scripts" / "week6_build_crater_labels.py"

osgeo = types.ModuleType("osgeo")
gdal = types.ModuleType("osgeo.gdal")
gdal.UseExceptions = lambda *a, **k: None
gdal.Open = lambda *a, **k: None
gdal.GetDriverByName = lambda *a, **k: None
gdal.GDT_Byte = 1
osgeo.gdal = gdal
sys.modules["osgeo"] = osgeo
sys.modules["osgeo.gdal"] = gdal

spec = importlib.util.spec_from_file_location("w6l", str(MOD))
w6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w6)

fails = []


def check(name, got, want, tol):
    ok = abs(float(got) - float(want)) <= tol
    print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(name, got, want, "OK" if ok else "FAIL"))
    if not ok:
        fails.append(name)


print("== 1. column detection on a realistic header ==")
hdr = ["CRATER_ID", "CRATER_NAME", "LATITUDE", "LONGITUDE", "DIAMETER", "DEPTH"]
ilat, ilon, idiam = w6.find_columns(hdr)
check("latitude column index", ilat, 2, 0)
check("longitude column index", ilon, 3, 0)
check("diameter column index", idiam, 4, 0)

hdr2 = ["id", "lat", "lon", "diam_km", "depth_km"]
i2 = w6.find_columns(hdr2)
check("short names: lat", i2[0], 1, 0)
check("short names: lon", i2[1], 2, 0)
check("short names: diam", i2[2], 3, 0)

print("")
print("== 2. region test ==")
box = (353.0, 8.0, 359.0, 13.0)
check("point inside", w6.in_box(10.0, 356.0, box), True, 0)
check("point south of box", w6.in_box(7.0, 356.0, box), False, 0)
check("point east of box", w6.in_box(10.0, 359.5, box), False, 0)
span = (350.0, 0.0, 10.0, 20.0)          # crosses 0/360
check("wrap box: 355E inside", w6.in_box(10.0, 355.0, span), True, 0)
check("wrap box: 5E inside", w6.in_box(10.0, 5.0, span), True, 0)
check("wrap box: 20E outside", w6.in_box(10.0, 20.0, span), False, 0)

print("")
print("== 3. subset applies both the box and the diameter cut ==")
rows = [(10.0, 356.0, 5.0), (10.0, 356.5, 0.5), (2.0, 356.0, 3.0), (12.9, 358.9, 2.0)]
sub = w6.subset(rows, (353.0, 8.0, 359.0, 13.0), min_diam=1.0)
check("subset size (expect 2)", len(sub), 2, 0)

print("")
print("== 4. crater disc rasterisation area ==")
# SLDEM study-area grid: 0.001953125 deg/pixel, origin at 353E / 13N
px_deg = 1.0 / 512.0
gt = (353.0 - px_deg / 2, px_deg, 0.0, 13.0 + px_deg / 2, 0.0, -px_deg)
shape = (2561, 3073)
lat0, lon0, diam = 10.0, 356.0, 10.0
mask = w6.crater_disc_mask(shape, gt, [(lat0, lon0, diam)])
expected = math.pi * (diam / 2 / 30.32 / px_deg) * (diam / 2 / 30.32 / px_deg / math.cos(math.radians(lat0)))
got = float(mask.sum())
print("  analytic pixel area: {:.0f}, rasterised: {:.0f}".format(expected, got))
check("disc area within 5 %", got / expected, 1.0, 0.05)

rr, cc = np.nonzero(mask)
lat_c = gt[3] + gt[5] * (rr.mean() + 0.5)
lon_c = gt[0] + gt[1] * (cc.mean() + 0.5)
check("centroid latitude", lat_c, lat0, 0.02)
check("centroid longitude", lon_c, lon0, 0.02)

print("")
print("== 5. two overlapping craters do not double count ==")
m2 = w6.crater_disc_mask(shape, gt, [(lat0, lon0, 10.0), (lat0, lon0, 10.0)])
check("identical discs give the same mask", float(m2.sum()), got, 0)

print("")
print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
