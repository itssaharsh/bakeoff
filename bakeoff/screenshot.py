"""Pictures of each candidate, for contests whose scope is a web page.

The watcher renders the scoped HTML file at each PR's head commit in a headless
browser and posts the pictures into the room, so the people deciding see every
candidate side by side without checking anything out.
"""

from __future__ import annotations


def render(html: str, width: int = 1280, height: int = 800, dark: bool = False) -> bytes:
    from playwright.sync_api import sync_playwright  # optional dependency group "screens"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": height},
                                    color_scheme="dark" if dark else "light")
            page.route("**/*", lambda route: route.abort() if route.request.url.startswith("http") else route.continue_())
            page.set_content(html, wait_until="load", timeout=15_000)
            return page.screenshot(full_page=False, type="png")
        finally:
            browser.close()


def html_scope(scope: list[str]) -> str | None:
    """The first scoped path that is a web page, or None."""
    return next((s for s in scope if s.endswith((".html", ".htm"))), None)
