#!/usr/bin/env python3
"""Build data/metadata/data_manifest.csv from data/raw products.

Reads PDS3 labels (detached .LBL or attached header in .IMG) and computes
sha256 for each file.
Output columns: product_id, type, source_url, acquisition_time,
resolution, crs, file, size_bytes, sha256, notes.
"""
import argparse
import csv
import hashlib
import re
from pathlib import Path

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

def sha256(path: Path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def parse_label(text: str):
    """Minimal PDS3 label parser for the fields we care about."""
    def grab(pattern):
        m = re.search(pattern, text, re.I | re.S)
        return m.group(1).strip().strip("'\"") if m else ""
    prod = grab(r"PRODUCT_ID\s*=\s*(\S+)")
    instr = grab(r"INSTRUMENT_ID\s*=\s*(\S+)")
    start = grab(r"START_TIME\s*=\s*([^\n]+)")
    lines = grab(r"LINE_SAMPLES\s*=\s*(\d+)")
    samples = grab(r"LINE_SAMPLES\s*=\s*(\d+)")
    # PDS3 uses SAMPLE_TYPE/LINE_SAMPLES; sample size
    sample_type = grab(r"SAMPLE_TYPE\s*=\s*(\S+)")
    return {
        "product_id": prod,
        "instrument": instr,
        "start_time": start,
        "lines": lines,
        "samples": samples,
        "sample_type": sample_type,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir", help="data/raw directory")
    ap.add_argument("out_csv", help="output csv path")
    ap.add_argument("--no-hash", action="store_true", help="skip sha256 (fast)")
    args = ap.parse_args()

    rows = []
    raw = Path(args.raw_dir)
    for sub in sorted(raw.iterdir()):
        if not sub.is_dir():
            continue
        imgs = sorted(sub.glob("*.IMG"))
        for img in imgs:
            # PDS3 attached label: read the header; find the ^IMAGE offset to know label length
            header = img.read_bytes()[:8192].decode(errors="replace")
            meta = parse_label(header)
            if not re.search(r"\^IMAGE\s*=\s*(\d+)", header, re.I):
                continue
            source_url = ""
            if sub.name == "lroc_nac_edr":
                source_url = ("https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/"
                              "LROLRC_0010/DATA/SCI/2012013/NAC/" + img.name)
            rows.append({
                "product_id": img.stem,
                "type": sub.name,
                "source_url": source_url,
                "acquisition_time": meta["start_time"],
                "resolution": "",
                "crs": "PDS3 raw",
                "file": str(img.relative_to(raw.parent)),
                "size_bytes": img.stat().st_size,
                "sha256": "" if args.no_hash else sha256(img),
                "notes": (f"instrument={meta['instrument']}; samples={meta['samples']}; "
                          f"type={meta['sample_type']}; label_product_id={meta['product_id']}"),
            })
    rows.sort(key=lambda r: r["product_id"])
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["product_id", "type", "source_url", "acquisition_time",
                            "resolution", "crs", "file", "size_bytes", "sha256", "notes"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out_csv}")

if __name__ == "__main__":
    main()
