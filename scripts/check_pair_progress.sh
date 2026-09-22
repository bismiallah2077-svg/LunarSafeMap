#!/usr/bin/env bash
# Show how far the Rimae Bode NAC stereo pipeline got before the reboot.
REPO=$HOME/projects/LunarSafeMap
W=$REPO/data/interim/nac_pair
O=$REPO/outputs/week4

echo "=== disk space ==="
df -h "$REPO" | tail -1

echo
echo "=== working dir: $W ==="
ls -la "$W" 2>/dev/null | head -30

echo
echo "=== cubes ==="
for f in "$W"/*.cub; do
  [ -e "$f" ] || continue
  printf "%-44s %14s B  %s\n" "$(basename "$f")" "$(stat -c %s "$f")" "$(stat -c %y "$f" | cut -d. -f1)"
done

echo
echo "=== ASP run directories ==="
ls -d "$W"/run* 2>/dev/null || echo "(none)"
if [ -d "$W/run-stereo" ]; then
  echo "run-stereo entries: $(ls "$W/run-stereo" | wc -l)"
  ls "$W/run-stereo" | head -6
fi

echo
echo "=== ASP logs (last lines) ==="
for f in "$W"/run-log-stereo*.txt "$W"/run-log-*.txt; do
  [ -e "$f" ] || continue
  echo "--- $(basename "$f")"
  tail -4 "$f"
done

echo
echo "=== outputs/week4 ==="
ls -la "$O" 2>/dev/null | head -20

echo
echo "=== still running? ==="
ps -eo pid,etime,cmd | grep -E "parallel_stereo|point2dem|cam2map|lronaccal|stereo_" | grep -v grep || echo "no pipeline process running"

echo
echo "=== last 12 lines of the pipeline log (if any) ==="
for f in "$REPO"/logs/*.log "$W"/*.log; do
  [ -e "$f" ] || continue
  echo "--- $(basename "$f")"
  tail -12 "$f"
done