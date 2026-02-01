#!/bin/bash
# Install git hooks for Lattice project
# Run this script after cloning the repository

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/git-hooks"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

echo "Installing git hooks..."

# Copy hooks
cp "$HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
cp "$HOOKS_DIR/commit-msg" "$GIT_HOOKS_DIR/commit-msg"

# Make executable
chmod +x "$GIT_HOOKS_DIR/pre-commit"
chmod +x "$GIT_HOOKS_DIR/commit-msg"

echo "✅ Git hooks installed successfully!"
echo ""
echo "Installed hooks:"
echo "  - pre-commit: runs ruff and unit tests"
echo "  - commit-msg: validates Conventional Commits format"
