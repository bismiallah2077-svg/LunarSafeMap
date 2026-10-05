#!/usr/bin/env bash
# Run every self test in the repository.
#
# The index test needs only the standard library, so it also runs in CI.
# Everything else needs the lunarsafe environment (GDAL, numpy, scipy, matplotlib,
# torch); the script skips a test gracefully when a dependency is missing.
set -u
cd "$(dirname "$0")/.."

fail=0
pass=0
skip=0
for t in tests/test_*.py; do
  name=$(basename "$t")
  out=$(python "$t" 2>&1)
  if echo "$out" | grep -q "ALL CHECKS PASSED\|ALL FILES INDEXED"; then
    printf "  PASS  %s\n" "$name"
    pass=$((pass + 1))
  elif echo "$out" | grep -qi "ModuleNotFoundError\|ImportError"; then
    printf "  SKIP  %s  (missing dependency)\n" "$name"
    skip=$((skip + 1))
  else
    printf "  FAIL  %s\n" "$name"
    echo "$out" | tail -5 | sed "s/^/        /"
    fail=$((fail + 1))
  fi
done

echo
echo "  ${pass} passed, ${fail} failed, ${skip} skipped"
exit $((fail > 0))
