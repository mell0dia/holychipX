#!/usr/bin/env bash
# Pre-flight asset check before committing a new Holy Chip story release.
#
# Usage:  bash check_release_assets.sh HC024
#
# Verifies every required file exists AND is tracked by git (not just present
# on disk). Prints a green ✓ for each, red ✗ for any missing/untracked. Exits
# non-zero if anything is wrong — wire this into the release flow so commits
# never ship with a missing .pre.png, missing translation, or missing tease.

set -u
SID="${1:-}"
if [ -z "$SID" ]; then
  echo "usage: check_release_assets.sh <SID>  (e.g. HC024)" >&2
  exit 2
fi

SITE="$HOME/holy-chip/website/holy-chip-site"
cd "$SITE" || { echo "site not found"; exit 2; }

OK=0; BAD=0

check_file() {
  local path="$1"
  local full="$SITE/$path"
  if [ ! -f "$full" ]; then
    printf "  \033[31m✗\033[0m  %s  (MISSING on disk)\n" "$path"
    BAD=$((BAD+1)); return
  fi
  # is it tracked by git on the current branch?
  if ! git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    # Maybe it's staged for first commit?
    if git diff --cached --name-only | grep -qx "$path"; then
      printf "  \033[33m●\033[0m  %s  (staged, will commit)\n" "$path"
      OK=$((OK+1))
    else
      printf "  \033[31m✗\033[0m  %s  (UNTRACKED — run \`git add %s\`)\n" "$path" "$path"
      BAD=$((BAD+1))
    fi
  else
    printf "  \033[32m✓\033[0m  %s\n" "$path"
    OK=$((OK+1))
  fi
}

echo "==== ${SID} release asset check ===="
echo
echo "Story images:"
check_file "stories/${SID}.png"
check_file "stories/${SID}.pre.png"
check_file "stories/${SID}.json"
echo
echo "Analysis + blogs (4 languages):"
check_file "stories/analysis/${SID}.md"
check_file "stories/analysis/${SID}.blog.md"
check_file "stories/analysis/${SID}.blog.pt.md"
check_file "stories/analysis/${SID}.blog.fr.md"
check_file "stories/analysis/${SID}.blog.es.md"
echo
echo "Tease (text card source):"
check_file "stories/analysis/${SID}.tease.md"
echo
echo "Origin page (generated):"
check_file "origins/${SID}.html"
echo
echo "Origins index card (must contain ${SID}):"
if grep -q "${SID}" "$SITE/origins/index.html"; then
  printf "  \033[32m✓\033[0m  origins/index.html contains ${SID}\n"
  OK=$((OK+1))
else
  printf "  \033[31m✗\033[0m  origins/index.html MISSING ${SID} card — add it by hand\n"
  BAD=$((BAD+1))
fi
echo
echo "Generator entry (STORIES list must reference ${SID}):"
if grep -q "\"${SID}\"" "$SITE/stories/analysis/generate_origins.py"; then
  printf "  \033[32m✓\033[0m  generate_origins.py STORIES has ${SID}\n"
  OK=$((OK+1))
else
  printf "  \033[31m✗\033[0m  generate_origins.py STORIES MISSING ${SID}\n"
  BAD=$((BAD+1))
fi
echo
echo "===================================="
if [ "$BAD" -eq 0 ]; then
  printf "\033[32m✓ All %d checks passed. Safe to commit.\033[0m\n" "$OK"
  exit 0
else
  printf "\033[31m✗ %d failure(s), %d ok. FIX BEFORE COMMITTING.\033[0m\n" "$BAD" "$OK"
  exit 1
fi
