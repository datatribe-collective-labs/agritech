#!/usr/bin/env bash
# Copies the frontend to the folder Caddy serves. Run on the server after `git pull`.
# (Caddy runs as its own user and cannot read /root, so the site is served from /var/www.)
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../frontend" && pwd)"
DEST=/var/www/planting-intelligence
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
rm -rf "$DEST/tests" "$DEST/README.md"
chmod -R a+rX "$DEST"
echo "Published $SRC to $DEST"
