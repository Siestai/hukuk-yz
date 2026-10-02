#!/usr/bin/env bash
# Persistent SSH to the hukuk VPS via an SSH ControlMaster socket.
#   vps.sh --connect      open (or reuse) the master connection and print a status summary
#   vps.sh '<command>'    run a command on the VPS over the open connection
#   vps.sh --close        close the master connection
#   vps.sh                interactive shell (run by the user with `! ...`, not by Claude)
# Settings come from .env.claude at the repo root (gitignored); see SKILL.md.
set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
ENV_FILE="$ROOT/.env.claude"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a

: "${VPS_HOST:?VPS_HOST is not set; add it to $ENV_FILE}"
VPS_USER="${VPS_USER:-root}"
VPS_KEY="${VPS_KEY:-$HOME/.ssh/id_ed25519}"
SOCK="$HOME/.ssh/cm-hukuk-vps-%C"

OPTS=(-i "$VPS_KEY" -o ControlMaster=auto -o "ControlPath=$SOCK" -o ControlPersist=30m
      -o ConnectTimeout=10 -o ServerAliveInterval=30)

# Password fallback: only when VPS_PASSWORD is set. The password stays in the env, never on argv or disk.
if [ -n "${VPS_PASSWORD:-}" ]; then
  ASKPASS="$(mktemp)"; trap 'rm -f "$ASKPASS"' EXIT
  printf '#!/bin/sh\nprintf "%%s\\n" "$VPS_PASSWORD"\n' > "$ASKPASS"; chmod 700 "$ASKPASS"
  export VPS_PASSWORD SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force
fi

TARGET="$VPS_USER@$VPS_HOST"

case "${1:-}" in
  --connect)
    ssh "${OPTS[@]}" "$TARGET" '
      echo "connected: $(hostname) ($(. /etc/os-release; echo $PRETTY_NAME)), up $(uptime -p | sed "s/up //")"
      free -m | awk "/Mem:/{printf \"ram: %d MB used / %d MB, %d MB available\n\", \$3, \$2, \$7}"
      df -h / | awk "NR==2{print \"disk: \"\$3\" used / \"\$2\" (\"\$5\")\"}"
      echo "containers:"; docker ps --format "  {{.Names}}  {{.Status}}"
    '
    ;;
  --close)
    ssh "${OPTS[@]}" -O exit "$TARGET" 2>&1 || true
    ;;
  "")
    exec ssh "${OPTS[@]}" -t "$TARGET"
    ;;
  *)
    ssh "${OPTS[@]}" "$TARGET" "$@"
    ;;
esac
