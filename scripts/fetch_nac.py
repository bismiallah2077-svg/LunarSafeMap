#!/usr/bin/env python3
"""Fetch LROC NAC EDR products and verify them against their PDS labels.

Two ways to specify a product:

  1. a full URL (copy it from the LROC QuickMap / PDS product page):
       python scripts/fetch_nac.py --url https://pds.lroc.im-ldi.com/.../M123456789LE.IMG
  2. a product id together with its volume and acquisition date:
       python scripts/fetch_nac.py --volume LROLRC_0010 --date 2012013 M181058717LE

Files land in data/raw/lroc_nac_<region>/ (default: lroc_nac_rimae_bode) and the
script checks the downloaded size against RECORD_BYTES x FILE_RECORDS read from
the embedded label, so a truncated download is reported instead of silently used.

Proxy: honours http_proxy / https_proxy environment variables.
"""
import argparse
import hashlib
import re
import urllib.request
from pathlib import Path

BASE = "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0"
REPO = Path(__file__).resolve().parents[1]


def build_url(volume: str, date: str, pid: str) -> str:
    return f"{BASE}/{volume}/DATA/SCI/{date}/NAC/{pid}.IMG"


def download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "LunarSafeMap/0.1"})
    with urllib.request.urlopen(req, timeout=1800) as r, dest.open("wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def label_size(path: Path):
    """RECORD_BYTES x FILE_RECORDS from the embedded PDS3 label."""
    head = path.open("rb").read(20000).decode(errors="replace")
    rb = re.search(r"RECORD_BYTES\s*=\s*(\d+)", head)
    fr = re.search(r"FILE_RECORDS\s*=\s*(\d+)", head)
    if rb and fr:
        return int(rb.group(1)) * int(fr.group(1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("product_ids", nargs="*", help="e.g. M181058717LE")
    ap.add_argument("--url", action="append", default=[],
                    help="full download URL (repeatable)")
    ap.add_argument("--volume", help="PDS volume, e.g. LROLRC_0010")
    ap.add_argument("--date", help="acquisition date folder, e.g. 2012013")
    ap.add_argument("--region", default="rimae_bode",
                    help="sub-folder name under data/raw/")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    outdir = Path(args.out) if args.out else REPO / "data" / "raw" / f"lroc_nac_{args.region}"
    outdir.mkdir(parents=True, exist_ok=True)

    urls = list(args.url)
    for pid in args.product_ids:
        if not args.volume or not args.date:
            raise SystemExit("pass --volume and --date when using product ids")
        urls.append(build_url(args.volume, args.date, pid))
    if not urls:
        raise SystemExit("nothing to do: pass --url or product ids")

    for url in urls:
        name = url.rstrip("/").split("/")[-1]
        dest = outdir / name
        print(f"GET {url}")
        size = download(url, dest)
        expected = label_size(dest)
        sha = sha256_file(dest)
        state = "complete" if expected == size else f"MISMATCH (label says {expected})"
        print(f"  {dest}")
        print(f"  {size} bytes, size={state}")
        print(f"  sha256 {sha}")


if __name__ == "__main__":
    main()