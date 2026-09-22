#!/usr/bin/env python3
"""Week 6.5: collect the ablation runs into one table and one figure.

Each training run writes outputs/week6/metrics_<tag>.csv with three rows:
  val_north_band   training box north of 14 N - the model-development set
  test_study_area  Rimae Bode - never used for training or model selection
  train_history    final epoch losses
This script reads every tag, prints the two evaluation rows side by side and
writes outputs/week6/ablation_features.csv (+ a grouped bar chart).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
W6 = REPO / "outputs" / "week6"

PRETTY = {"dem": "DEM", "dslope": "DEM+slope", "dshade": "DEM+slope+shade"}
METRICS = ["iou", "precision", "recall", "f1"]


def read_run(tag: str) -> dict:
    """Return {'val': {...}, 'test': {...}, 'history': {...}} for one tag."""
    path = W6 / "metrics_{}.csv".format(tag)
    if not path.exists():
        raise SystemExit("missing {} - run week6_ablation.sh first".format(path))
    out = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            out[row["set"]] = row
    if "test_study_area" not in out:
        raise SystemExit("{} has no test_study_area row".format(path))
    return {"val": out.get("val_north_band", {}),
            "test": out["test_study_area"],
            "history": out.get("train_history", {})}


def main(argv: list[str]) -> int:
    tags = argv[1:] or ["dem", "dslope", "dshade"]
    runs = {t: read_run(t) for t in tags}
    base = runs[tags[0]]["test"]

    rows = []
    for tag in tags:
        r = runs[tag]
        row = {"run": tag, "channels": PRETTY.get(tag, tag)}
        for split in ("val", "test"):
            for m in METRICS:
                raw = r[split].get(m, "")
                row["{}_{}".format(split, m)] = round(float(raw), 4) if raw else ""
        row["test_f1_delta_vs_{}".format(tags[0])] = round(
            float(r["test"]["f1"]) - float(base["f1"]), 4)
        row["test_recall_delta_vs_{}".format(tags[0])] = round(
            float(r["test"]["recall"]) - float(base["recall"]), 4)
        for k in ("train_loss", "val_loss"):
            row[k] = r["history"].get(k, "")
        row["test_tp"] = r["test"].get("tp", "")
        row["test_fp"] = r["test"].get("fp", "")
        row["test_fn"] = r["test"].get("fn", "")
        rows.append(row)

    order = ["run", "channels", "test_iou", "test_precision", "test_recall", "test_f1"]
    order += [k for k in rows[0] if k not in order]
    out_csv = W6 / "ablation_features.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in order if k in rows[0]])
        w.writeheader()
        w.writerows(rows)

    print("feature ablation (test set = Rimae Bode, never seen in training)")
    print("  {:<18} {:>7} {:>7} {:>7} {:>7} {:>9}".format(
        "input", "IoU", "P", "R", "F1", "d(F1)"))
    for row in rows:
        print("  {:<18} {:>7.3f} {:>7.3f} {:>7.3f} {:>7.3f} {:>+9.3f}".format(
            row["channels"], row["test_iou"], row["test_precision"],
            row["test_recall"], row["test_f1"], row["test_f1_delta_vs_" + tags[0]]))
    print("  wrote {}".format(out_csv))

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    width = 0.2
    xs = list(range(len(rows)))
    for i, m in enumerate(METRICS):
        ax.bar([x + i * width for x in xs],
               [row["test_" + m] for row in rows], width,
               label={"iou": "IoU", "precision": "precision",
                      "recall": "recall", "f1": "F1"}[m])
    ax.set_xticks([x + 1.5 * width for x in xs])
    ax.set_xticklabels([row["channels"] for row in rows])
    ax.set_ylim(0, 1)
    ax.set_ylabel("score (pixel level, test area)")
    ax.set_title("U-Net crater detection: input-feature ablation")
    ax.legend(ncol=4, fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out_png = W6 / "ablation_features.png"
    fig.savefig(out_png, dpi=150)
    print("  wrote {}".format(out_png))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
