import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("brief_check", Path(__file__).parent.parent / "scripts" / "brief_check.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)


def test_placeholder_page_passes_and_dark_mode_is_required():
    html = Path("site/index.html").read_text()
    assert all(ok for _, ok in bc.checks(html))
    assert dict(bc.checks(html.replace("prefers-color-scheme", "")))["has a dark mode (prefers-color-scheme)"] is False


def test_external_script_is_caught():
    html = '<script src="https://cdn.x/y.js"></script>'
    assert dict(bc.checks(html))["no external scripts"] is False
