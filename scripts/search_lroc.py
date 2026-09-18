#!/usr/bin/env python3
"""Search the LROC archive (wms.lroc.asu.edu) for products in a bounding box.

The LROC image search is a Rails form (POST + CSRF token), so this script
fetches the form, extracts the token, submits the query and parses the
returned product list.

Usage:
  python scripts/search_lroc.py --south 8 --north 13 --west -7 --east -1 \
      --product-type NAC --out data/metadata/lroc_search_nac_rimae_bode.csv
"""
import argparse
import csv
import http.cookiejar
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://wms.lroc.asu.edu"
SEARCH = BASE + "/lroc/search"
UA = "LunarSafeMap/0.1 (undergraduate research; python-urllib)"
PRODUCT_RE = re.compile(r"\b(M\d{9}[LR][EN])\b")


def make_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", UA)]
    return opener


def fetch(opener, url, data=None):
    if data is not None:
        data = urllib.parse.urlencode(data, doseq=True, safe="[]").encode()
    with opener.open(url, data=data, timeout=180) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--south", type=float, required=True)
    ap.add_argument("--north", type=float, required=True)
    ap.add_argument("--west", type=float, required=True)
    ap.add_argument("--east", type=float, required=True)
    ap.add_argument("--product-type", default="NAC", help="NAC or WAC")
    ap.add_argument("--per-page", type=int, default=200)
    ap.add_argument("--out", required=True, help="output CSV path")
    args = ap.parse_args()

    opener = make_opener()
    form = fetch(opener, SEARCH)
    m = re.search(r'name="authenticity_token"[^>]*value="([^"]+)"', form)
    if not m:
        raise SystemExit("could not find CSRF token on search page")
    token = m.group(1)
    print(f"got token ({len(token)} chars)")

    payload = [
        ("utf8", "✓"),
        ("authenticity_token", token),
        ("filter[north]", f"{args.north}"),
        ("filter[south]", f"{args.south}"),
        ("filter[east]", f"{args.east}"),
        ("filter[west]", f"{args.west}"),
    ]
    for pt in args.product_type.split(","):
        payload.append(("filter[product_type][]", pt.strip()))
    payload += [
        ("filter[slew_abs]", "0"),
        ("per_page", str(args.per_page)),
        ("commit", "Search"),
    ]
    html = fetch(opener, SEARCH, payload)
    Path("/tmp/lroc_search_result.html").write_text(html, encoding="utf-8")
    print(f"result page: {len(html)} chars")

    ids = sorted(set(PRODUCT_RE.findall(html)))
    print(f"products found: {len(ids)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "product_type", "search_south", "search_north",
                    "search_west", "search_east"])
        for pid in ids:
            w.writerow([pid, args.product_type, args.south, args.north,
                        args.west, args.east])
    print(f"wrote {out}")
    for pid in ids[:20]:
        print("  ", pid)


if __name__ == "__main__":
    main()