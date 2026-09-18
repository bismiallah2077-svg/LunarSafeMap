#!/usr/bin/env python3
"""Build data/metadata/data_manifest.csv from data/raw products.

Supports:
  - PDS3 with detached label (SLDEM2015: .LBL + raw .IMG)
  - PDS3 with attached label (LROC NAC EDR: header inside .IMG)

Each product is verified against the size declared in its label
(RECORD_BYTES x FILE_RECORDS), so partial downloads are flagged.

Output columns: product_id, type, source_url, acquisition_time,
resolution, crs, file, size_bytes, sha256, notes.
"""
import argparse
import csv
import hashlib
import re
from pathlib import Path


def sha256(path: Path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _grab(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.I | re.S)
    return m.group(1).strip().strip("'\"") if m else ""


def _valid_label(text: str) -> bool:
    """A usable PDS3 detached label must declare a product and image size."""
    return bool(
        re.search(r"PRODUCT_ID\s*=\s*\S+", text, re.I)
        and re.search(r"LINES\s*=\s*\d+", text, re.I)
        and re.search(r"LINE_SAMPLES\s*=\s*\d+", text, re.I)
    )


def _expected_bytes(text: str):
    """Expected file size declared by the label, or None if unknown."""
    rb = _grab(text, r"RECORD_BYTES\s*=\s*(\d+)")
    fr = _grab(text, r"FILE_RECORDS\s*=\s*(\d+)")
    if rb.isdigit() and fr.isdigit():
        return int(rb) * int(fr)
    return None


def _size_note(img: Path, expected) -> str:
    actual = img.stat().st_size
    if not expected:
        return "size=unverified"
    if actual == expected:
        return f"size=complete ({actual} B)"
    pct = 100.0 * actual / expected
    return f"size=PARTIAL {actual}/{expected} B ({pct:.1f}% downloaded)"


def parse_detached(lbl: Path, img: Path):
    """Parse a PDS3 detached label next to a raw binary IMG (e.g. SLDEM)."""
    text = lbl.read_text(encoding="utf-8", errors="replace")
    if not _valid_label(text):
        return None
    lines = _grab(text, r"LINES\s*=\s*(\d+)")
    samples = _grab(text, r"LINE_SAMPLES\s*=\s*(\d+)")
    sample_bits = _grab(text, r"SAMPLE_BITS\s*=\s*(\d+)")
    max_lat = _grab(text, r"MAXIMUM_LATITUDE\s*=\s*([\d.]+)")
    min_lat = _grab(text, r"MINIMUM_LATITUDE\s*=\s*([\d.]+)")
    west = _grab(text, r"WESTERNMOST_LONGITUDE\s*=\s*([\d.]+)")
    east = _grab(text, r"EASTERNMOST_LONGITUDE\s*=\s*([\d.]+)")
    ppd = _grab(text, r"MAP_RESOLUTION\s*=\s*(\d+)")
    start = _grab(text, r"START_TIME\s*=\s*([^\n]+)")
    instr = _grab(text, r"INSTRUMENT_ID\s*=\s*(\S+)")
    prod = _grab(text, r"(?<!_)\bPRODUCT_ID\s*=\s*(\S+)")
    # 1 deg of longitude on the Moon ~= 2*pi*1737.4 km / 360 ~= 30.32 km
    ppd_int = int(ppd) if ppd.isdigit() else 0
    res = f"{ppd} ppd (~{round(30320 / ppd_int)} m)" if ppd_int else ""
    return {
        "product_id": prod or img.stem,
        "instrument": instr,
        "start_time": start,
        "lines": lines,
        "samples": samples,
        "sample_bits": sample_bits,
        "resolution": res,
        "crs": f"simple cylindrical {min_lat}-{max_lat}N, {west}-{east}E",
        "expected": _expected_bytes(text),
    }


def parse_attached(img: Path):
    header = img.read_bytes()[:20000].decode(errors="replace")
    if not re.search(r"\^IMAGE\s*=\s*(\d+)", header, re.I):
        return None
    return {
        "product_id": _grab(header, r"(?<!_)\bPRODUCT_ID\s*=\s*(\S+)") or img.stem,
        "instrument": _grab(header, r"INSTRUMENT_ID\s*=\s*(\S+)"),
        "start_time": _grab(header, r"START_TIME\s*=\s*([^\n]+)"),
        "lines": _grab(header, r"(?<!_)(?<!LINE_)LINES\s*=\s*(\d+)"),
        "samples": _grab(header, r"LINE_SAMPLES\s*=\s*(\d+)"),
        "sample_bits": _grab(header, r"SAMPLE_BITS\s*=\s*(\d+)"),
        "resolution": "",
        "crs": "PDS3 raw (EDR)",
        "expected": _expected_bytes(header),
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

        # Detached-label products: .LBL + .IMG
        parsed_stems = set()
        for lbl in sorted(sub.glob("*.LBL")):
            img = sub / (lbl.stem + ".IMG")
            if not img.exists():
                continue
            meta = parse_detached(lbl, img)
            if meta is None:
                continue  # e.g. failed-download .LBL, not a real PDS3 label
            parsed_stems.add(img.stem)
            source_url = ""
            if sub.name == "sldem2015":
                source_url = ("http://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG/"
                              + img.name)
            rows.append({
                "product_id": meta["product_id"],
                "type": sub.name,
                "source_url": source_url,
                "acquisition_time": meta["start_time"],
                "resolution": meta["resolution"],
                "crs": meta["crs"],
                "file": str(img.relative_to(raw.parent)),
                "size_bytes": img.stat().st_size,
                "sha256": "" if args.no_hash else sha256(img),
                "notes": (f"instrument={meta['instrument']}; lines={meta['lines']}; "
                          f"samples={meta['samples']}; bits={meta['sample_bits']}; "
                          f"{_size_note(img, meta['expected'])}"),
            })

        # Attached-label products (e.g. LROC NAC EDR)
        for img in sorted(sub.glob("*.IMG")):
            if img.stem in parsed_stems:
                continue  # already handled via its detached label
            meta = parse_attached(img)
            if meta is None:
                continue
            source_url = ""
            if sub.name == "lroc_nac_edr":
                source_url = ("https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/"
                              "LROLRC_0010/DATA/SCI/2012013/NAC/" + img.name)
            rows.append({
                "product_id": meta["product_id"],
                "type": sub.name,
                "source_url": source_url,
                "acquisition_time": meta["start_time"],
                "resolution": meta["resolution"],
                "crs": meta["crs"],
                "file": str(img.relative_to(raw.parent)),
                "size_bytes": img.stat().st_size,
                "sha256": "" if args.no_hash else sha256(img),
                "notes": (f"instrument={meta['instrument']}; lines={meta['lines']}; "
                          f"samples={meta['samples']}; bits={meta['sample_bits']}; "
                          f"{_size_note(img, meta['expected'])}"),
            })

    rows.sort(key=lambda r: (r["type"], r["product_id"]))
    fieldnames = ["product_id", "type", "source_url", "acquisition_time",
                  "resolution", "crs", "file", "size_bytes", "sha256", "notes"]
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out_csv}")
    for r in rows:
        if "PARTIAL" in r["notes"]:
            print(f"  ! {r['product_id']}: {r['notes'].split(';')[-1].strip()}")


if __name__ == "__main__":
    main()