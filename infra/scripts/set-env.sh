#!/bin/sh
# Set KEY=VALUE in .env (replace the line, commented-out or not, or append). Used by the Makefile
# targets that switch the archive mount; portable sed -i differs between macOS and Linux, so no sed.
set -eu
key=$1
value=$2
file=${ENV_FILE:-.env}
tmp=$(mktemp)
awk -v key="$key" -v value="$value" '
    BEGIN { done = 0 }
    $0 ~ "^#? ?" key "=" && !done { print key "=" value; done = 1; next }
    { print }
    END { if (!done) print key "=" value }
' "$file" > "$tmp"
cat "$tmp" > "$file"
rm -f "$tmp"
