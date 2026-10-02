#!/usr/bin/env python3
"""Week 6.6: list the false positives and the misses for manual inspection.

A detection-level precision of 0.451 only says "45 % of our detections match a
Robbins crater".  It cannot say whether the remaining 55 % are *wrong* or just
*missing from the catalogue* - that judgement needs a human looking at the
terrain.  This script produces the smallest possible set of things to look at:

  outputs/week6/review_false_positives.csv   every spurious detection
  outputs/week6/review_misses.csv            every known crater we missed
  outputs/week6/review_fp_map.png            quick-look over the study-area DEM

Usage
  python scripts/week6_review_false_positives.py               # everything
  python scripts/week6_review_false_positives.py --bin 1 2     # only 1-2 km
  python scripts/week6_review_false_positives.py --top 20      # 20 biggest only
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402
from osgeo import gdal  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week6_mask_to_catalog as mtc  # noqa: E402

W6 = REPO / "outputs" / "week6"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
MOON_M_PER_DEG = 30320.0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", nargs=2, type=float, metavar=("LO", "HI"),
                    help="only review detections in this diameter range (km)")
    ap.add_argument("--top", type=int, default=0,
                    help="only the N largest spurious detections")
    ap.add_argument("--random", type=int, default=0,
                    help="sample N spurious detections UNIFORMLY AT RANDOM; "
                         "only a random sample can correct the precision")
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for --random, so the sample is reproducible")
    ap.add_argument("--misses", type=int, default=0,
                    help="sample N *missed* craters (false negatives) uniformly at "
                         "random, to estimate the detectable recall")
    ap.add_argument("--force", action="store_true",
                    help="overwrite a review file that already contains verdicts")
    ap.add_argument("--summarise", action="store_true",
                    help="read the filled-in verdicts and report the corrected "
                         "precision with a Wilson interval")
    ap.add_argument("--mask", default=str(mtc.MASK),
                    help="predicted mask to review")
    args = ap.parse_args(argv[1:])

    if args.summarise:
        return summarise(args)

    mask, gt, ds = mtc.load_mask() if args.mask == str(mtc.MASK) else _load(args.mask)
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    print("=== predicted mask: {} x {}, {:.2f} % coverage".format(
        mask.shape[1], mask.shape[0], 100.0 * mask.mean()))

    dets_raw, _ = mtc.components(mask, gt)
    dets = [d for d in dets_raw if d["diam_km"] >= mtc.MIN_DET_KM]
    gts = mtc.read_gt(mtc.GT)
    tp, fp, fn = mtc.match(dets, gts)
    print("  detections {:,} (>= {:.1f} km), truth {:,}, matched {:,}".format(
        len(dets), mtc.MIN_DET_KM, len(gts), len(tp)))

    if args.bin:
        lo, hi = args.bin
        fp = [d for d in fp if lo <= d["diam_km"] < hi]
        fn = [g for g in fn if lo <= g["diam_km"] < hi]
    fp = sorted(fp, key=lambda d: -d["area_px"])
    if args.top:
        fp = fp[: args.top]
    if args.random:
        rng = np.random.default_rng(args.seed)
        k = min(args.random, len(fp))
        idx = rng.choice(len(fp), size=k, replace=False)
        fp = [fp[i] for i in sorted(idx)]
        print("  UNIFORM RANDOM sample: {:,} of the spurious detections (seed {})".format(k, args.seed))
        print("    -> random, so the share you judge to be real craters can be")
        print("       used to correct the precision (see --summarise)")

    fp_path = W6 / "review_false_positives.csv"
    wrote_fp = False
    if not (args.top or args.random or args.force):
        print("  (no --random / --top given: leaving {} untouched)".format(fp_path.name))
    elif has_verdicts(fp_path) and not args.force:
        print("  ! {} already contains verdicts - refusing to overwrite it "
              "(use --force to reset)".format(fp_path.name))
    else:
        # utf-8-sig: Excel on Chinese Windows reads (and re-saves) this correctly
        # instead of treating the file as ANSI and mangling the notes column
        with fp_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["rank", "lon", "lat", "diam_km", "area_px",
                        "verdict", "note"])
            for i, d in enumerate(fp, 1):
                # verdict / note are left blank for the human reviewer
                w.writerow([i, round(d["lon"], 5), round(d["lat"], 5),
                            round(d["diam_km"], 3), d["area_px"], "", ""])
        wrote_fp = True
        print("  wrote {} ({:,} rows to review)".format(fp_path, len(fp)))

    miss_path = W6 / "review_misses.csv"
    wrote_miss = []
    if args.misses or args.force:
        all_path = W6 / "review_misses_all.csv"
        with all_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["lon", "lat", "diam_km"])
            for g in sorted(fn, key=lambda g: -g["diam_km"]):
                w.writerow([round(g["lon"], 5), round(g["lat"], 5),
                            round(g["diam_km"], 3)])
        k = min(args.misses, len(fn)) if args.misses else len(fn)
        # a different random stream from the false-positive draw
        rng = np.random.default_rng(args.seed + 1)
        idx = rng.choice(len(fn), size=k, replace=False) if k else []
        sample = sorted((fn[i] for i in idx), key=lambda g: -g["diam_km"])
        rows = []
        for i, g in enumerate(sample, 1):
            here = {"lat": g["lat"], "lon": g["lon"]}
            near = min(dets, key=lambda d: mtc.centre_distance_km(d, here)) if dets else None
            dist = mtc.centre_distance_km(near, here) if near else None
            blob = any(mtc.centre_distance_km(d, here) < 0.5 * g["diam_km"]
                       for d in dets_raw)
            rows.append([i, round(g["lon"], 5), round(g["lat"], 5),
                         round(g["diam_km"], 3),
                         round(dist, 2) if dist is not None else "",
                         round(near["diam_km"], 2) if near else "",
                         "yes" if blob else "no", "", ""])
        if has_verdicts(miss_path) and not args.force:
            print("  ! {} already contains verdicts - refusing to overwrite it "
                  "(use --force to reset)".format(miss_path.name))
        else:
            with miss_path.open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["rank", "lon", "lat", "diam_km", "nearest_det_km",
                            "nearest_det_diam_km", "blob_inside", "verdict", "note"])
                w.writerows(rows)
            wrote_miss = sample
            print("  UNIFORM RANDOM sample of {:,} of the {:,} missed craters "
                  "(seed {})".format(k, len(fn), args.seed + 1))
            print("    wrote {} - fill the verdict column with".format(miss_path))
            print("      detectable     = the rim is visible, the model should have found it")
            print("      not_detectable = too degraded / buried / at the edge for 59 m/px")
            print("      unclear        = cannot decide")
            print("    blob_inside=yes means the model did fire inside this crater but the")
            print("    blob was dropped by the >= {:.1f} km size rule".format(mtc.MIN_DET_KM))
        print("    (full list of {:,} misses kept as {})".format(len(fn), all_path.name))
    else:
        print("  (no --misses given: leaving {} untouched)".format(miss_path.name))

    if STUDY_DEM.exists():
        dem_ds = gdal.Open(str(STUDY_DEM))
        z = dem_ds.GetRasterBand(1).ReadAsArray().astype("float32")
        dgt = dem_ds.GetGeoTransform()
        fig, ax = plt.subplots(figsize=(11, 9))
        ax.imshow(z, cmap="gray", origin="upper",
                  extent=(dgt[0], dgt[0] + dgt[1] * z.shape[1],
                          dgt[3] + dgt[5] * z.shape[0], dgt[3]))
        for g in gts:
            ax.add_patch(Circle((g["lon"], g["lat"]), g["diam_km"] / 111.0,
                                fill=False, ec="#39ff14", lw=0.7))
        n_mark = 0
        if wrote_fp and fp:
            ax.scatter([d["lon"] for d in fp], [d["lat"] for d in fp],
                       s=14, c="red", marker="x", label="spurious detection")
            n_mark += 1
        if wrote_miss:
            ax.scatter([g["lon"] for g in wrote_miss], [g["lat"] for g in wrote_miss],
                       s=44, facecolors="none", edgecolors="orange",
                       label="missed crater (sample)")
            n_mark += 1
        ax.set_xlabel("longitude (deg E)")
        ax.set_ylabel("latitude (deg N)")
        ax.set_title("Review sample (green = Robbins truth)")
        if n_mark:
            ax.legend(loc="upper right")
        fig.tight_layout()
        out_png = W6 / ("review_fp_map.png" if wrote_fp else "review_miss_map.png")
        fig.savefig(out_png, dpi=150)
        print("  wrote {}".format(out_png))
    else:
        print("  (no study DEM at {} - skipped the quick-look map)".format(STUDY_DEM))
    return 0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (better than normal approx)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / d, (centre + half) / d


def read_review(path):
    """Read the review CSV, trying UTF-8 first and falling back to GB18030.

    Spreadsheets on Chinese Windows still save as GBK/GB18030 by default, and
    the notes column is where all the scientific reasoning lives, so decode it
    properly instead of crashing (or silently producing mojibake).
    """
    last = None
    for enc in ("utf-8-sig", "gb18030", "cp1252"):
        try:
            with path.open(newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as exc:
            last = exc
    raise SystemExit("cannot decode {}: {}".format(path, last))


def summarise(args) -> int:
    """Turn the filled-in verdicts into a corrected precision for the catalogue."""
    path = W6 / "review_false_positives.csv"
    if not path.exists():
        raise SystemExit("no {} - run the review step first".format(path))
    rows = read_review(path)
    counts = {"true_crater": 0, "not_crater": 0, "unclear": 0, "": 0}
    for r in rows:
        v = (r.get("verdict") or "").strip().lower()
        # In this table every row is a *spurious* detection, so "TP" means
        # "this one is actually a real crater Robbins missed" and "FP" means
        # "genuinely not a crater".
        if v in ("true_crater", "true", "t", "tp", "yes", "y", "1",
                 "\u771f\u5751", "\u662f\u5751"):
            counts["true_crater"] += 1
        elif v in ("not_crater", "false", "f", "fp", "no", "n", "0",
                   "\u975e\u5751", "\u5047"):
            counts["not_crater"] += 1
        elif v in ("unclear", "?", "u", "\u4e0d\u786e\u5b9a"):
            counts["unclear"] += 1
        else:
            counts[""] += 1

    a, b, c = counts["true_crater"], counts["not_crater"], counts["unclear"]
    n = a + b + c
    print("=== manual review summary ===")
    print("  (TP/true_crater = a real crater that Robbins missed;")
    print("   FP/not_crater  = genuinely spurious)")
    print("  reviewed        : {:,}  (unfilled: {:,})".format(n, counts[""]))
    print("  true crater     : {:,}".format(a))
    print("  not a crater    : {:,}".format(b))
    print("  unclear         : {:,}".format(c))
    if n == 0:
        raise SystemExit("nothing filled in yet - put true_crater / not_crater / "
                         "unclear in the verdict column")
    p = a / n
    lo, hi = wilson(a, n)
    print("  share of spurious detections that are really craters: {:.3f}".format(p))
    print("  95 % Wilson interval for that share: [{:.3f}, {:.3f}]".format(lo, hi))

    metrics = W6 / "catalog_metrics.csv"
    with metrics.open(newline="") as f:
        metric_rows = list(csv.DictReader(f))
    allrow = next(r for r in metric_rows if r["scope"] == "all")
    n_det, n_tp, n_fp = int(allrow["n_det"]), int(allrow["n_tp"]), int(allrow["n_fp"])
    n_fn = int(allrow["n_fn"])
    print("")
    print("=== corrected catalogue quality ===")
    print("  reported  precision {:.3f}  (against the Robbins catalogue)".format(
        n_tp / n_det))
    print("  corrected precision {:.3f} .. {:.3f}  (Robbins misses included)".format(
        (n_tp + n_fp * lo) / n_det, (n_tp + n_fp * hi) / n_det))
    print("")
    print("  reading: the {:,} 'spurious' detections are not all wrong - if {:.0%} of"
          .format(n_fp, p))
    print("  them are genuine craters the catalogue missed, the real precision is")
    print("  about {:.0%} rather than {:.0%}.".format(
        (n_tp + n_fp * p) / n_det, n_tp / n_det))
    print("  Recall against Robbins ({:,}/{}, {:.0%}) is unchanged: those craters"
          .format(n_tp, n_tp + n_fn, n_tp / (n_tp + n_fn)))
    print("  simply absent from the reference catalogue used to score the model.")

    # A detection you called "a real crater" can mean two different things:
    #   (a) it sits on a crater Robbins already lists -> duplicate / partial
    #       detection of a known crater (no new information)
    #   (b) it sits on a crater Robbins does not have at all -> a genuine
    #       omission in the reference catalogue
    # Only (b) justifies the "the catalogue is incomplete" conclusion.
    gts = mtc.read_gt(mtc.GT)
    mask, gt, _ds = mtc.load_mask()
    dets_raw, _ = mtc.components(mask, gt)
    dets = [d for d in dets_raw if d["diam_km"] >= mtc.MIN_DET_KM]
    tp_pairs, _fp, _fn = mtc.match(dets, gts)
    matched_ids = {id(g) for g, _d, _dist in tp_pairs}

    dup = new = outside = 0
    for r in rows:
        if norm_verdict(r) != "true":
            continue
        here = {"lat": float(r["lat"]), "lon": float(r["lon"])}
        near = min(gts, key=lambda g: mtc.centre_distance_km(g, here))
        dist = mtc.centre_distance_km(near, here)
        if dist < 0.5 * near["diam_km"]:
            if id(near) in matched_ids:
                dup += 1
            else:
                outside += 1
        else:
            new += 1
    print("")
    print("=== what those 'real crater' detections actually are ===")
    print("  inside a crater Robbins already lists (duplicate / partial): {:,}".format(dup))
    print("  inside a crater Robbins lists but the model missed          : {:,}".format(outside))
    print("  on a crater Robbins does not have at all                    : {:,}".format(new))
    print("  -> only the last group is evidence of catalogue incompleteness")

    print("")
    print("=== correction by detection diameter ===")
    print("  {:>9} {:>5} {:>5} {:>7} {:>11} {:>11}".format(
        "det diam", "n", "real", "share", "P reported", "P corrected"))
    for lo, hi in ((1.0, 2.0), (2.0, 5.0), (5.0, 100.0)):
        sel = [norm_verdict(r) for r in rows
               if lo <= float(r["diam_km"]) < hi]
        sel = [v for v in sel if v in ("true", "false")]
        label = "{:.0f}-{:.0f}".format(lo, hi)
        row_m = next((r for r in metric_rows if r["scope"] == label), None)
        if not sel or row_m is None:
            print("  {:>9} {:>5} {:>5} {:>7} {:>11} {:>11}".format(
                label, len(sel), "-", "-", "-", "no sample"))
            continue
        k, n_bin = sel.count("true"), len(sel)
        share = k / n_bin
        tp_b, fp_b = int(row_m["n_tp"]), int(row_m["n_fp"])
        p_rep = tp_b / (tp_b + fp_b)
        p_cor = (tp_b + fp_b * share) / (tp_b + fp_b)
        lo_w, hi_w = wilson(k, n_bin)
        p_lo = (tp_b + fp_b * lo_w) / (tp_b + fp_b)
        p_hi = (tp_b + fp_b * hi_w) / (tp_b + fp_b)
        print("  {:>9} {:>5} {:>5} {:>7.2f} {:>11.3f} {:>6.3f} [{:.2f}, {:.2f}]".format(
            label, n_bin, k, share, p_rep, p_cor, p_lo, p_hi))

    extra = summarise_misses(n_tp, n_fn)
    if extra:
        print(extra)
    return 0


def summarise_misses(n_tp: int, n_fn: int) -> str:
    """Estimate how many of the missed craters were detectable at all.

    The reported recall (TP / (TP + FN)) treats every Robbins crater we did not
    detect as a failure.  Some of them cannot be identified at 59 m/px (buried,
    degraded, clipped by the scene edge), so a random sample of the misses gives
    a fairer denominator: the *detectable* recall.
    """
    path = W6 / "review_misses.csv"
    if not path.exists():
        return ""
    rows = read_review(path)
    det = notdet = unc = unf = 0
    for r in rows:
        v = norm_verdict_miss(r)
        if v == "detectable":
            det += 1
        elif v == "not_detectable":
            notdet += 1
        elif v == "unclear":
            unc += 1
        else:
            unf += 1
    n = det + notdet + unc
    if n == 0:
        return ("\n=== missed craters (false negatives) ===\n"
                "  {:,} rows waiting for a verdict in {} - fill the verdict column\n"
                "  (detectable / not_detectable / unclear) and run --summarise again"
                .format(len(rows), path.name))
    q = det / n
    q_lo, q_hi = wilson(det, n)
    return "\n".join([
        "", "=== missed craters (false negatives) ===",
        "  reviewed        : {:,} of {:,} misses (unfilled: {:,})".format(n, n_fn, unf),
        "  detectable      : {:,}".format(det),
        "  not detectable  : {:,}".format(notdet),
        "  unclear         : {:,}".format(unc),
        "  share of the misses that were detectable: {:.3f}  [{:.3f}, {:.3f}]".format(
            q, q_lo, q_hi),
        "  recall vs the Robbins catalogue : {:.3f}".format(n_tp / (n_tp + n_fn)),
        "  detectable recall               : {:.3f}  [{:.3f}, {:.3f}]".format(
            n_tp / (n_tp + n_fn * q), n_tp / (n_tp + n_fn * q_hi),
            n_tp / (n_tp + n_fn * q_lo)),
        "  (the interval runs backwards: a larger share of detectable misses "
        "means a lower recall)",
    ])


def has_verdicts(path) -> bool:
    """True if a review file already carries at least one filled verdict."""
    p = Path(path)
    if not p.exists():
        return False
    try:
        rows = read_review(p)
    except SystemExit:
        return True          # unreadable: be safe and treat it as filled
    if not rows:
        return False
    if "verdict" in rows[0]:
        return any((r.get("verdict") or "").strip() for r in rows)
    return any((r.get("reason") or "").strip() for r in rows)


def norm_verdict_miss(row) -> str:
    """Map a misses verdict cell to detectable / not_detectable / unclear / ''."""
    v = (row.get("verdict") or "").strip().lower()
    if v in ("detectable", "det", "yes", "y", "1", "tp",
             "\u53ef\u63a2\u6d4b", "\u80fd\u63a2\u6d4b"):
        return "detectable"
    if v in ("not_detectable", "undetectable", "no", "n", "0", "fp",
             "\u4e0d\u53ef\u63a2\u6d4b", "\u65e0\u6cd5\u63a2\u6d4b"):
        return "not_detectable"
    if v in ("unclear", "?", "u", "\u4e0d\u786e\u5b9a"):
        return "unclear"
    return ""


def norm_verdict(row) -> str:
    """Map the free-text verdict cell to true / false / unclear / ''."""
    v = (row.get("verdict") or "").strip().lower()
    if v in ("true_crater", "true", "t", "tp", "yes", "y", "1",
             "\u771f\u5751", "\u662f\u5751"):
        return "true"
    if v in ("not_crater", "false", "f", "fp", "no", "n", "0",
             "\u975e\u5751", "\u5047"):
        return "false"
    if v in ("unclear", "?", "u", "\u4e0d\u786e\u5b9a"):
        return "unclear"
    return ""


def _load(path: str):
    """Open a raster as a 0/1 uint8 mask."""
    ds = gdal.Open(path)
    if ds is None:
        raise SystemExit("cannot open {}".format(path))
    return (ds.GetRasterBand(1).ReadAsArray() > 0).astype(np.uint8), ds.GetGeoTransform(), ds


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
