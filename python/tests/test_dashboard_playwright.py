"""Optional browser UI tests (Playwright).

Run only when playwright is installed and browsers are available:

  pip install playwright
  playwright install chromium
  pytest tests/test_dashboard_playwright.py -v

These start the FastAPI app via ASGI and drive a headless browser.
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright


@pytest.fixture(scope="module")
def live_server():
    """Run uvicorn in a background thread."""
    import threading
    import time

    import uvicorn

    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # wait for boot
    for _ in range(50):
        try:
            import urllib.request

            urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield "http://127.0.0.1:8765"
    server.should_exit = True


@pytest.mark.ui
def test_dashboard_renders_shell(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/dashboard", wait_until="networkidle", timeout=30000)
        assert page.locator("h1").count() >= 1
        assert "Paper Portfolio" in page.locator("h1").inner_text()
        assert page.locator("#candleHost").count() == 1
        assert page.locator("#symbolSelect").count() == 1
        assert page.locator("#equity").count() == 1
        # controls present
        assert page.get_by_role("button", name="Refresh").count() >= 1
        assert page.get_by_role("button", name="STOP").count() >= 1
        browser.close()


@pytest.mark.ui
def test_symbol_selector_options(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/dashboard", wait_until="domcontentloaded", timeout=30000)
        options = page.locator("#symbolSelect option").all_inner_texts()
        assert "SPY" in options
        assert "QQQ" in options
        browser.close()


@pytest.mark.ui
def test_range_buttons_exist(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/dashboard", wait_until="domcontentloaded", timeout=30000)
        for label in ("1M", "3M", "6M", "1Y"):
            assert page.get_by_role("button", name=label).count() >= 1
        browser.close()
