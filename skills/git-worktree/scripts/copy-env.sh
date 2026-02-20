#!/bin/bash
# Copy environment files to a new worktree
# Usage: copy-env.sh <worktree-path> [source-root]

set -e

WORKTREE_PATH="$1"
SOURCE_ROOT="${2:-$(git rev-parse --show-toplevel 2>/dev/null)}"

if [ -z "$WORKTREE_PATH" ]; then
    echo "Error: Worktree path is required"
    echo "Usage: $0 <worktree-path>"
    exit 1
fi

if [ ! -d "$WORKTREE_PATH" ]; then
    echo "Error: Worktree path does not exist: $WORKTREE_PATH"
    exit 1
fi

copied=0

# Copy .env if it exists
if [ -f "$SOURCE_ROOT/.env" ]; then
    cp "$SOURCE_ROOT/.env" "$WORKTREE_PATH/.env"
    echo "Copied .env to $WORKTREE_PATH"
    copied=$((copied + 1))
fi

# Copy any .env.* files (like .env.local, .env.development, .env.production, etc.)
for envfile in "$SOURCE_ROOT"/.env.*; do
    if [ -f "$envfile" ]; then
        filename=$(basename "$envfile")
        # Skip example files
        [[ "$filename" == *.example ]] && continue
        cp "$envfile" "$WORKTREE_PATH/$filename"
        echo "Copied $filename to $WORKTREE_PATH"
        copied=$((copied + 1))
    fi
done

if [ $copied -eq 0 ]; then
    echo "No .env files found in $SOURCE_ROOT"
else
    echo "Successfully copied $copied environment file(s)"
fi
