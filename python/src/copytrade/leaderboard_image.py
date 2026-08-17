"""Render paper-book leaderboard as a PNG for Telegram.

Falls back: matplotlib → Pillow → pure-stdlib solid PNG + sidecar .txt
(no AI, works without optional deps).
"""

from __future__ import annotations

import logging
import struct
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("trading_core.copytrade.leaderboard_image")
REPORTS = Path(__file__).resolve().parents[2] / "data" / "reports"


def _truncate(name: str, n: int = 22) -> str:
    name = (name or "").strip() or "—"
    return name if len(name) <= n else name[: n - 1] + "…"


def render_leaderboard_png(
    rows: list[dict[str, Any]],
    *,
    title: str = "Paper books leaderboard",
    subtitle: str | None = None,
    out_path: Path | None = None,
) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = out_path or (REPORTS / "leaderboard_latest.png")
    sub = subtitle or datetime.utcnow().strftime("%Y-%m-%d UTC · virtual paper only")

    try:
        return _render_matplotlib(rows, title=title, subtitle=sub, path=path)
    except Exception as exc:
        log.warning("matplotlib render failed: %s — trying Pillow", type(exc).__name__)
    try:
        return _render_pillow(rows, title=title, subtitle=sub, path=path)
    except Exception as exc:
        log.warning("Pillow render failed: %s — stdlib PNG + txt", type(exc).__name__)
        return _render_stdlib(rows, title=title, subtitle=sub, path=path)


def _render_matplotlib(
    rows: list[dict[str, Any]],
    *,
    title: str,
    subtitle: str,
    path: Path,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top = rows[:12]
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 8),
        gridspec_kw={"height_ratios": [1.2, 1]},
        facecolor="#0b0d12",
    )
    ax_tbl, ax_bar = axes
    for ax in axes:
        ax.set_facecolor("#141822")
        ax.tick_params(colors="#8b95a8")
        for spine in ax.spines.values():
            spine.set_color("#2a3348")

    ax_tbl.axis("off")
    ax_tbl.set_title(title, color="#e8ecf4", fontsize=14, fontweight="bold", loc="left", pad=12)
    ax_tbl.text(0, 1.02, subtitle, transform=ax_tbl.transAxes, color="#8b95a8", fontsize=9)

    if not top:
        ax_tbl.text(
            0.5,
            0.5,
            "No paper books yet\n/track a filer",
            ha="center",
            va="center",
            color="#8b95a8",
            fontsize=12,
            transform=ax_tbl.transAxes,
        )
        ax_bar.axis("off")
    else:
        cell = []
        colors = []
        for r in top:
            ret = r.get("return_pct")
            if ret is None:
                ret = r.get("total_return_pct")
            eq = r.get("equity")
            if eq is None:
                eq = r.get("final_equity")
            ret_s = f"{float(ret):+.1f}%" if ret is not None else "—"
            eq_s = f"${float(eq):,.0f}" if eq is not None else "—"
            fills = r.get("fills") if r.get("fills") is not None else r.get("fills_executed", "—")
            cell.append(
                [
                    str(r.get("rank") or ""),
                    _truncate(str(r.get("filer") or ""), 24),
                    ret_s,
                    eq_s,
                    str(fills),
                ]
            )
            colors.append("#3dd68c" if (ret is not None and float(ret) >= 0) else "#f31260")

        table = ax_tbl.table(
            cellText=cell,
            colLabels=["#", "Filer", "Return", "Equity", "Fills"],
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.15, 1.45)
        for (row, col), cell_obj in table.get_celld().items():
            cell_obj.set_edgecolor("#2a3348")
            if row == 0:
                cell_obj.set_facecolor("#1a2030")
                cell_obj.set_text_props(color="#8b95a8", weight="bold")
            else:
                cell_obj.set_facecolor("#141822")
                c = "#e8ecf4" if col != 2 else colors[row - 1]
                cell_obj.set_text_props(color=c)

        names = [_truncate(str(r.get("filer") or ""), 16) for r in top]
        vals = []
        for r in top:
            ret = r.get("return_pct")
            if ret is None:
                ret = r.get("total_return_pct") or 0
            vals.append(float(ret))
        bar_colors = ["#3dd68c" if v >= 0 else "#f31260" for v in vals]
        ax_bar.barh(list(reversed(names)), list(reversed(vals)), color=list(reversed(bar_colors)))
        ax_bar.axvline(0, color="#2a3348", linewidth=1)
        ax_bar.set_xlabel("Return %", color="#8b95a8")
        ax_bar.set_title("Return % by filer", color="#e8ecf4", fontsize=11, loc="left")

    fig.text(
        0.5,
        0.01,
        "Delayed public PTRs · not politicians' real P&L · paper research only",
        ha="center",
        color="#8b95a8",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


def _render_pillow(
    rows: list[dict[str, Any]],
    *,
    title: str,
    subtitle: str,
    path: Path,
) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    top = rows[:12]
    w, h = 900, 120 + max(1, len(top)) * 36 + 40
    img = Image.new("RGB", (w, h), "#0b0d12")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = font_sm = font_b = ImageFont.load_default()

    draw.text((24, 20), title, fill="#e8ecf4", font=font_b)
    draw.text((24, 52), subtitle, fill="#8b95a8", font=font_sm)
    y = 90
    draw.text(
        (24, y),
        "#   Filer                      Return    Equity    Fills",
        fill="#8b95a8",
        font=font_sm,
    )
    y += 28
    if not top:
        draw.text((24, y), "No paper books — /track a filer", fill="#8b95a8", font=font)
    for r in top:
        ret = r.get("return_pct")
        if ret is None:
            ret = r.get("total_return_pct")
        eq = r.get("equity")
        if eq is None:
            eq = r.get("final_equity")
        ret_s = f"{float(ret):+.1f}%" if ret is not None else "—"
        color = "#3dd68c" if (ret is not None and float(ret) >= 0) else "#f31260"
        line = (
            f"{str(r.get('rank') or ''):>2}  {_truncate(str(r.get('filer') or ''), 24):<24}  "
            f"{ret_s:>8}  ${float(eq or 0):>8,.0f}  {r.get('fills') or r.get('fills_executed') or '—'}"
        )
        draw.text((24, y), line, fill=color if ret is not None else "#e8ecf4", font=font_sm)
        y += 32
    img.save(path, format="PNG")
    return path


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    """Minimal valid RGB PNG (stdlib only)."""
    r, g, b = rgb
    raw = b""
    row = b"\x00" + bytes([r, g, b]) * width
    raw = row * height
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", compressed)
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _render_stdlib(
    rows: list[dict[str, Any]],
    *,
    title: str,
    subtitle: str,
    path: Path,
) -> Path:
    """No matplotlib/Pillow: write solid PNG + human-readable .txt next to it."""
    top = rows[:12]
    lines = [title, subtitle, "", "#  Filer                      Return    Equity    Fills"]
    if not top:
        lines.append("(no paper books — /track a filer)")
    for i, r in enumerate(top, 1):
        ret = r.get("return_pct")
        if ret is None:
            ret = r.get("total_return_pct")
        eq = r.get("equity")
        if eq is None:
            eq = r.get("final_equity")
        ret_s = f"{float(ret):+.1f}%" if ret is not None else "—"
        lines.append(
            f"{i:>2}  {_truncate(str(r.get('filer') or ''), 24):<24}  "
            f"{ret_s:>8}  ${float(eq or 0):>8,.0f}  "
            f"{r.get('fills') or r.get('fills_executed') or '—'}"
        )
    lines.append("")
    lines.append("Delayed public PTRs · paper research only")
    path.with_suffix(".txt").write_text("\n".join(lines))
    _write_solid_png(path, 64, 64, (11, 13, 18))
    return path


def build_and_save_leaderboard_image(*, fetch_prices: bool = True) -> tuple[Path, dict[str, Any]]:
    from src.copytrade.leaderboard import ranked_leaderboard

    board = ranked_leaderboard(fetch_prices=fetch_prices)
    path = render_leaderboard_png(
        board.get("leaderboard") or [],
        title="Trading Core · paper books",
        subtitle=f"{board.get('generated_at', '')} · ranked by return %",
    )
    return path, board
