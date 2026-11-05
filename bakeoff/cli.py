"""bakeoff CLI: matrix, mcp, watch."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict


def _matrix(args) -> int:
    from .github import GitHub, collect_contest
    from .matrix import render_text
    from .state import Store

    c = collect_contest(GitHub(args.repo), args.issue)
    if not c.prs:
        print(f"Issue #{args.issue} in {args.repo} has no open pull requests that close it.", file=sys.stderr)
        return 1
    readings = Store().readings(args.repo, args.issue)
    m = c.matrix(readings)
    if args.json:
        print(json.dumps(asdict(m), indent=2))
    else:
        print(render_text(m))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bakeoff", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("matrix", help="print the contest matrix for OWNER/REPO ISSUE")
    m.add_argument("repo")
    m.add_argument("issue", type=int)
    m.add_argument("--json", action="store_true")
    sub.add_parser("mcp", help="run the Bakeoff MCP server on stdio")
    w = sub.add_parser("watch", help="open a Switch room for every contested issue")
    w.add_argument("repo", nargs="+")
    w.add_argument("--interval", type=int, default=30)
    w.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "matrix":
        return _matrix(args)
    if args.cmd == "mcp":
        from .mcp_server import run
        run()
        return 0
    if args.cmd == "watch":
        from .watch import run_watch
        return run_watch(args.repo, interval=args.interval, once=args.once)
    return 2


if __name__ == "__main__":
    sys.exit(main())
