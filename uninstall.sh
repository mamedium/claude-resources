#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
COMMANDS_DIR="$HOME/.claude/commands"
CONFIG_DIR="$HOME/.config/claude-resources"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "claude-resources uninstall"
echo "=========================="
echo ""

REMOVED=0

# Remove symlinks that point to this repo
if [[ -d "$SKILLS_DIR" ]]; then
  for link in "$SKILLS_DIR"/*; do
    if [[ -L "$link" ]]; then
      target="$(readlink "$link")"
      if [[ "$target" == "$REPO_DIR/skills/"* ]]; then
        echo -e "${YELLOW}Removing symlink: $link -> $target${NC}"
        rm "$link"
        REMOVED=$((REMOVED + 1))
      fi
    fi
  done
fi

if [[ $REMOVED -eq 0 ]]; then
  echo "No skill symlinks pointing to this repo found."
else
  echo -e "${GREEN}Removed $REMOVED skill symlink(s).${NC}"
fi

# Remove command symlinks that point to this repo
REMOVED_CMD=0
if [[ -d "$COMMANDS_DIR" ]]; then
  for link in "$COMMANDS_DIR"/*; do
    if [[ -L "$link" ]]; then
      target="$(readlink "$link")"
      if [[ "$target" == "$REPO_DIR/commands/"* ]]; then
        echo -e "${YELLOW}Removing symlink: $link -> $target${NC}"
        rm "$link"
        REMOVED_CMD=$((REMOVED_CMD + 1))
      fi
    fi
  done
fi

if [[ $REMOVED_CMD -eq 0 ]]; then
  echo "No command symlinks pointing to this repo found."
else
  echo -e "${GREEN}Removed $REMOVED_CMD command symlink(s).${NC}"
fi

echo ""

# Optionally remove config
if [[ -d "$CONFIG_DIR" ]]; then
  read -rp "Remove config directory $CONFIG_DIR? (y/N): " REMOVE_CONFIG
  if [[ "$REMOVE_CONFIG" == "y" || "$REMOVE_CONFIG" == "Y" ]]; then
    rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}Removed $CONFIG_DIR${NC}"
  else
    echo "Keeping config directory."
  fi
else
  echo "No config directory found."
fi

echo ""
echo "Uninstall complete."
