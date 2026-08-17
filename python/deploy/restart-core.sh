#!/usr/bin/env bash
set -euo pipefail
systemctl --user restart trading-api.service
systemctl --user restart trading-telegram.service
systemctl --user daemon-reload
echo "restarted api + telegram"
systemctl --user is-active trading-api.service trading-telegram.service
