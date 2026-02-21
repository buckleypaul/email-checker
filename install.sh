#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="com.paulbuckley.email-checker.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "Installing Email Checker..."

# 1. Create venv and install Python dependencies
echo "→ Setting up virtual environment..."
python3 -m venv "$SCRIPT_DIR/venv"
"$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# 2. Copy plist
echo "→ Installing LaunchAgent..."
mkdir -p "$LAUNCH_AGENTS"
cp "$SCRIPT_DIR/$PLIST" "$LAUNCH_AGENTS/$PLIST"

# 3. Load (or reload) the launchd job
if launchctl list | grep -q "com.paulbuckley.email-checker"; then
    echo "→ Reloading existing LaunchAgent..."
    launchctl unload "$LAUNCH_AGENTS/$PLIST" 2>/dev/null || true
fi
launchctl load "$LAUNCH_AGENTS/$PLIST"

echo "✓ Email Checker installed and running."
echo "  Look for the ✉ icon in your menu bar."
