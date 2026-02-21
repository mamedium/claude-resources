#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
COMMANDS_DIR="$HOME/.claude/commands"
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

# Install commands
if [[ -d "$REPO_DIR/commands" ]]; then
  echo ""
  echo "Installing commands..."
  mkdir -p "$COMMANDS_DIR"

  for item in "$REPO_DIR/commands"/*; do
    name="$(basename "$item")"
    target="$COMMANDS_DIR/$name"

    if [[ -L "$target" ]]; then
      echo -e "${YELLOW}Removing existing symlink: $target${NC}"
      rm "$target"
    elif [[ -e "$target" ]]; then
      echo -e "${YELLOW}Removing existing: $target${NC}"
      rm -rf "$target"
    fi

    ln -s "$item" "$target"
    echo -e "${GREEN}Linked: $target -> $item${NC}"
  done
fi

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

# daily config setup
if printf '%s\n' "${SELECTED[@]}" | grep -qx "daily"; then
  CONFIG_FILE="$CONFIG_DIR/daily.yaml"

  if [[ -f "$CONFIG_FILE" ]]; then
    echo "daily config already exists at $CONFIG_FILE"
    read -rp "Overwrite? (y/N): " OVERWRITE
    if [[ "$OVERWRITE" != "y" && "$OVERWRITE" != "Y" ]]; then
      echo "Keeping existing config."
    else
      rm "$CONFIG_FILE"
    fi
  fi

  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo ""
    echo "Setting up daily config..."
    echo "This skill needs your Slack IDs and channel IDs to monitor activity."
    echo ""

    read -rp "Your name (for Slack searches): " DAILY_NAME
    read -rp "Your Slack user ID (e.g. UXXXXXXXXXX): " DAILY_SLACK_ID
    read -rp "Geekbot DM channel ID (e.g. DXXXXXXXXXX): " DAILY_GEEKBOT_DM
    read -rp "Geekbot bot user ID (e.g. UXXXXXXXXXX): " DAILY_GEEKBOT_UID

    echo ""
    echo "Slack channels to monitor (enter channel IDs, or leave blank to skip):"
    read -rp "  Tech channel ID: " CH_TECH
    read -rp "  Bugs channel ID: " CH_BUGS
    read -rp "  Reported calls channel ID: " CH_CALLS
    read -rp "  Tech dev channel ID: " CH_TECHDEV
    read -rp "  Team channel ID: " CH_TEAM
    read -rp "  Jira channel ID: " CH_JIRA

    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" << EOF
user_name: $DAILY_NAME
user_slack_id: $DAILY_SLACK_ID

geekbot_dm_channel: $DAILY_GEEKBOT_DM
geekbot_user_id: $DAILY_GEEKBOT_UID

channels:
  tech: $CH_TECH
  bugs: $CH_BUGS
  reported_calls: $CH_CALLS
  tech_dev: $CH_TECHDEV
  team: $CH_TEAM
  jira: $CH_JIRA

# Edit these templates manually after setup
chores_template:
  - Item 1
  - Item 2

personal_template:
  - Exercise
  - Read
EOF

    echo -e "${GREEN}Config written to $CONFIG_FILE${NC}"
    echo -e "${YELLOW}Edit $CONFIG_FILE to customize chores_template and personal_template.${NC}"
  fi
fi

echo ""
echo "Setup complete!"
echo ""
echo "Installed skills:"
for skill in "${SELECTED[@]}"; do
  echo "  - $skill -> $SKILLS_DIR/$skill"
done
if [[ -d "$REPO_DIR/commands" ]]; then
  echo ""
  echo "Installed commands:"
  for item in "$REPO_DIR/commands"/*; do
    name="$(basename "$item")"
    echo "  - $name -> $COMMANDS_DIR/$name"
  done
fi
echo ""
echo "Start a new Claude Code session to use the skills and commands."
