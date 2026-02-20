#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
CONFIG_DIR="$HOME/.config/claude-resources"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "claude-resources setup"
echo "======================"
echo ""

# Discover available skills
mapfile -t SKILLS < <(ls -1 "$REPO_DIR/skills")

echo "Available skills:"
for i in "${!SKILLS[@]}"; do
  echo "  $((i + 1)). ${SKILLS[$i]}"
done
echo ""

# Ask which to install
read -rp "Install which skills? (enter numbers separated by spaces, or 'all') [all]: " SELECTION
SELECTION="${SELECTION:-all}"

SELECTED=()
if [[ "$SELECTION" == "all" ]]; then
  SELECTED=("${SKILLS[@]}")
else
  for num in $SELECTION; do
    idx=$((num - 1))
    if [[ $idx -ge 0 && $idx -lt ${#SKILLS[@]} ]]; then
      SELECTED+=("${SKILLS[$idx]}")
    else
      echo -e "${RED}Invalid selection: $num${NC}"
    fi
  done
fi

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  echo "No skills selected. Exiting."
  exit 0
fi

echo ""

# Create skills directory if needed
mkdir -p "$SKILLS_DIR"

# Install each selected skill
for skill in "${SELECTED[@]}"; do
  target="$SKILLS_DIR/$skill"
  source="$REPO_DIR/skills/$skill"

  # Remove existing (symlink or directory)
  if [[ -L "$target" ]]; then
    echo -e "${YELLOW}Removing existing symlink: $target${NC}"
    rm "$target"
  elif [[ -d "$target" ]]; then
    echo -e "${YELLOW}Removing existing directory: $target${NC}"
    rm -rf "$target"
  fi

  ln -s "$source" "$target"
  echo -e "${GREEN}Linked: $target -> $source${NC}"
done

echo ""

# codespace-dev config setup
if printf '%s\n' "${SELECTED[@]}" | grep -qx "codespace-dev"; then
  CONFIG_FILE="$CONFIG_DIR/codespace-dev.yaml"

  if [[ -f "$CONFIG_FILE" ]]; then
    echo "codespace-dev config already exists at $CONFIG_FILE"
    read -rp "Overwrite? (y/N): " OVERWRITE
    if [[ "$OVERWRITE" != "y" && "$OVERWRITE" != "Y" ]]; then
      echo "Keeping existing config."
    else
      rm "$CONFIG_FILE"
    fi
  fi

  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo ""
    echo "Setting up codespace-dev config..."

    # Try to auto-detect codespace
    if command -v gh &>/dev/null; then
      echo ""
      echo "Available codespaces:"
      gh codespace list 2>/dev/null || echo "  (could not list codespaces)"
      echo ""
    fi

    read -rp "Codespace name: " CS_NAME
    read -rp "Repo directory in codespace [/workspaces/monorepo]: " CS_REPO
    CS_REPO="${CS_REPO:-/workspaces/monorepo}"
    read -rp "Default app [dashboard]: " CS_APP
    CS_APP="${CS_APP:-dashboard}"
    read -rp "Default port [3000]: " CS_PORT
    CS_PORT="${CS_PORT:-3000}"

    echo ""
    echo "Additional apps (enter empty name to finish):"
    APPS="  $CS_APP: $CS_PORT"
    while true; do
      read -rp "  App name (or enter to finish): " APP_NAME
      [[ -z "$APP_NAME" ]] && break
      read -rp "  Port for $APP_NAME: " APP_PORT
      APPS="$APPS"$'\n'"  $APP_NAME: $APP_PORT"
    done

    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" << EOF
codespace_name: $CS_NAME
repo_dir: $CS_REPO
default_app: $CS_APP
apps:
$APPS
EOF

    echo -e "${GREEN}Config written to $CONFIG_FILE${NC}"
  fi
fi

echo ""
echo "Setup complete!"
echo ""
echo "Installed skills:"
for skill in "${SELECTED[@]}"; do
  echo "  - $skill -> $SKILLS_DIR/$skill"
done
echo ""
echo "Start a new Claude Code session to use the skills."
