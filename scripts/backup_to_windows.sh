#!/usr/bin/env bash
# Mirror the repository's text artefacts to the Windows workspace as a backup.
#
# Direction matters: the WSL repository is the single source of truth.  The
# Windows folder (C:\Users\zwx\Documents\Codex\2026-08-14\w) used to be the
# editing copy, which caused one real incident - a script was updated there and
# the run used the stale repository copy.  Editing now happens in the repo; this
# script only copies repo -> Windows, never the other way round.
set -e
W=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w
R=$HOME/projects/LunarSafeMap
cd "$R"

mkdir -p "$W/backup_repo"/{scripts,docs,tests,configs,outputs}
rsync -a --delete scripts/ "$W/backup_repo/scripts/"
rsync -a --delete docs/ "$W/backup_repo/docs/"
rsync -a --delete tests/ "$W/backup_repo/tests/"
rsync -a --delete configs/ "$W/backup_repo/configs/"
cp README.md "$W/backup_repo/" 2>/dev/null || true
cp data/metadata/derived_products.csv "$W/backup_repo/" 2>/dev/null || true
du -sh "$W/backup_repo"
echo "[backup] repo -> $W/backup_repo"
