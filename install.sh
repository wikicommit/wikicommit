#!/usr/bin/env bash
set -euo pipefail

# WikiCommit Skills Installer
# Copies wikicommit-* Skills from this repository to the target wiki repo's .claude/skills/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(pwd)/.claude/skills"
SOURCE_DIR="${SCRIPT_DIR}/.claude/skills"

# Parse options
YES=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --yes) YES=true ;;
    --dry-run) DRY_RUN=true ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: bash install.sh [--yes] [--dry-run]" >&2
      exit 1
      ;;
  esac
done

# Skills to install
SKILLS=("wikicommit-init" "wikicommit-generate" "wikicommit-merge" "wikicommit-review" "wikicommit-remove" "wikicommit-fix" "wikicommit-status" "wikicommit-collect" "wikicommit-search" "wikicommit-ask" "wikicommit-quiz" "wikicommit-synthesize" "wikicommit-serve" "wikicommit-translate" "wikicommit-schema-propose")

echo "WikiCommit Skills Installer"
echo ""
echo "Installing Skills to: ${INSTALL_DIR}/"
echo ""

# Collect files to install
declare -a NEW_FILES=()
declare -a EXISTING_FILES=()

for skill in "${SKILLS[@]}"; do
  skill_src="${SOURCE_DIR}/${skill}"
  if [[ ! -d "${skill_src}" ]]; then
    echo "  [WARN] Source skill not found: ${skill}/" >&2
    continue
  fi

  while IFS= read -r -d '' src_file; do
    rel_path="${src_file#${SOURCE_DIR}/}"
    dest_file="${INSTALL_DIR}/${rel_path}"
    if [[ -f "${dest_file}" ]]; then
      EXISTING_FILES+=("${rel_path}")
    else
      NEW_FILES+=("${rel_path}")
    fi
  done < <(find "${skill_src}" -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -not -path '*/node_modules/*' -print0 | sort -z)
done

# Display planned actions
for rel_path in "${NEW_FILES[@]+"${NEW_FILES[@]}"}"; do
  echo "  [NEW]  ${rel_path}"
done
for rel_path in "${EXISTING_FILES[@]+"${EXISTING_FILES[@]}"}"; do
  echo "  [EXISTS] ${rel_path}"
done

total_files=$(( ${#NEW_FILES[@]} + ${#EXISTING_FILES[@]} ))

if [[ "${total_files}" -eq 0 ]]; then
  echo "" >&2
  echo "Error: No skill source files found in ${SOURCE_DIR}" >&2
  echo "Make sure you run install.sh from the root of the wikicommit repository." >&2
  exit 1
fi

if [[ "${DRY_RUN}" == true ]]; then
  echo ""
  echo "Dry run — no files were copied."
  echo "  ${#NEW_FILES[@]} new file(s), ${#EXISTING_FILES[@]} existing file(s) would be affected."
  exit 0
fi

echo ""

# Create destination directory
mkdir -p "${INSTALL_DIR}"

# Install files
installed=0

for skill in "${SKILLS[@]}"; do
  skill_src="${SOURCE_DIR}/${skill}"
  [[ -d "${skill_src}" ]] || continue

  while IFS= read -r -d '' src_file; do
    rel_path="${src_file#${SOURCE_DIR}/}"
    dest_file="${INSTALL_DIR}/${rel_path}"

    if [[ -f "${dest_file}" ]] && [[ "${YES}" == false ]]; then
      printf "  [EXISTS] %s — overwrite? [y/N] " "${rel_path}"
      answer=""
      { read -r answer < /dev/tty; } 2>/dev/null || answer=""
      case "${answer}" in
        [yY]*) ;;
        *) continue ;;
      esac
    fi

    mkdir -p "$(dirname "${dest_file}")"
    cp "${src_file}" "${dest_file}"
    installed=$(( installed + 1 ))
  done < <(find "${skill_src}" -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -not -path '*/node_modules/*' -print0 | sort -z)
done

echo "Successfully installed ${installed} file(s)."
echo ""
echo "Next steps:"
echo "  1. Run /wikicommit-init in Claude Code to initialize your wiki repository"
echo "  2. Run /wikicommit-generate <path|url> to register a source and generate wiki pages"
echo "  3. Run /wikicommit-review <page> to validate and review a manually created/edited page"
echo "  4. Run /wikicommit-remove <page> to mark a page (and its translations) as removed"
echo "  5. Run /wikicommit-fix <issue-url> to fix a wiki page based on a GitHub Issue"
echo "  6. Run /wikicommit-merge to run quality gates and open a PR"
echo "  7. Run /wikicommit-status to check wiki health (orphans, unreviewed, expired, stale translations)"
echo "  8. Run /wikicommit-collect to discover candidate sources related to your wiki's theme (requires config.yml theme)"
