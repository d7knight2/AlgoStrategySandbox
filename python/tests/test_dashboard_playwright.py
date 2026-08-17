"""Optional browser UI tests (Playwright).

Not part of default unit suite (ui + integration). No AI calls.

  pip install playwright && playwright install chromium
  pytest tests/test_dashboard_playwright.py -v -m ui
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

pytestmark = [pytest.mark.ui, pytest.mark.integration]


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
    for _ in range(50):
        try:
            import urllib.request

            urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield "http://127.0.0.1:8765"
    server.should_exit = True


def test_dashboard_renders_shell(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/dashboard", wait_until="networkidle", timeout=30000)
        assert page.locator("h1").count() >= 1
        assert "Paper" in page.locator("h1").inner_text()
        browser.close()
