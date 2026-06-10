#!/usr/bin/env bash
# Shared helpers for the focus tracker.
# Sourced by the focus CLI (and optionally by hooks). Keep dependencies minimal: bash + sed + awk + grep.

# CUSTOMIZE: where the tracker data lives. Override with `export FOCUS_DIR=...`.
FOCUS_DIR="${FOCUS_DIR:-$HOME/.claude/focus}"
FOCUS_FILE="$FOCUS_DIR/active.md"

# Extract a ticket ID (e.g. ENG-123) from a string. Echoes empty on no match.
focus__extract_ticket() {
  local input="${1:-}"
  echo "$input" | grep -oE '[A-Z]+-[0-9]+' | head -1
}

# Detect the ticket ID for a given working directory.
# Order: 1) git branch (user/eng-123 -> ENG-123), 2) directory basename, 3) parent dir.
focus__ticket_from_cwd() {
  local cwd="${1:-$PWD}"
  local branch=""
  local ticket=""

  if branch=$(git -C "$cwd" branch --show-current 2>/dev/null); then
    if [[ -n "$branch" ]]; then
      # Branch like "user/eng-123" or "eng-123-foo" or "ENG-123"
      ticket=$(echo "$branch" | tr '[:lower:]' '[:upper:]' | grep -oE '[A-Z]+-[0-9]+' | head -1)
      if [[ -n "$ticket" ]]; then
        echo "$ticket"
        return 0
      fi
    fi
  fi

  # Try directory basename
  ticket=$(basename "$cwd" | tr '[:lower:]' '[:upper:]' | grep -oE '[A-Z]+-[0-9]+' | head -1)
  if [[ -n "$ticket" ]]; then
    echo "$ticket"
    return 0
  fi

  # Try parent directory (worktrees are often /path/<TICKET>/)
  ticket=$(basename "$(dirname "$cwd")" | tr '[:lower:]' '[:upper:]' | grep -oE '[A-Z]+-[0-9]+' | head -1)
  echo "$ticket"
}

# ISO 8601 UTC timestamp.
focus__now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Check if the tracker contains a ticket section.
focus__has_ticket() {
  local ticket="$1"
  [[ -f "$FOCUS_FILE" ]] || return 1
  grep -qE "^## $ticket( |$)" "$FOCUS_FILE"
}

# Get a field value for a ticket. Args: ticket, field-name.
focus__get_field() {
  local ticket="$1" field="$2"
  [[ -f "$FOCUS_FILE" ]] || return 1
  awk -v t="$ticket" -v f="$field" '
    $0 ~ "^## " t "( |$)" { in_section=1; next }
    in_section && /^## / { in_section=0 }
    in_section && $0 ~ "^- " f ":" {
      sub("^- " f ": *", "")
      print
      exit
    }
  ' "$FOCUS_FILE"
}

# Set a field value for a ticket. Args: ticket, field-name, new-value.
# Idempotent - creates or updates in place.
focus__set_field() {
  local ticket="$1" field="$2" value="$3"
  [[ -f "$FOCUS_FILE" ]] || return 1

  if ! focus__has_ticket "$ticket"; then
    return 1
  fi

  local tmp
  tmp=$(mktemp)
  awk -v t="$ticket" -v f="$field" -v v="$value" '
    $0 ~ "^## " t "( |$)" { in_section=1; print; next }
    in_section && /^## / { in_section=0 }
    in_section && $0 ~ "^- " f ":" {
      print "- " f ": " v
      next
    }
    { print }
  ' "$FOCUS_FILE" > "$tmp"
  mv "$tmp" "$FOCUS_FILE"
}

# Add a new ticket section. Args: ticket, title, status, worktree, next, blocked_by.
focus__add_ticket() {
  local ticket="$1" title="$2" status="${3:-active}" worktree="${4:--}" next_step="${5:--}" blocked="${6:--}"
  local now
  now=$(focus__now)

  if focus__has_ticket "$ticket"; then
    return 0
  fi

  mkdir -p "$FOCUS_DIR"
  {
    echo ""
    echo "## $ticket - $title"
    echo "- status: $status"
    echo "- worktree: $worktree"
    echo "- last_touched: $now"
    echo "- next: $next_step"
    echo "- blocked_by: $blocked"
  } >> "$FOCUS_FILE"
}

# Count entries by status. Arg: status.
focus__count_status() {
  local status="$1"
  [[ -f "$FOCUS_FILE" ]] || { echo 0; return; }
  grep -cE "^- status: $status\$" "$FOCUS_FILE" || true
}

# List ticket IDs by status. Arg: status (or "all").
focus__list_by_status() {
  local status="$1"
  [[ -f "$FOCUS_FILE" ]] || return 0
  awk -v want="$status" '
    /^## / {
      ticket = $2
      title = ""
      for (i=4; i<=NF; i++) title = title (i==4?"":" ") $i
      next
    }
    /^- status: / {
      s = $3
      if (want == "all" || s == want) print ticket "\t" s "\t" title
    }
  ' "$FOCUS_FILE"
}

# Get last_touched age for a ticket in days. Echoes integer.
focus__age_days() {
  local ticket="$1"
  local ts
  ts=$(focus__get_field "$ticket" last_touched)
  [[ -z "$ts" ]] && { echo "999"; return; }
  local then now diff
  # BSD date (macOS) first, GNU date (Linux) fallback.
  then=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts" +%s 2>/dev/null || date -u -d "$ts" +%s 2>/dev/null || echo 0)
  now=$(date -u +%s)
  diff=$(( (now - then) / 86400 ))
  echo "$diff"
}
