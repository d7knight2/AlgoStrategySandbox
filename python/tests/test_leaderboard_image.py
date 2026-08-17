"""Leaderboard PNG unit test — no network, no AI."""

from __future__ import annotations

from pathlib import Path


def test_render_leaderboard_png(tmp_path):
    from src.copytrade.leaderboard_image import render_leaderboard_png

    out = tmp_path / "lb.png"
    path = render_leaderboard_png(
        [
            {"filer": "Nancy Pelosi", "return_pct": 4.5, "equity": 10450},
            {"filer": "Tommy Tuberville", "return_pct": -1.2, "equity": 9880},
        ],
        out_path=out,
    )
    assert Path(path).is_file()
    assert Path(path).stat().st_size > 100
