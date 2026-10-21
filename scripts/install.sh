#!/usr/bin/env bash
# Provision the `agi` wrapper on PATH via a symlink in ~/.local/bin.
# Idempotent. Does not touch /usr/local/bin or system config.
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
WRAPPER="$ROOT/bin/agi"
TARGET_DIR="${HOME}/.local/bin"
TARGET="$TARGET_DIR/agi"

if [ ! -x "$WRAPPER" ]; then
    chmod +x "$WRAPPER"
fi

mkdir -p "$TARGET_DIR"

if [ -L "$TARGET" ] || [ -e "$TARGET" ]; then
    EXISTING="$(readlink -f "$TARGET" 2>/dev/null || echo '')"
    if [ "$EXISTING" = "$WRAPPER" ]; then
        echo "[install] already linked: $TARGET -> $WRAPPER"
    else
        echo "[install] target exists and is not our wrapper: $TARGET"
        echo "[install]   existing: $EXISTING"
        echo "[install]   remove it manually if you want this one"
        exit 1
    fi
else
    ln -s "$WRAPPER" "$TARGET"
    echo "[install] linked: $TARGET -> $WRAPPER"
fi

case ":${PATH}:" in
    *":${TARGET_DIR}:"*) ;;
    *) echo "[install] add $TARGET_DIR to PATH to use 'agi' directly" ;;
esac

echo "[install] done. Try: agi version"
