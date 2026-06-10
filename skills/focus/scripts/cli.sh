#!/usr/bin/env bash
# Focus CLI - used by the /focus skill and direct invocation.
#
# Subcommands:
#   list                       - print all tracker entries grouped by status
#   show <ticket>              - show details of one ticket
#   focus <ticket> [next...]   - mark ticket as the active one
#   pause <ticket>             - mark ticket as paused
#   block <ticket> <by>        - mark ticket as blocked, link the blocker ticket ID
#   unblock <ticket>           - clear blocked_by, set status to paused
#   resume <ticket>            - set status to active (without auto-pausing others)
#   add <ticket> "<title>"     - add a new ticket entry (usable from hooks too)
#   touch <ticket>             - bump last_touched (e.g. from a Stop hook)
#   done <ticket>              - mark finished (prune removes it after 7 days)
#   remove <ticket>            - drop the entry entirely
#   prune                      - remove `done` entries older than 7 days

set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

usage() {
  cat <<'EOF'
focus - focus tracker CLI

Usage:
  focus list
  focus show <ticket>
  focus focus <ticket> [next step...]
  focus pause <ticket>
  focus block <ticket> <blocker>
  focus unblock <ticket>
  focus resume <ticket>
  focus add <ticket> "<title>"
  focus touch <ticket>
  focus done <ticket>
  focus remove <ticket>
  focus prune
EOF
}

cmd="${1:-list}"
shift || true

case "$cmd" in
  list)
    if [[ ! -f "$FOCUS_FILE" ]]; then
      echo "(no tracker yet - run /focus to start one)"
      exit 0
    fi
    for status in active blocked paused done; do
      lines=$(focus__list_by_status "$status" || true)
      [[ -z "$lines" ]] && continue
      echo "## $status"
      while IFS=$'\t' read -r ticket s title; do
        age=$(focus__age_days "$ticket")
        echo "  - $ticket - $title  (${age}d)"
      done <<< "$lines"
      echo
    done
    ;;

  show)
    ticket="${1:?ticket required}"
    awk -v t="$ticket" '
      $0 ~ "^## " t "( |$)" { in_section=1 }
      in_section && /^## / && NR>1 && $0 !~ "^## " t "( |$)" { exit }
      in_section { print }
    ' "$FOCUS_FILE"
    ;;

  focus)
    ticket="${1:?ticket required}"
    shift
    next_step="${*:-}"
    if ! focus__has_ticket "$ticket"; then
      echo "ticket $ticket not in tracker - run: focus add $ticket \"<title>\"" >&2
      exit 1
    fi
    focus__set_field "$ticket" status active
    focus__set_field "$ticket" last_touched "$(focus__now)"
    if [[ -n "$next_step" ]]; then
      focus__set_field "$ticket" next "$next_step"
    fi
    echo "active: $ticket"
    ;;

  pause)
    ticket="${1:?ticket required}"
    focus__set_field "$ticket" status paused
    echo "paused: $ticket"
    ;;

  block)
    ticket="${1:?ticket required}"
    blocker="${2:?blocker ticket required}"
    focus__set_field "$ticket" status blocked
    focus__set_field "$ticket" blocked_by "$blocker"
    echo "blocked: $ticket (by $blocker)"
    ;;

  unblock)
    ticket="${1:?ticket required}"
    focus__set_field "$ticket" status paused
    focus__set_field "$ticket" blocked_by "-"
    echo "unblocked: $ticket"
    ;;

  resume)
    ticket="${1:?ticket required}"
    focus__set_field "$ticket" status active
    focus__set_field "$ticket" last_touched "$(focus__now)"
    echo "resumed: $ticket"
    ;;

  add)
    ticket="${1:?ticket required}"
    title="${2:?title required}"
    if focus__has_ticket "$ticket"; then
      echo "already tracked: $ticket"
      exit 0
    fi
    focus__add_ticket "$ticket" "$title" active "${3:--}" "${4:--}" "${5:--}"
    echo "added: $ticket"
    ;;

  touch)
    ticket="${1:?ticket required}"
    if ! focus__has_ticket "$ticket"; then
      exit 0
    fi
    focus__set_field "$ticket" last_touched "$(focus__now)"
    # If it was paused or blocked but we're touching it, leave status alone - only
    # an explicit /focus or /resume should reactivate. This avoids surprising
    # status flips when you cd into an old worktree just to look around.
    ;;

  done)
    ticket="${1:?ticket required}"
    focus__set_field "$ticket" status done
    focus__set_field "$ticket" last_touched "$(focus__now)"
    echo "done: $ticket"
    ;;

  remove)
    ticket="${1:?ticket required}"
    [[ -f "$FOCUS_FILE" ]] || exit 0
    tmp=$(mktemp)
    awk -v t="$ticket" '
      $0 ~ "^## " t "( |$)" { in_section=1; next }
      in_section && /^## / { in_section=0 }
      !in_section { print }
    ' "$FOCUS_FILE" > "$tmp"
    mv "$tmp" "$FOCUS_FILE"
    echo "removed: $ticket"
    ;;

  prune)
    [[ -f "$FOCUS_FILE" ]] || exit 0
    while IFS=$'\t' read -r ticket s title; do
      age=$(focus__age_days "$ticket")
      if (( age > 7 )); then
        "$0" remove "$ticket" >/dev/null
        echo "pruned: $ticket (done, ${age}d old)"
      fi
    done < <(focus__list_by_status done)
    ;;

  -h|--help|help)
    usage
    ;;

  *)
    usage
    exit 1
    ;;
esac
