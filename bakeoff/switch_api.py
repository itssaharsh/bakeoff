"""Talk to a Switch server as the bakeoff-intake bot agent (Switch agent bridge API)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "bakeoff.room.yaml"


class SwitchError(RuntimeError):
    pass


class Switch:
    """base_url: the Switch API (http://127.0.0.1:8000). agent_id / api_key: bakeoff-intake's credentials."""

    def __init__(self, base_url: str | None = None, agent_id: str | None = None, api_key: str | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.base = (base_url or os.environ.get("SWITCH_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.agent_id = agent_id or os.environ.get("BAKEOFF_INTAKE_AGENT_ID", "")
        key = api_key or os.environ.get("BAKEOFF_INTAKE_API_KEY", "")
        self.http = httpx.Client(base_url=self.base, timeout=60, transport=transport,
                                 headers={"Authorization": f"Bearer {key}"} if key else {})

    def _post(self, path: str, payload: dict) -> dict:
        r = self.http.post(path, json=payload)
        if r.status_code >= 400:
            raise SwitchError(f"{path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def create_room_from_template(self, inputs: dict, yaml_text: str | None = None) -> str:
        """Create the contest room from the Bakeoff template; returns the room id."""
        text = yaml_text if yaml_text is not None else TEMPLATE.read_text()
        out = self._post(f"/agents/{self.agent_id}/ops/create_room_from_yaml",
                         {"yaml": text, "inputs": inputs})
        room = _find_room_id(out)
        if not room:
            raise SwitchError(f"create_room_from_yaml returned no room id: {str(out)[:300]}")
        return room

    def post_files(self, room_id: str, files: list[tuple[str, bytes, str]], caption: str = "") -> dict:
        r = self.http.post(f"/agents/{self.agent_id}/rooms/{room_id}/media",
                           files=[("files", f) for f in files], data={"caption": caption} if caption else None)
        if r.status_code >= 400:
            raise SwitchError(f"media upload -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def post(self, room_id: str, content: str) -> str:
        out = self._post(f"/agents/{self.agent_id}/message", {"room_id": room_id, "content": content})
        return str(out.get("event_id", ""))


def _find_room_id(obj) -> str:
    """The ops result nests the created room differently across versions; find its id."""
    if isinstance(obj, dict):
        for k in ("room_id", "roomId"):
            if isinstance(obj.get(k), str):
                return obj[k]
        if isinstance(obj.get("room"), dict) and isinstance(obj["room"].get("id"), str):
            return obj["room"]["id"]
        for v in obj.values():
            if (found := _find_room_id(v)):
                return found
    if isinstance(obj, list):
        for v in obj:
            if (found := _find_room_id(v)):
                return found
    return ""
