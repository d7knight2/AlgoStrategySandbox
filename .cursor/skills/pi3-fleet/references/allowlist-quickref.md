# Pi 3 run_command allowlist quick reference

Source of truth: `pi-remote` → `mcp/fleet/policy.yml`

## Currently allowed (regex patterns)

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

## Common requests that need policy additions

| User request | Suggested pattern to add |
|--------------|-------------------------|
| LAN neighbors | `'^ip neigh show$'` |
| ARP scan | `'^arp-scan --localnet$'` |
| Wake desktop | `'^wakeonlan -i [0-9.]+ [0-9a-fA-F:]+$'` |
| Ping LAN host | `'^ping -c [0-9]+ [0-9.]+$'` |

After editing policy on primary:

```bash
systemctl --user restart pi-mcp.service
```
