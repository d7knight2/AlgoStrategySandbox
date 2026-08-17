---
name: pi3-fleet
description: Operate the Raspberry Pi 3 worker (RaspberryPi32bitOs) via fleet Pi MCP on the primary Pi. Use when the user mentions pi3, Pi 3, raspberrypi32bitos, WOL, mini-router LAN tasks, or remote checks on the second Pi at 100.85.88.91.
---

# Pi 3 fleet worker (via Pi MCP)

Pi 3 is **not** a separate MCP endpoint. Fleet MCP on **raspberrypi464bitos** (primary) delegates to Pi 3 over SSH using `host="pi3"`.

## Prerequisites

- **Pi MCP** server connected in Cursor (fleet on primary Pi at `~/pi-tools/fleet/`).
- Do **not** assume Cloud Agent or `pi-mcp-server` npm can reach Pi 3 unless Pi MCP is configured for that session.
- Start every Pi 3 session with **`list_hosts`** and confirm `pi3: status=online`.

## Identity

| Field | Value |
|-------|--------|
| Fleet host id | `pi3` |
| Hostname | `RaspberryPi32bitOs` |
| Tailscale IP | `100.85.88.91` |
| MagicDNS | `raspberrypi32bitos.tail8f3a4a.ts.net` |
| LAN (typical) | `10.0.0.38` (mini-router segment) |
| SSH user | `d7knight` |
| Fleet key | `id_ed25519_fleet` (primary → Pi 3) |
| Arch | `armhf` (32-bit Raspbian) |

Pi 3 does **not** run Docker, agent CLIs, GitHub `gh`, or its own FastMCP server.

## Tool selection

Always pass **`host="pi3"`** (except `list_hosts`, which takes no host).

| Goal | Pi MCP tool | Example |
|------|-------------|---------|
| Reachability | `list_hosts` | `{}` |
| Health snapshot | `system_summary` | `{ "host": "pi3" }` |
| Temperature | `cpu_temp` | `{ "host": "pi3" }` |
| Disk / memory / uptime | `disk_free`, `memory_info`, `uptime_info` | `{ "host": "pi3" }` |
| Allowlisted shell | `run_command` | `{ "host": "pi3", "command": "hostname" }` |
| Tailnet peers | `run_command` | `{ "host": "pi3", "command": "tailscale status" }` |

Prefer **`system_summary`** over chaining multiple `run_command` calls.

If `host_diagnostics` is available on the live fleet server, use it for JSON reachability + disk + memory.

## run_command rules (critical)

Policy is **deny-by-default** (`pi-remote` → `mcp/fleet/policy.yml`).

### Allowed on Pi 3 (current allowlist)

- `hostname`, `uptime`, `uname`, `whoami`, `id`, `date`
- `df -h`, `free -h`
- `cat /proc/loadavg`, `cat /proc/meminfo`, `cat /proc/cpuinfo`
- `vcgencmd measure_temp`, `cat /sys/class/thermal/thermal_zone0/temp`
- `tailscale status`, `tailscale ip -4`, `tailscale version`
- `ls`, `ls -la` (under `/home/...` only)
- `systemctl --user status|is-active <unit>` (limited)

### Never do on Pi 3 via run_command

- Chained commands (`hostname && uptime`) — **blocked**
- `sudo …` — **blocked**
- `arp-scan`, `ip neigh`, `nmap`, `wakeonlan` — **not allowlisted** (add to policy first)
- `rm`, `reboot`, `shutdown`, pipe-to-shell — **hard deny**

If you get `blocked: not in allowlist`, read `pi-remote` `mcp/fleet/policy.yml` via `repo_read` on **primary** and propose a minimal new `pattern`, then restart `pi-mcp.service` on primary.

## Standard workflows

### 1. Smoke test Pi 3

1. `list_hosts` → expect `pi3 … status=online`
2. `system_summary` with `host="pi3"`
3. `run_command` with `hostname` on `pi3`

### 2. Check tailnet from Pi 3’s perspective

```
run_command(host="pi3", command="tailscale status")
```

Useful for seeing whether Mac/iPhone/other Pis are active on Tailscale.

### 3. Diagnose “pi3 offline”

1. `list_hosts` — if `offline (…timed out…)`, Tailscale/SSH issue
2. On **primary** (`host="primary"` or default): `run_command(command="tailscale status")`
3. Read primary fleet logs via `repo_read` repo=`pi-remote` path=`…` or ask user to check `~/pi-tools/fleet/mcp.log`
4. User may run on primary: `python3 scripts/18-patch-live-fleet-pi3.py` then `systemctl --user restart pi-mcp.service`

### 4. Wake-on-LAN / LAN scan (not enabled by default)

Pi 3 sits on the mini-router LAN — the right place to discover desktop MACs **once allowlisted**.

Before WOL:

1. Confirm desktop WOL enabled (BIOS + wired adapter)
2. Add allowlist patterns in `pi-remote` `mcp/fleet/policy.yml`, e.g. `ip neigh show`, `arp-scan --localnet`, `wakeonlan …`
3. Restart fleet MCP on primary
4. Run scan on `host="pi3"`, then `wakeonlan -i <broadcast> <MAC>`

Do not guess MAC addresses; scan or ask the user.

## Primary vs Pi 3

| Task | Host |
|------|------|
| Trading API, dashboard, Telegram MCP | `primary` (local) |
| Git repos, `repo_*`, agent CLIs | `primary` only |
| Mini-router LAN / Pi 3 worker ops | `pi3` |
| Docker | `primary` only |

## References

- In-repo: `python/docs/MCP_OPS.md` (fleet allowlist patterns for trading API)
- On Pi: `pi-remote` → `docs/PI3.md`, `mcp/fleet/hosts.yaml`, `mcp/fleet/policy.yml`

## Response conventions

- Show **`list_hosts`** output when reporting Pi 3 connectivity.
- Quote exact MCP tool results; do not invent command output.
- If Pi 3 is offline, say so clearly and distinguish Tailscale vs SSH vs allowlist blocks.
