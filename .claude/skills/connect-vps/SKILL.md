---
name: connect-vps
description: Use when the user runs /connect-vps or asks to connect to, inspect, or run commands on the hukuk VPS (the server hosting the Themis/Hermes container hermes-hukuk and the hukuk-yz deployment).
---

# connect-vps

Opens a persistent SSH connection (ControlMaster, 30 min idle) to the hukuk VPS. Every later server command in the session reuses it.

## Run

1. Run `.claude/skills/connect-vps/vps.sh --connect` and show the user the status it prints (host, RAM, disk, containers).
2. If it fails with `VPS_HOST is not set`, tell the user to create `.env.claude` at the repo root (format below) and stop.
3. On any other error (timeout, `Permission denied`), report the exact error. Do not retry with other users, keys or hosts.

## Using the connection

- Run server commands as `.claude/skills/connect-vps/vps.sh '<command>'`, not plain `ssh`.
- For an interactive shell, tell the user to type `! .claude/skills/connect-vps/vps.sh`.
- To close the connection: `vps.sh --close`.

## `.env.claude` (repo root, gitignored by `.env.*`)

```
VPS_HOST=<server ip>
VPS_USER=root                    # optional, default root
VPS_KEY=~/.ssh/id_ed25519        # optional, default shown
# VPS_PASSWORD=...               # only if key auth is unavailable
```

## Rules

- **The repo is public.** Never write the IP, password or keys into tracked files. They belong only in `.env.claude`.
- **Never print `.env.claude`, or the server's `/opt/hermes-hukuk/data/.env`.** To check a value, print a prefix, a suffix or a count.
- **Read `~/Desktop/SERVERS.md` before changing anything on the server,** and update it afterwards.
- **Themis config is read-only inside the container.** To change it, edit it on the host, then run `docker compose up -d --force-recreate` in `/opt/hermes-hukuk`. Before recreating, check in `data/logs/agent.log` that the agent is idle.
