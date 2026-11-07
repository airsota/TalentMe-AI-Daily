#!/usr/bin/env bash
# Sync the latest daily editions, commit, and push.
# Wire this to cron on the machine that has the website content:
#   0 8 * * * /path/to/TalentMe-AI-Daily/scripts/publish_daily.sh
set -euo pipefail

cd "$(dirname "$0")/.."

python3 scripts/sync_daily.py

git add -A
if git diff --cached --quiet; then
  echo "No changes to publish."
  exit 0
fi

git commit -m "chore: sync daily digests $(date -u +%Y-%m-%d)"
git push origin HEAD
