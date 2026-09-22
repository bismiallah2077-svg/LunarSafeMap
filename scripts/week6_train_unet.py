#!/usr/bin/env python3
"""Week 6.2: U-Net crater segmentation baseline (PyTorch, CPU friendly).

Data
  input  : SLDEM elevation windows (the same 512 ppd product used in weeks 4-5)
  target : Robbins (2018) crater discs with diameter >= MIN_DIAM_KM

Split (geographic, no random tile shuffling across regions)
  train / val : inside the training box 340-360E, 0-20N, excluding the study
                area, split into a western and an eastern half by longitude
  test        : the Rimae Bode study area 353-359E, 8-13N (never seen in training)

Outputs (outputs/week6/): unet_craters.pt, metrics.csv, predictions on the study
area (GeoTIFF), and the training log printed to stdout.

Usage
  python scripts/week6_train_unet.py --selftest          # model sanity check
  python scripts/week6_train_unet.py --epochs 12         # real run
  python scripts/week6_train_unet.py --quick             # tiny smoke run
"""
import argparse
import csv
import math
import sys
import time
from pathlib import Path

import numpy as np
from osgeo import gdal

import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from week6_build_crater_labels import crater_disc_mask, MOON_M_PER_DEG  # noqa: E402

gdal.UseExceptions()

W4 = REPO / "outputs" / "week4"
W6 = REPO / "outputs" / "week6"
INTERIM = REPO / "data" / "interim" / "week6"
SLDEM_VRT = REPO / "data" / "interim" / "week4" / \
    "SLDEM2015_512_00N_30N_315_360_FLOAT.vrt"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"

STUDY = (353.0, 8.0, 359.0, 13.0)        # west, south, east, north
TRAIN_BOX = (340.0, 0.0, 360.0, 20.0)
TILE = 256
MIN_DIAM_KM = 1.0
MAX_DIAM_KM = 7.0         # keep craters whose rim fits inside a 15 km tile
POS_WEIGHT = 1.0          # the crater class is ~10-20 % of a tile, not rare
PX_DEG = 1.0 / 512.0
KM_TO_M = 1000.0          # the SLDEM VRT stores kilometres


def read_craters(path, min_diam=MIN_DIAM_KM, max_diam=MAX_DIAM_KM):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                lat, lon, d = float(row["lat"]), float(row["lon"]), float(row["diameter_km"])
            except (KeyError, ValueError):
                continue
            if min_diam <= d <= max_diam:
                out.append((lat, lon, d))
    return out


def tile_grid(box, tile_px=TILE):
    """List of (row0, col0, lat_min, lat_max, lon_min, lon_max) for a lat/lon box.

    The grid is defined on the SLDEM 512 ppd raster, so tiles are exact
    multiples of a pixel; the box is snapped outwards.
    """
    w, s, e, n = box
    lon0 = math.floor(w / PX_DEG) * PX_DEG
    lon1 = math.ceil(e / PX_DEG) * PX_DEG
    lat0 = math.floor(s / PX_DEG) * PX_DEG
    lat1 = math.ceil(n / PX_DEG) * PX_DEG
    ncols = int(round((lon1 - lon0) / PX_DEG))
    nrows = int(round((lat1 - lat0) / PX_DEG))
    out = []
    for r in range(0, nrows - tile_px + 1, tile_px):
        for c in range(0, ncols - tile_px + 1, tile_px):
            t_lon0 = lon0 + c * PX_DEG
            t_lon1 = t_lon0 + tile_px * PX_DEG
            t_lat1 = lat1 - r * PX_DEG
            t_lat0 = t_lat1 - tile_px * PX_DEG
            out.append((r, c, t_lat0, t_lat1, t_lon0, t_lon1))
    return out, (lat0, lat1, lon0, lon1)


def lonlat_to_window(gt, lat0, lat1, lon0, lon1, tile_px=TILE, size=None):
    """Pixel window for a tile whose top-left corner is (lon0, lat1).

    The tile grid is aligned to the 512 ppd raster, so the offsets are exact
    integers; floor/ceil would produce a 257 pixel window and read past the
    raster edge.  The window is clamped to the raster and may therefore be
    smaller than tile_px near the border (the caller pads).
    """
    x0 = int(round((lon0 - gt[0]) / gt[1]))
    y0 = int(round((lat1 - gt[3]) / gt[5]))
    w = h = tile_px
    if size is not None:
        nx, ny = size
        x0 = max(0, min(x0, nx - 1))
        y0 = max(0, min(y0, ny - 1))
        w = max(1, min(tile_px, nx - x0))
        h = max(1, min(tile_px, ny - y0))
    return x0, y0, w, h


def box_overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


class DoubleConv(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):
    """Compact U-Net: 4 downsampling levels, base channels configurable."""

    def __init__(self, cin=1, base=16):
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.d1 = DoubleConv(cin, base)
        self.d2 = DoubleConv(base, base * 2)
        self.d3 = DoubleConv(base * 2, base * 4)
        self.d4 = DoubleConv(base * 4, base * 8)
        self.bottleneck = DoubleConv(base * 8, base * 8)
        self.u4 = nn.ConvTranspose2d(base * 8, base * 8, 2, stride=2)
        self.c4 = DoubleConv(base * 16, base * 8)
        self.u3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.c3 = DoubleConv(base * 8, base * 4)
        self.u2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.c2 = DoubleConv(base * 4, base * 2)
        self.u1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.c1 = DoubleConv(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, x):
        s1 = self.d1(x)
        s2 = self.d2(self.pool(s1))
        s3 = self.d3(self.pool(s2))
        s4 = self.d4(self.pool(s3))
        b = self.bottleneck(self.pool(s4))
        x = self.c4(torch.cat([self.u4(b), s4], dim=1))
        x = self.c3(torch.cat([self.u3(x), s3], dim=1))
        x = self.c2(torch.cat([self.u2(x), s2], dim=1))
        x = self.c1(torch.cat([self.u1(x), s1], dim=1))
        return self.out(x)


def dice_loss(logits, target):
    """Soft dice on probabilities."""
    p = torch.sigmoid(logits)
    num = 2.0 * (p * target).sum(dim=(1, 2, 3)) + 1.0
    den = p.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3)) + 1.0
    return 1.0 - (num / den).mean()


class CraterTiles(torch.utils.data.Dataset):
    """Reads DEM windows on demand and rasterises the crater labels."""

    def __init__(self, ds, gt, tiles, craters, mean, std, augment=False,
                 scale_to_m=KM_TO_M, mode="pertile", channels="dem"):
        self.scale_to_m = scale_to_m
        self.mode = mode
        self.channels = channels
        self.px_m = abs(gt[1]) * MOON_M_PER_DEG
        self.ds = ds
        self.gt = gt
        self.tiles = tiles
        self.mean = mean
        self.std = std
        self.augment = augment
        self.windows = [lonlat_to_window(gt, t[2], t[3], t[4], t[5],
                                         size=(ds.RasterXSize, ds.RasterYSize))
                        for t in tiles]
        # craters near each tile (with a margin of one crater radius)
        self.local = []
        for (r, c, lat0, lat1, lon0, lon1) in tiles:
            sel = []
            for (clat, clon, cd) in craters:
                rad = cd * 1000.0 / MOON_M_PER_DEG
                if (lat0 - rad <= clat <= lat1 + rad) and (lon0 - rad * 2 <= clon <= lon1 + rad * 2):
                    sel.append((clat, clon, cd))
            self.local.append(sel)

    def __len__(self):
        return len(self.tiles)

    def tile_gt(self, i):
        _, _, lat0, lat1, lon0, lon1 = self.tiles[i]
        return (lon0 - PX_DEG / 2, PX_DEG, 0.0, lat1 + PX_DEG / 2, 0.0, -PX_DEG)

    def __getitem__(self, i):
        x0, y0, w, h = self.windows[i]
        arr = self.ds.ReadAsArray(x0, y0, w, h).astype("float32") * self.scale_to_m
        z = np.full((TILE, TILE), np.nan, dtype="float32")
        hh, ww = min(h, TILE), min(w, TILE)
        z[:hh, :ww] = arr[:hh, :ww]
        lab = crater_disc_mask((TILE, TILE), self.tile_gt(i), self.local[i])
        x = build_channels(z, self.px_m, self.channels, self.mean, self.std)
        if self.augment:
            x, lab = augment_tile(x, lab, np.random)
        return (torch.from_numpy(x.astype("float32")),
                torch.from_numpy(lab[None, :, :].astype("float32")))


def metrics_from_counts(tp, fp, fn):
    eps = 1e-9
    prec = tp / (tp + fp + eps)
    rec = tp / (tp + fn + eps)
    f1 = 2 * prec * rec / (prec + rec + eps)
    iou = tp / (tp + fp + fn + eps)
    return {"precision": prec, "recall": rec, "f1": f1, "iou": iou}


def tile_box(t):
    _, _, lat0, lat1, lon0, lon1 = t
    return (lon0, lat0, lon1, lat1)


def build_tile_lists(craters, train_lat_split=14.0, negatives_ratio=0.5, seed=0,
                     limit=None):
    """Positives = tiles with a crater centre; negatives = empty tiles.

    Geographic split inside the training box: tiles south of train_lat_split
    are the training set, tiles to the north are the validation set.  Tiles
    overlapping the study area are dropped from both.
    """
    rng = np.random.default_rng(seed)
    tiles, bounds = tile_grid(TRAIN_BOX)
    pos_all, neg_all = [], []
    for t in tiles:
        bx = tile_box(t)
        if box_overlaps(bx, STUDY):
            continue
        hit = any((bx[1] <= clat <= bx[3]) and (bx[0] <= clon <= bx[2])
                  for (clat, clon, _d) in craters)
        (pos_all if hit else neg_all).append(t)
    if limit and len(pos_all) > limit:
        # sample randomly, not the first N: tile_grid runs north to south, so
        # truncating would put nearly everything into the northern validation band
        idx = rng.choice(len(pos_all), size=limit, replace=False)
        pos_all = [pos_all[i] for i in sorted(idx)]
    n_neg = int(negatives_ratio * len(pos_all))
    if n_neg and len(neg_all) > n_neg:
        idx = rng.choice(len(neg_all), size=n_neg, replace=False)
        neg_all = [neg_all[i] for i in sorted(idx)]
    train_tiles = [t for t in pos_all + neg_all if t[2] < train_lat_split]
    val_tiles = [t for t in pos_all + neg_all if t[2] >= train_lat_split]
    return train_tiles, val_tiles, pos_all, neg_all, bounds


CHANNEL_SETS = {"dem": 1, "dem+slope": 2, "dem+slope+shade": 3}


def build_channels(z, px_m, channels="dem", mean=0.0, std=1.0):
    """Stack the input channels for one tile (C, H, W).

    dem   : per-tile standardised elevation
    slope : terrain slope in degrees, scaled to ~[0, 1] by 45 deg
    shade : hillshade with a fixed sun (azimuth 315, elevation 45), [0, 1]
    """
    zf = np.nan_to_num(z, nan=mean)
    ch = [normalise(zf, "pertile", mean, std)]
    if channels in ("dem+slope", "dem+slope+shade"):
        gy, gx = np.gradient(zf)
        slope_deg = np.degrees(np.arctan(np.hypot(gx, gy) / px_m))
        ch.append((slope_deg / 45.0).clip(0, 1).astype("float32"))
    if channels == "dem+slope+shade":
        az, alt = math.radians(315.0), math.radians(45.0)
        sl = np.arctan(np.hypot(gx, gy) / px_m)
        asp = np.arctan2(-gx, gy)
        shade = (math.sin(alt) * np.cos(sl)
                 + math.cos(alt) * np.sin(sl) * np.cos(az - asp))
        ch.append(((shade + 1.0) / 2.0).clip(0, 1).astype("float32"))
    return np.stack(ch).astype("float32")


def augment_tile(x, lab, rng=np.random):
    """Random 90 deg rotation + optional horizontal flip of a single tile.

    x is (C, H, W) and lab is (H, W).  Only the two *spatial* axes are
    transformed: rotating axes 0/1 of a multi-channel tile would mix the
    channel axis with the row axis and silently destroy the sample (a
    1-channel tile becomes 256x1x256).  Keeping this in its own function
    means the regression test can call it directly.
    """
    k = int(rng.randint(4))
    x = np.rot90(x, k, axes=(1, 2)).copy()
    lab = np.rot90(lab, k).copy()
    if rng.rand() < 0.5:
        x = x[:, :, ::-1].copy()
        lab = lab[:, ::-1].copy()
    return x, lab


def normalise(z, mode="pertile", mean=0.0, std=1.0):
    """Per-tile robust standardisation (the crater signal is local morphology)."""
    if mode == "pertile":
        med = float(np.nanmedian(z))
        iqr = float(np.nanpercentile(z, 75) - np.nanpercentile(z, 25))
        s = iqr / 1.349 if iqr > 0 else (float(np.nanstd(z)) or 1.0)
        return (z - med) / s
    return (z - mean) / std


def estimate_normalisation(ds, gt, tiles, n_sample=60, seed=1):
    """Robust elevation scale from a sample of training windows."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(tiles), size=min(n_sample, len(tiles)), replace=False)
    vals = []
    for i in idx:
        x0, y0, w, h = lonlat_to_window(gt, tiles[i][2], tiles[i][3],
                                        tiles[i][4], tiles[i][5],
                                        size=(ds.RasterXSize, ds.RasterYSize))
        a = ds.ReadAsArray(x0, y0, w, h).astype("float32") * KM_TO_M
        a = a[np.isfinite(a)]
        if a.size:
            vals.append(a)
    if not vals:
        return 0.0, 1.0
    v = np.concatenate(vals)
    med = float(np.median(v))
    iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
    std = iqr / 1.349 if iqr > 0 else float(v.std() + 1e-6)
    return med, std


def run_epoch(model, loader, opt, device, train=True):
    model.train(train)
    total, n = 0.0, 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.set_grad_enabled(train):
            logits = model(x)
            bce = nn.functional.binary_cross_entropy_with_logits(
                logits, y, pos_weight=torch.tensor([POS_WEIGHT], device=device))
            loss = 0.5 * bce + 0.5 * dice_loss(logits, y)
            if train:
                opt.zero_grad()
                loss.backward()
                opt.step()
        total += float(loss.detach()) * x.shape[0]
        n += x.shape[0]
    return total / max(n, 1)


@torch.no_grad()
def evaluate(model, ds, gt, craters, tiles, mean, std, device, threshold=0.5,
             scale_to_m=KM_TO_M, mode="pertile", channels="dem"):
    """Accumulate TP/FP/FN over a set of tiles."""
    model.eval()
    tp = fp = fn = 0
    for (r, c, lat0, lat1, lon0, lon1) in tiles:
        x0, y0, w, h = lonlat_to_window(gt, lat0, lat1, lon0, lon1,
                                        size=(ds.RasterXSize, ds.RasterYSize))
        arr = ds.ReadAsArray(x0, y0, w, h).astype("float32") * scale_to_m
        z = np.full((TILE, TILE), np.nan, dtype="float32")
        z[:min(h, TILE), :min(w, TILE)] = arr[:TILE, :TILE]
        z = np.nan_to_num(z, nan=mean)
        tgt_gt = (lon0 - PX_DEG / 2, PX_DEG, 0.0, lat1 + PX_DEG / 2, 0.0, -PX_DEG)
        lab = crater_disc_mask((TILE, TILE), tgt_gt, craters)
        px_m = abs(gt[1]) * MOON_M_PER_DEG
        x = torch.from_numpy(build_channels(z, px_m, channels, mean, std)[None].astype("float32")).to(device)
        pred = (torch.sigmoid(model(x))[0, 0] > threshold).cpu().numpy()
        tp += int(((pred == 1) & (lab == 1)).sum())
        fp += int(((pred == 1) & (lab == 0)).sum())
        fn += int(((pred == 0) & (lab == 1)).sum())
    return metrics_from_counts(tp, fp, fn), {"tp": tp, "fp": fp, "fn": fn}


def predict_full_study(model, ds, gt, mean, std, device, out_tif, threshold=0.5,
                       scale_to_m=1.0, mode="pertile", channels="dem"):
    """Slide over the study-area raster and write the predicted mask."""
    ny, nx = ds.RasterYSize, ds.RasterXSize
    out = np.zeros((ny, nx), dtype=np.uint8)
    model.eval()
    with torch.no_grad():
        for r in range(0, ny, TILE):
            for c in range(0, nx, TILE):
                w = min(TILE, nx - c)
                h = min(TILE, ny - r)
                arr = ds.ReadAsArray(c, r, w, h).astype("float32") * scale_to_m
                z = np.full((TILE, TILE), mean, dtype="float32")
                z[:h, :w] = np.nan_to_num(arr, nan=mean)
                px_m = abs(gt[1]) * MOON_M_PER_DEG
                x = torch.from_numpy(build_channels(z, px_m, channels, mean, std)[None].astype("float32")).to(device)
                pred = (torch.sigmoid(model(x))[0, 0].cpu().numpy() > threshold)
                out[r:r + h, c:c + w] = pred[:h, :w].astype(np.uint8)
    drv = gdal.GetDriverByName("GTiff")
    ds_out = drv.Create(str(out_tif), nx, ny, 1, gdal.GDT_Byte,
                        options=["COMPRESS=DEFLATE"])
    ds_out.SetGeoTransform(gt)
    ds_out.SetProjection(ds.GetProjection())
    ds_out.GetRasterBand(1).WriteArray(out)
    ds_out = None
    return out


def selftest(args):
    print("=== model self test ===")
    cin = CHANNEL_SETS[getattr(args, "channels", "dem")]
    model = UNet(cin, args.base)
    nparam = sum(p.numel() for p in model.parameters())
    x = torch.randn(2, cin, TILE, TILE)
    target = torch.zeros(2, 1, TILE, TILE)
    t0 = time.time()
    y = model(x)
    loss = nn.functional.binary_cross_entropy_with_logits(y, target) + dice_loss(y, target)
    loss.backward()
    dt = time.time() - t0
    print("  parameters      : {:,}".format(nparam))
    print("  input shape     : {}".format(tuple(x.shape)))
    print("  output shape    : {}".format(tuple(y.shape)))
    print("  loss            : {:.4f}".format(float(loss)))
    print("  forward+backward : {:.2f} s for a batch of 2 tiles".format(dt))
    ok = tuple(y.shape) == (2, 1, TILE, TILE) and math.isfinite(float(loss))
    print("  RESULT          : {}".format("OK" if ok else "FAILED"))
    return 0 if ok else 1


def evaluate_checkpoint(args):
    """Load the saved weights and redo the evaluation + prediction only."""
    ckpt_path = W6 / "unet_craters.pt"
    if not ckpt_path.exists():
        raise SystemExit("no checkpoint at {}".format(ckpt_path))
    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    ch_mode = ckpt.get("channels", "dem")
    model = UNet(CHANNEL_SETS[ch_mode], ckpt.get("base", args.base))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    mean, std = ckpt["mean"], ckpt["std"]
    gdal.SetConfigOption("GDAL_VRT_RAWRASTERBAND_ALLOWED_SOURCE",
                         str((REPO / "data").resolve()))
    study_craters = read_craters(INTERIM / "craters_study_area.csv")
    study_ds = gdal.Open(str(STUDY_DEM))
    study_gt = study_ds.GetGeoTransform()
    study_tiles, _ = tile_grid(STUDY)
    print("=== evaluation from checkpoint (channels={}, {:,} study-area craters) ===".format(ch_mode, len(study_craters)))
    m, c = evaluate(model, study_ds, study_gt, study_craters, study_tiles, mean, std,
                    torch.device("cpu"), scale_to_m=1.0, channels=ch_mode)
    print("  TEST study area: IoU {:.3f}  P {:.3f}  R {:.3f}  F1 {:.3f}  (tp {} fp {} fn {})"
          .format(m["iou"], m["precision"], m["recall"], m["f1"], c["tp"], c["fp"], c["fn"]))
    mask = predict_full_study(model, study_ds, study_gt, mean, std, torch.device("cpu"),
                              W6 / "study_area_crater_pred.tif", channels=ch_mode)
    print("  predicted crater coverage: {:.2f} % of the study area".format(100.0 * mask.mean()))
    with (W6 / "metrics_test.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set", "iou", "precision", "recall", "f1", "tp", "fp", "fn", "coverage_pct"])
        w.writerow(["test_study_area", round(m["iou"], 4), round(m["precision"], 4),
                    round(m["recall"], 4), round(m["f1"], 4), c["tp"], c["fp"], c["fn"],
                    round(100.0 * float(mask.mean()), 2)])
    print("  wrote {}".format(W6 / "metrics_test.csv"))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--base", type=int, default=16, help="base channel width")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--limit", type=int, default=0, help="cap the number of tiles")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true", help="2 epochs on a small subset")
    ap.add_argument("--channels", default="dem",
                    choices=sorted(CHANNEL_SETS), help="input feature set")
    ap.add_argument("--tag", default="", help="suffix for the output files")
    ap.add_argument("--predict-only", action="store_true",
                    help="load outputs/week6/unet_craters.pt and only evaluate/predict")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args)
    if args.predict_only:
        return evaluate_checkpoint(args)
    if args.quick:
        args.epochs = 2
        args.limit = 60

    W6.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(0)
    np.random.seed(0)

    print("=== data ===")
    # the SLDEM VRT wraps a raw binary IMG; GDAL 4 restricts such references
    gdal.SetConfigOption("GDAL_VRT_RAWRASTERBAND_ALLOWED_SOURCE",
                         str((REPO / "data").resolve()))
    train_craters = read_craters(INTERIM / "craters_training_region.csv")
    study_craters = read_craters(INTERIM / "craters_study_area.csv")
    print("  training-region craters >= {:.1f} km : {:,}".format(MIN_DIAM_KM, len(train_craters)))
    print("  study-area craters     >= {:.1f} km : {:,}".format(MIN_DIAM_KM, len(study_craters)))

    ds = gdal.Open(str(SLDEM_VRT))
    gt = ds.GetGeoTransform()
    tiles, val_extra, pos, neg, bounds = build_tile_lists(
        train_craters, limit=(args.limit or None))
    print("  tiles in the training box: {} positive, {} negative".format(len(pos), len(neg)))
    print("  train tiles: {}   val tiles (north of 14N): {}".format(len(tiles), len(val_extra)))

    mean, std = estimate_normalisation(ds, gt, tiles)
    print("  normalisation: mean {:.1f} m, std {:.1f} m".format(mean, std))

    train_ds = CraterTiles(ds, gt, tiles, train_craters, mean, std, augment=True,
                           channels=args.channels)
    val_ds = CraterTiles(ds, gt, val_extra, train_craters, mean, std, augment=False,
                         channels=args.channels)
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=args.batch,
                                               shuffle=True, num_workers=0)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=args.batch,
                                             shuffle=False, num_workers=0)

    device = torch.device("cpu")
    cin = CHANNEL_SETS[args.channels]
    model = UNet(cin, args.base).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    print("")
    print("=== training ({:,} parameters, {} epochs) ===".format(
        sum(p.numel() for p in model.parameters()), args.epochs))
    history = []
    t_start = time.time()
    for ep in range(1, args.epochs + 1):
        tr = run_epoch(model, train_loader, opt, device, train=True)
        va = run_epoch(model, val_loader, opt, device, train=False)
        hist = {"epoch": ep, "train_loss": round(tr, 4), "val_loss": round(va, 4)}
        history.append(hist)
        print("  epoch {:2d}/{:2d}  train {:.4f}  val {:.4f}  ({:.0f} s elapsed)"
              .format(ep, args.epochs, tr, va, time.time() - t_start))
    ckpt = W6 / ("unet_craters" + (("_" + args.tag) if args.tag else "") + ".pt")
    torch.save({"state_dict": model.state_dict(), "mean": mean, "std": std,
                "base": args.base, "tile": TILE, "channels": args.channels}, str(ckpt))
    print("  saved {}".format(ckpt))

    print("")
    print("=== evaluation ===")
    rows = []
    if val_extra:
        m, c = evaluate(model, ds, gt, train_craters, val_extra, mean, std, device,
                        channels=args.channels)
        print("  validation (training box, north of 14N): IoU {:.3f}  P {:.3f}  R {:.3f}  F1 {:.3f}"
              .format(m["iou"], m["precision"], m["recall"], m["f1"]))
        rows.append({"set": "val_north_band", "n_tiles": len(val_extra), **{k: round(v, 4) for k, v in m.items()}, **c})
    study_ds = gdal.Open(str(STUDY_DEM))
    study_gt = study_ds.GetGeoTransform()
    study_tiles, _ = tile_grid(STUDY)
    m, c = evaluate(model, study_ds, study_gt, study_craters, study_tiles, mean, std,
                    device, scale_to_m=1.0, channels=args.channels)
    print("  TEST study area (Rimae Bode): IoU {:.3f}  P {:.3f}  R {:.3f}  F1 {:.3f}"
          .format(m["iou"], m["precision"], m["recall"], m["f1"]))
    rows.append({"set": "test_study_area", "n_tiles": len(study_tiles),
                 **{k: round(v, 4) for k, v in m.items()}, **c})
    if history:
        rows.append({"set": "train_history", "n_tiles": 0,
                     **{k: v for k, v in history[-1].items()}})

    with (W6 / ("metrics" + (("_" + args.tag) if args.tag else "") + ".csv")).open("w", newline="") as f:
        keys = sorted({k for r in rows for k in r})
        order = ["set", "n_tiles", "iou", "precision", "recall", "f1", "tp", "fp", "fn",
                 "epoch", "train_loss", "val_loss"]
        w = csv.DictWriter(f, fieldnames=[k for k in order if k in keys] +
                                        [k for k in keys if k not in order])
        w.writeheader()
        w.writerows(rows)
    print("  wrote {}".format(W6 / ("metrics" + (("_" + args.tag) if args.tag else "") + ".csv")))

    pred_tif = W6 / ("study_area_crater_pred" + (("_" + args.tag) if args.tag else "") + ".tif")
    mask = predict_full_study(model, study_ds, study_gt, mean, std, device, pred_tif,
                              channels=args.channels)
    print("  predicted mask coverage: {:.2f} % of the study area".format(100.0 * mask.mean()))
    print("  wrote {}".format(pred_tif))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
