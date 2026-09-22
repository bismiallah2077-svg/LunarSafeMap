#!/usr/bin/env bash
# Week 6.5: controlled ablation of the U-Net input features.
#
# Exactly one thing changes between the three runs: how many input channels the
# network sees (elevation only / + slope / + slope + hillshade).  Everything
# else is pinned: the same random seed, so the same 400 crater tiles end up in
# the training and validation sets, the same 12 epochs, the same learning rate,
# the same architecture.  That is what turns three runs into one controlled
# experiment: if the score moves, the input features are the only explanation.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w

LIMIT=${LIMIT:-400}
EPOCHS=${EPOCHS:-12}

echo "=== 0. sync files ==="
cp "$M/scripts/week6_train_unet.py" scripts/
cp "$M/scripts/week6_ablation_summary.py" scripts/

echo "=== 1. self test ==="
python scripts/week6_train_unet.py --selftest --channels dem+slope+shade | tail -4

run_one () {
  local channels="$1" tag="$2"
  echo
  echo "############################################################"
  echo "### run: channels=$channels  tag=$tag  (limit $LIMIT, $EPOCHS epochs)"
  echo "############################################################"
  python -u scripts/week6_train_unet.py \
      --channels "$channels" --tag "$tag" \
      --limit "$LIMIT" --epochs "$EPOCHS"
}

echo "=== 2. feature ablation ==="
run_one "dem"              "dem"
run_one "dem+slope"        "dslope"
run_one "dem+slope+shade"  "dshade"

echo
echo "=== 3. summary ==="
python scripts/week6_ablation_summary.py dem dslope dshade

echo
echo "[week6-ablation] DONE - see outputs/week6/ablation_features.csv"
