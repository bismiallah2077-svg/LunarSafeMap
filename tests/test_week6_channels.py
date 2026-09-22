#!/usr/bin/env python3
"""Numerical self test for the week-6 input channels and tile augmentation.

Three things are checked against closed-form answers:
  1. build_channels() on a synthetic tilted plane: the slope channel must equal
     atan(dz/dx) in degrees / 45, the hillshade channel must equal
     (sin(45 deg) + 1) / 2 on flat ground, and the DEM channel must be the
     per-tile standardised elevation.
  2. augment_tile() must keep the (C, H, W) shape for every channel count.
     This is the regression that broke the 3-channel run: np.rot90(x, k) on a
     (1, 256, 256) tile rotates axes 0 and 1 and returns (256, 1, 256).
  3. the U-Net first layer must grow by exactly 144 weights per extra channel.

Run with:  python tests/test_week6_channels.py
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

MOD = Path(__file__).resolve().parents[1] / "scripts" / "week6_train_unet.py"
spec = importlib.util.spec_from_file_location("w6u", str(MOD))
w6 = importlib.util.module_from_spec(spec)
sys.modules["w6u"] = w6
spec.loader.exec_module(w6)

fails = []


def check(name, got, want, tol=1e-6):
    ok = abs(float(got) - float(want)) <= tol
    print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(
        name, got, want, "OK" if ok else "FAIL"))
    if not ok:
        fails.append(name)


print("== 1. channel construction against closed-form answers ==")
n = 64
px_m = 1.0
ii, jj = np.mgrid[0:n, 0:n].astype("float32")

flat = np.full((n, n), 100.0, dtype="float32")
dem1 = w6.build_channels(flat, px_m, "dem")
check("dem mode -> 1 channel", dem1.shape[0], 1)
check("dem mode is standardised (median 0)", float(np.median(dem1[0])), 0.0, 1e-6)

ch3 = w6.build_channels(flat, px_m, "dem+slope+shade")
check("3-channel mode -> 3 channels", ch3.shape[0], 3)
check("flat ground slope channel", float(np.mean(ch3[1])), 0.0, 1e-6)
check("flat ground hillshade = (sin45+1)/2",
      float(np.mean(ch3[2])), (math.sin(math.radians(45.0)) + 1.0) / 2.0, 1e-6)

a = 0.5
plane = (a * jj).astype("float32")
chp = w6.build_channels(plane, px_m, "dem+slope+shade")
want_slope = math.degrees(math.atan(a)) / 45.0
check("tilted plane slope channel (interior)",
      float(np.median(chp[1])), want_slope, 1e-5)
check("tilted plane dem channel median", float(np.median(chp[0])), 0.0, 1e-6)

chp2 = w6.build_channels(plane, 2.0 * px_m, "dem+slope")
want_slope2 = math.degrees(math.atan(a / 2.0)) / 45.0
check("pixel size enters the slope", float(np.median(chp2[1])), want_slope2, 1e-5)

print("")
print("== 2. augmentation keeps (C, H, W) and keeps x aligned with the label ==")
np.random.seed(0)
patch = (ii * 100.0 + jj).astype("float32")
lab = np.zeros((n, n), dtype="float32")
lab[: n // 2, :] = 1.0
for cin, mode in ((1, "dem"), (2, "dem+slope"), (3, "dem+slope+shade")):
    x = np.stack([lab] * cin).astype("float32")
    if cin > 1:
        x[1:] = patch[None, :, :]
    bad_shape = 0
    misaligned = 0
    for _ in range(30):
        xa, la = w6.augment_tile(x, lab, np.random)
        if xa.shape != (cin, n, n):
            bad_shape += 1
        if not np.array_equal(xa[0], la):
            misaligned += 1
    check("{} channels: shape preserved in 30 draws".format(cin), bad_shape, 0)
    check("{} channels: x stays aligned with y".format(cin), misaligned, 0)

print("")
print("== 3. the network grows by 144 weights per input channel ==")
n1 = sum(p.numel() for p in w6.UNet(1, 16).parameters())
n2 = sum(p.numel() for p in w6.UNet(2, 16).parameters())
n3 = sum(p.numel() for p in w6.UNet(3, 16).parameters())
check("UNet(1) parameter count", n1, 1286417, 0)
check("extra weights for channel 2", n2 - n1, 16 * 3 * 3, 0)
check("extra weights for channel 3", n3 - n2, 16 * 3 * 3, 0)

print("")
print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
raise SystemExit(0 if not fails else 1)
