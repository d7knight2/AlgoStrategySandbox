"""SEC EDGAR 13F filings for well-known investment managers.

Uses data.sec.gov (free; requires a descriptive User-Agent).
13F holdings are delayed ~45 days. Paper research only.
"""

from __future__ import annotations

import logging
from typing import Any

from src.feeds.http import USER_AGENT, get_json

log = logging.getLogger("trading_core.feeds.sec13f")

DEFAULT_MANAGERS = [
    {"name": "Berkshire Hathaway", "cik": "0001067983", "manager": "Warren Buffett"},
    {"name": "Pershing Square", "cik": "0001336528", "manager": "Bill Ackman"},
    {"name": "Icahn Enterprises", "cik": "0000812011", "manager": "Carl Icahn"},
]


def _pad_cik(cik: str) -> str:
    digits = "".join(ch for ch in cik if ch.isdigit())
    return digits.zfill(10)


def fetch_latest_13f(cik: str, name: str) -> dict[str, Any]:
    padded = _pad_cik(cik)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    try:
        data = get_json(url, headers={"User-Agent": USER_AGENT})
    except Exception as exc:
        log.warning("13F submissions failed cik=%s error=%s", padded, exc)
        return {"ok": False, "name": name, "cik": padded, "error": str(exc)[:300]}

    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    latest: dict[str, Any] | None = None
    for form, filed, acc in zip(forms, dates, accessions, strict=False):
        if str(form).upper().startswith("13F"):
            acc_nodash = str(acc).replace("-", "")
            archives = f"https://www.sec.gov/Archives/edgar/data/{int(padded)}/{acc_nodash}/"
            latest = {
                "ok": True,
                "name": name,
                "cik": padded,
                "form": form,
                "filed": filed,
                "accession": acc,
                "index_url": archives,
            }
            break
    if latest is None:
        return {"ok": False, "name": name, "cik": padded, "error": "no 13F in recent filings"}
    return latest


def fetch_manager_filings(managers: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    rows = managers or DEFAULT_MANAGERS
    out: list[dict[str, Any]] = []
    for mgr in rows:
        info = fetch_latest_13f(mgr["cik"], mgr.get("manager") or mgr["name"])
        info["firm"] = mgr.get("name")
        out.append(info)
    return out
