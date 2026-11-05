"""Contest state shared by the watcher and every agent's MCP server (one JSON file, locked)."""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .matrix import VERDICTS, Reading


def default_path() -> Path:
    return Path(os.environ.get("BAKEOFF_STATE", Path.home() / ".bakeoff" / "state.json"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked(self, write: bool):
        lock = self.path.with_suffix(".lock")
        with open(lock, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            data = json.loads(self.path.read_text()) if self.path.exists() and self.path.stat().st_size else {}
            data.setdefault("contests", {})
            yield data
            if write:
                tmp = self.path.with_suffix(f".tmp{os.getpid()}{time.time_ns()}")
                tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
                os.replace(tmp, self.path)

    @staticmethod
    def _key(repo: str, issue: int) -> str:
        return f"{repo}#{issue}"

    def contest(self, repo: str, issue: int) -> dict | None:
        with self._locked(False) as d:
            return d["contests"].get(self._key(repo, issue))

    def contests(self) -> dict:
        with self._locked(False) as d:
            return dict(d["contests"])

    def open_contest(self, repo: str, issue: int, room_id: str, prs: list[int]) -> None:
        with self._locked(True) as d:
            c = d["contests"].setdefault(self._key(repo, issue), {"readings": []})
            c.update({"repo": repo, "issue": issue, "room_id": room_id, "prs": sorted(prs),
                      "opened_at": c.get("opened_at") or _now()})

    def set_prs(self, repo: str, issue: int, prs: list[int]) -> None:
        with self._locked(True) as d:
            d["contests"][self._key(repo, issue)]["prs"] = sorted(prs)

    def add_reading(self, repo: str, issue: int, agent: str, pr: int, item: int, verdict: str, evidence: str) -> None:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}, not {verdict!r}")
        with self._locked(True) as d:
            c = d["contests"].setdefault(self._key(repo, issue), {"repo": repo, "issue": issue, "readings": []})
            c.setdefault("readings", []).append({"agent": agent, "pr": int(pr), "item": int(item),
                                                 "verdict": verdict, "evidence": evidence[:400], "at": _now()})

    def readings(self, repo: str, issue: int) -> list[Reading]:
        c = self.contest(repo, issue) or {}
        return [Reading(r["agent"], r["pr"], r["item"], r["verdict"], r.get("evidence", ""))
                for r in c.get("readings", [])]

    def decide(self, repo: str, issue: int, winner: int, decided_by: str) -> bool:
        """Record the pick once. False when the contest was already decided."""
        with self._locked(True) as d:
            c = d["contests"].setdefault(self._key(repo, issue), {"repo": repo, "issue": issue, "readings": []})
            if c.get("winner"):
                return False
            c.update({"winner": int(winner), "decided_by": decided_by, "decided_at": _now()})
            return True

    def undecide(self, repo: str, issue: int) -> None:
        with self._locked(True) as d:
            c = d["contests"].get(self._key(repo, issue), {})
            for k in ("winner", "decided_by", "decided_at"):
                c.pop(k, None)

    def note(self, repo: str, issue: int, **fields) -> None:
        with self._locked(True) as d:
            d["contests"].setdefault(self._key(repo, issue), {"readings": []}).update(fields)
