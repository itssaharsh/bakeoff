"""Deterministic checks for the landing-page brief (issue: design the Bakeoff landing page).

  uv run python scripts/brief_check.py site/index.html

Each line is one Done-when item code can decide; exit 1 if any fails. The rest of the
brief (does a stranger get it in five seconds?) is for the readers and the friends.
"""

import re
import sys
from pathlib import Path

SENTENCE = "When several pull requests fix one issue"


def checks(html: str) -> list[tuple[str, bool]]:
    size = len(html.encode())
    return [
        (f"under 60 KB ({size} bytes)", size < 60_000),
        ("no external scripts", not re.search(r"<script[^>]+src=[\"']?https?:", html, re.I)),
        ("no external stylesheets or fonts", not re.search(r"<link[^>]+href=[\"']?https?:", html, re.I)),
        ("has a dark mode (prefers-color-scheme)", "prefers-color-scheme" in html),
        (f'opens with "{SENTENCE}…"', SENTENCE.lower() in html.lower()),
        ("links to the repository", "github.com/itssaharsh/bakeoff" in html),
        ("has a viewport meta for phones", 'name="viewport"' in html),
    ]


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "site/index.html")
    results = checks(path.read_text())
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
