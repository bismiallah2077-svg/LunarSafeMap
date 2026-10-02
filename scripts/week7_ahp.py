#!/usr/bin/env python3
"""Week 7.4: turn expert judgement into factor weights, with a consistency check.

The weights in S = w1*H1 + w2*H2 + ... are not measurements - they encode a
trade-off.  AHP (analytic hierarchy process) makes that trade-off explicit and
*auditable*: you compare the factors two at a time on Saaty's 1-9 scale, and the
method converts the comparisons into weights while telling you whether your
judgements are self-consistent.

Why this matters for the thesis: "we used expert weights" is not defensible
unless the reader can see (a) the pairwise matrix, (b) the derived weights,
(c) the consistency ratio, and (d) how sensitive the result is to them.

Usage
  python scripts/week7_ahp.py --selftest
  python scripts/week7_ahp.py --file configs/ahp_matrix.csv
  python scripts/week7_ahp.py --matrix "1,3,2; 1/3,1,1/2; 1/2,2,1"
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FILE = REPO / "configs" / "ahp_matrix.csv"
FACTORS = ["slope", "roughness", "crater"]

# Saaty's random consistency index (the values used for n <= 9)
RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
      8: 1.41, 9: 1.45}


def parse_matrix(text: str) -> np.ndarray:
    """'1,3,2; 1/3,1,1/2; 1/2,2,1' -> 3x3 matrix (fractions allowed)."""
    rows = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        vals = []
        for tok in chunk.split(","):
            tok = tok.strip()
            if not tok:
                continue
            if "/" in tok:
                num, den = tok.split("/")
                vals.append(float(num) / float(den))
            else:
                vals.append(float(tok))
        rows.append(vals)
    a = np.asarray(rows, dtype="float64")
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise SystemExit("the matrix must be square; got shape {}".format(a.shape))
    return a


def read_matrix_file(path: Path) -> tuple[np.ndarray, list[str]]:
    """Read a CSV with a header row of factor names and the factors as rows."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    header = [h.strip() for h in rows[0]]
    names = [r[0].strip() for r in rows[1:]]
    if header[0].lower() in ("factor", "", "criteria"):
        header = header[1:]
    vals = []
    for r in rows[1:]:
        vals.append([float(x) for x in r[1:]])
    a = np.asarray(vals, dtype="float64")
    if a.shape != (len(names), len(names)):
        raise SystemExit("{}: expected a {}x{} matrix, got {}".format(
            path, len(names), len(names), a.shape))
    return a, names


def geometric_weights(a: np.ndarray) -> np.ndarray:
    """Row geometric mean, normalised (the standard practical AHP estimator)."""
    gm = np.prod(a, axis=1) ** (1.0 / a.shape[0])
    return gm / gm.sum()


def consistency(a: np.ndarray, w: np.ndarray) -> tuple[float, float, float]:
    """(lambda_max, consistency index, consistency ratio) for a matrix + weights."""
    n = a.shape[0]
    aw = a @ w
    lmax = float(np.mean(aw / w))
    ci = (lmax - n) / (n - 1) if n > 1 else 0.0
    cr = ci / RI[n] if RI.get(n, 0.0) else 0.0
    return lmax, ci, cr


def reciprocity_error(a: np.ndarray) -> float:
    """Largest deviation from a_ij * a_ji = 1 (should be ~0)."""
    return float(np.max(np.abs(a * a.T - 1.0)))


def ask_pairs(names) -> np.ndarray:
    """Ask the n(n-1)/2 pairwise questions and build the comparison matrix.

    This is the "hand holding" version of the exercise: three questions, each
    answer recorded immediately, matrix echoes back before the weights appear.
    """
    n = len(names)
    a = np.ones((n, n), dtype="float64")
    print("=== interactive AHP: three questions ===")
    print("For each pair, say which factor matters more for a *safe* landing,")
    print("and by how much on Saaty's 1-9 scale.")
    for i in range(n):
        for j in range(i + 1, n):
            print("")
            print("  Q: {}  vs  {}".format(names[i], names[j]))
            print("     1 = {} matters more".format(names[i]))
            print("     2 = {} matters more".format(names[j]))
            print("     0 = equally important")
            while True:
                ans = input("     > ").strip()
                if ans in ("0", "1", "2"):
                    break
                print("     please type 0, 1 or 2")
            if ans == "0":
                v = 1.0
            else:
                print("     by how much?  1 = equal, 3 = moderately,")
                print("                   5 = strongly, 9 = extremely")
                while True:
                    raw = input("     > ").strip()
                    try:
                        v = float(raw)
                    except ValueError:
                        print("     please type a number from 1 to 9")
                        continue
                    if 1.0 <= v <= 9.0:
                        break
                    print("     please type a number from 1 to 9")
                if ans == "2":
                    v = 1.0 / v
            a[i, j] = v
            a[j, i] = 1.0 / v
            print("     recorded: a[{},{}] = {:.4f}".format(names[i], names[j], v))
    return a


def selftest() -> int:
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:56s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    w = geometric_weights(np.ones((3, 3)))
    check("equal matrix -> equal weights", w[0], 1.0 / 3.0)
    _, _, cr = consistency(np.ones((3, 3)), w)
    check("equal matrix is perfectly consistent", cr, 0.0)

    # a perfectly consistent matrix built from 0.5 / 0.3 / 0.2
    want = np.array([0.5, 0.3, 0.2])
    a = want[:, None] / want[None, :]
    w2 = geometric_weights(a)
    for i, nm in enumerate(FACTORS):
        check("recovers the planted weight of {}".format(nm), w2[i], want[i], 1e-9)
    _, _, cr2 = consistency(a, w2)
    check("planted matrix is consistent", cr2, 0.0, 1e-9)

    # a realistic, slightly inconsistent judgement: slope > crater > roughness
    a3 = parse_matrix("1,3,2; 1/3,1,1/2; 1/2,2,1")
    w3 = geometric_weights(a3)
    check("slope has the largest weight", float(np.argmax(w3)), 0.0)
    _, _, cr3 = consistency(a3, w3)
    check("CR stays below 0.1", cr3 < 0.1, 1.0)
    check("weights sum to one", float(w3.sum()), 1.0)
    check("reciprocity error", reciprocity_error(a3), 0.0, 1e-12)

    a4 = parse_matrix("1,3,2; 1/3,1,1/2; 1/2,2,5")     # deliberately messy
    _, _, cr4 = consistency(a4, geometric_weights(a4))
    check("inconsistent judgement is detected", cr4 > 0.1, 1.0)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--file", default=str(DEFAULT_FILE),
                    help="CSV with a header row and one row per factor")
    ap.add_argument("--matrix", default="",
                    help='e.g. "1,3,2; 1/3,1,1/2; 1/2,2,1" (overrides --file)')
    ap.add_argument("--tag", default="ahp", help="tag suggested for the run")
    ap.add_argument("--interactive", action="store_true",
                    help="ask the three pairwise questions and build the matrix "
                         "from your answers")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    if args.interactive:
        a = ask_pairs(FACTORS)
        names = FACTORS
        source = "interactive answers"
    elif args.matrix:
        a = parse_matrix(args.matrix)
        names = FACTORS[: a.shape[0]]
        source = "command line"
    else:
        path = Path(args.file)
        if not path.exists():
            raise SystemExit("no {} - edit the template first".format(path))
        a, names = read_matrix_file(path)
        source = str(path)

    print("=== AHP pairwise matrix ({}) ===".format(source))
    print("  {:>10} ".format("") + " ".join("{:>8}".format(n[:8]) for n in names))
    for i, nm in enumerate(names):
        print("  {:>10} ".format(nm) + " ".join("{:>8.3f}".format(v) for v in a[i]))

    rec = reciprocity_error(a)
    if rec > 0.01:
        print("  ! the matrix is not reciprocal (max |a_ij*a_ji - 1| = {:.3f}); "
              "the lower triangle should be 1/a_ij".format(rec))

    w = geometric_weights(a)
    lmax, ci, cr = consistency(a, w)
    print("")
    print("=== weights ===")
    for nm, wi in zip(names, w):
        print("  {:<10} {:.4f}".format(nm, wi))
    print("")
    print("  lambda_max {:.4f} | CI {:.4f} | CR {:.4f}  ->  {}".format(
        lmax, ci, cr, "ACCEPTABLE (CR < 0.1)" if cr < 0.1 else
        "TOO INCONSISTENT - revisit the comparisons"))
    print("")
    print("  next step:")
    print("  python scripts/week7_suitability.py --weights {} --tag {}".format(
        ",".join("{:.4f}".format(x) for x in w), args.tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
