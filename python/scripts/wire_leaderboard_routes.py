from pathlib import Path

p = Path(__file__).resolve().parents[1] / "src" / "main.py"
t = p.read_text()
if "copytrade/leaderboard" in t:
    print("already wired")
else:
    insert = """

@app.get("/copytrade/leaderboard")
def copytrade_leaderboard(fetch_prices: bool = True) -> dict[str, Any]:
    from src.copytrade.leaderboard import ranked_leaderboard

    return ranked_leaderboard(fetch_prices=fetch_prices)


@app.get("/copytrade/leaderboard/charts")
def copytrade_leaderboard_charts(max_filers: int = Query(8, ge=1, le=20)) -> dict[str, Any]:
    from src.copytrade.leaderboard import multi_equity_series

    return multi_equity_series(max_filers=max_filers)


@app.get("/copytrade/equity/{filer}")
def copytrade_equity(filer: str) -> dict[str, Any]:
    from src.copytrade.leaderboard import equity_series_for_filer

    return equity_series_for_filer(filer)


@app.get("/copytrade/backtest/{filer}")
def copytrade_backtest_filer(
    filer: str,
    lookback_days: int = Query(365, ge=30, le=900),
    starting_cash: float = Query(10000.0, gt=0),
    notional_per_trade: float = Query(1000.0, gt=0),
    use_disclosure_date: bool = True,
) -> dict[str, Any]:
    from src.copytrade.copy_backtest import backtest_copy_filer

    try:
        return backtest_copy_filer(
            filer,
            lookback_days=lookback_days,
            starting_cash=starting_cash,
            notional_per_trade=notional_per_trade,
            use_disclosure_date=use_disclosure_date,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/copytrade/backtest/leaderboard")
def copytrade_backtest_board(
    lookback_days: int = Query(365, ge=30, le=900),
    starting_cash: float = Query(10000.0, gt=0),
    notional_per_trade: float = Query(1000.0, gt=0),
) -> dict[str, Any]:
    from src.config import settings as _settings
    from src.copytrade.copy_backtest import backtest_leaderboard

    filers = [x.strip() for x in (_settings.copytrade_filers or "").split(",") if x.strip()]
    if not filers:
        filers = ["Nancy Pelosi", "Tommy Tuberville", "Josh Gottheimer"]
    try:
        return backtest_leaderboard(
            filers,
            lookback_days=lookback_days,
            starting_cash=starting_cash,
            notional_per_trade=notional_per_trade,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request):
    return templates.TemplateResponse(request, "leaderboard.html")

"""
    anchor = '@app.get("/dashboard", response_class=HTMLResponse)'
    if anchor not in t:
        raise SystemExit("anchor missing")
    t = t.replace(anchor, insert + anchor, 1)
    if '"leaderboard"' not in t:
        t = t.replace(
            '"dashboard": "/dashboard",',
            '"dashboard": "/dashboard",\n            "leaderboard": "/leaderboard",',
        )
    p.write_text(t)
    print("wired ok")
