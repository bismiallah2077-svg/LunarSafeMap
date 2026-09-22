#!/usr/bin/env python3
"""Numerical self test for scripts/week5_error_spatial.py.

GDAL and matplotlib are stubbed out so the binning, block-median and
plane-fitting logic can be checked against synthetic fields whose answer is
known analytically.  Run with:  python tests/test_week5_error_spatial.py
"""
import importlib.util, sys, types
import numpy as np

MOD = r"C:\Users\zwx\Documents\Codex\2026-08-14\w\scripts\week5_error_spatial.py"

osgeo = types.ModuleType("osgeo")
gdal = types.ModuleType("osgeo.gdal")
gdal.UseExceptions = lambda *a, **k: None
osgeo.gdal = gdal
sys.modules["osgeo"] = osgeo
sys.modules["osgeo.gdal"] = gdal

mpl = types.ModuleType("matplotlib")
mpl.use = lambda *a, **k: None
pyplot = types.ModuleType("matplotlib.pyplot")
mpl.pyplot = pyplot
sys.modules["matplotlib"] = mpl
sys.modules["matplotlib.pyplot"] = pyplot

spec = importlib.util.spec_from_file_location("wes", str(MOD))
wes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wes)

fails = []


def check(name, got, want, tol):
    ok = abs(got - want) <= tol
    print("  {:56s} got {:9.4f}  want {:9.4f}  {}".format(name, got, want, "OK" if ok else "FAIL"))
    if not ok:
        fails.append(name)


print("== 1. bin_profile recovers a known along-track ramp ==")
ny, nx = 4000, 500
ramp = np.linspace(-10.0, 10.0, ny, dtype="float32")
resid = np.repeat(ramp[:, None], nx, axis=1)
valid = np.ones_like(resid, dtype=bool)
c, med, q1, q3, n = wes.bin_profile(resid, valid, axis=0, nbins=10)
check("median of first bin (expect ~ -9.5)", float(med[0]), -9.5, 0.6)
check("median of last bin  (expect ~ +9.5)", float(med[-1]), 9.5, 0.6)
check("mean of the two central bins (expect ~ 0)", float(0.5 * (med[4] + med[5])), 0.0, 0.6)
check("all bins populated", float(len(c)), 10.0, 0.001)

print("")
print("== 2. bin_profile across the swath axis ==")
across = np.linspace(0.0, 5.0, nx, dtype="float32")
resid2 = np.repeat(across[None, :], 200, axis=0)
v2 = np.ones_like(resid2, dtype=bool)
c2, med2, _, _, _ = wes.bin_profile(resid2, v2, axis=1, nbins=5)
check("first across bin (expect ~ 0.5)", float(med2[0]), 0.5, 0.3)
check("last across bin  (expect ~ 4.5)", float(med2[-1]), 4.5, 0.3)

print("")
print("== 3. coarse_grid on a constant field ==")
const = np.full((400, 400), 3.5, dtype="float32")
vc = np.ones_like(const, dtype=bool)
grid, cnt = wes.coarse_grid(const, vc, 20)
check("block median (expect 3.5)", float(np.nanmean(grid)), 3.5, 1e-4)

print("")
print("== 4. coarse_grid ignores invalid blocks ==")
const2 = np.full((400, 400), 3.5, dtype="float32")
vc2 = np.ones_like(const2, dtype=bool)
vc2[:200, :] = False
grid2, _ = wes.coarse_grid(const2, vc2, 20)
check("valid blocks share (expect 0.5)", float(np.isfinite(grid2).mean()), 0.5, 0.05)
check("invalid half is nan", float(np.isfinite(grid2[:10, :]).sum()), 0.0, 0.001)

print("")
print("== 5. plane_fit recovers a known tilt ==")
cell_m = 210.0
ny2, nx2 = 40, 60
yy, xx = np.mgrid[0:ny2, 0:nx2]
slope_m_per_cell = 2.0            # 2 m per cell along x
grid3 = (slope_m_per_cell * xx).astype("float64")
pf = wes.plane_fit(grid3, cell_m)
want = slope_m_per_cell / (cell_m / 1000.0)      # m/km
check("x tilt m/km (expect {:.2f})".format(want), pf[0], want, 1e-6)
check("y tilt m/km (expect 0)", pf[1], 0.0, 1e-6)

print("")
print("== 6. ascii_map runs and has the expected shape ==")
txt = wes.ascii_map(grid3)
expected_lines = float(len(range(0, 40, max(1, 40 // 18))))
check("number of lines", float(len(txt.split(chr(10)))), expected_lines, 0.001)
print("  sample:")
for line in txt.split(chr(10))[:3]:
    print("   |" + line)

print("")
print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
