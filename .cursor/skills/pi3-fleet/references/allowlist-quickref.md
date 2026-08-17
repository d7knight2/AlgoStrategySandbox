# Pi 3 run_command allowlist quick reference

Source of truth: `pi-remote` → `mcp/fleet/policy.yml` (live copy under `~/pi-tools/fleet/` on primary).

Canonical paste block: `python/docs/MCP_OPS.md` section A.

## Baseline (primary + pi3)

```
uptime, uptime -p
hostname
uname, uname -a, etc.
df -h, df -h /
free -h
cat /proc/loadavg | meminfo | cpuinfo
vcgencmd measure_temp
cat /sys/class/thermal/thermal_zone0/temp
tailscale status | ip -4 | version
whoami, id, date
ls, ls -la (paths under /home/...)
systemctl --user status|is-active <unit>
docker ps (primary only; pi3 has docker: false)
```

## Pi 3 LAN + Wake-on-LAN (host="pi3")

| Command | Purpose |
|---------|---------|
| `ip neigh show` | List LAN neighbors (MAC/IP) |
| `ip link show` | Interface link/MAC state |
| `ip -4 addr show` | Pi 3 interface addresses |
| `ip route` | Default route / subnet |
| `cat /proc/net/arp` | Kernel ARP table |
| `cat /sys/class/net/eth0/address` | Interface hardware MAC |
| `ping -c 3 10.0.0.x` | Reachability to a LAN IP |
| `ping -c 3 hostname` | Reachability by hostname |
| `getent hosts name` | Resolve hostname on LAN |
| `which wakeonlan` / `etherwake` / `arp-scan` | Check WOL tools installed |
| `wakeonlan aa:bb:cc:dd:ee:ff` | WOL magic packet (default broadcast) |
| `wakeonlan -i 10.0.0.255 aa:bb:…` | WOL with explicit broadcast |
| `etherwake -i eth0 aa:bb:…` | WOL via etherwake |

**Not allowlisted:** `arp-scan --localnet` (requires sudo), `nmap`, chained shells.

Install WOL tools on Pi 3 manually if missing: `sudo apt install wakeonlan` (not via MCP).

## Primary-only trading ops

See `python/docs/MCP_OPS.md` — localhost `:8080` curls, `trading-*` systemd, log tails, `pi-mcp.service` restart, `23-sync-fleet-policy.py`.

## After policy change

On primary (pick one):

```bash
python3 ~/repos/d7knight2/pi-remote/scripts/23-sync-fleet-policy.py
# or (also reinstalls trading units):
bash ~/repos/d7knight2/AlgoStrategySandbox/python/deploy/install-all.sh
```

Verify on pi3:

```
run_command(host="pi3", command="ip neigh show")
run_command(host="pi3", command="tailscale status")
```
