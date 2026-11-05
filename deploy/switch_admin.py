"""Small admin helper for a Switch server's Gateway API (run on the Switch box).

  python deploy/switch_admin.py policies --intake bakeoff-intake --merge-extra-users U123 U456
  python deploy/switch_admin.py rooms
  python deploy/switch_admin.py read ROOM_ID [--last 20]
  python deploy/switch_admin.py say ROOM_ID "@bakeoff-merge pick #2" --mention bakeoff-merge
  python deploy/switch_admin.py approvals
  SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-... python deploy/switch_admin.py slack
  python deploy/switch_admin.py answer AGENT_ID SESSION_ID REQUEST_ID OPTION_ID

Credentials: GATEWAY_ADMIN_EMAIL / GATEWAY_ADMIN_PASSWORD (read from ~/switch-server/.env when unset).
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

import httpx

GW = os.environ.get("SWITCH_GATEWAY_URL", "http://127.0.0.1:3000/gateway")
OWNER_RULE = {"rooms": "*", "room_groups": "*", "users": [], "agents": [], "owner": True,
              "owner_agents": True, "platform": False}


def _creds() -> tuple[str, str]:
    env = {}
    p = Path.home() / "switch-server" / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return (os.environ.get("GATEWAY_ADMIN_EMAIL") or env["GATEWAY_ADMIN_EMAIL"],
            os.environ.get("GATEWAY_ADMIN_PASSWORD") or env["GATEWAY_ADMIN_PASSWORD"])


def client() -> httpx.Client:
    c = httpx.Client(base_url=GW, timeout=60)
    email, pw = _creds()
    r = c.post("/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return c


def agent_ids(c: httpx.Client) -> dict[str, str]:
    r = c.get("/agents")
    r.raise_for_status()
    data = r.json()
    items = data.get("agents", data) if isinstance(data, dict) else data
    return {a["name"]: a["id"] for a in items}


def cmd_policies(c, a):
    ids = agent_ids(c)
    intake = ids.get(a.intake, a.intake)
    # Readers answer any person in the room (questions are welcome) and the intake bot (the kickoff).
    readers_policy = {"rules": [OWNER_RULE, {**OWNER_RULE, "owner": False, "owner_agents": False,
                                             "users": "*", "agents": [intake]}]}
    for name in ("bakeoff-checker", "bakeoff-second"):
        r = c.put(f"/agents/{ids[name]}/addressing-policy", json={"policy": readers_policy})
        print(name, r.status_code)
    # The merge agent answers its owner (the maintainer) and the listed maintainers only; agents may
    # not instruct it, so a reader can never trigger a merge.
    rules = [{**OWNER_RULE, "owner_agents": False}]
    ext = c.get("/auth/session").json()  # noqa: F841 (session check)
    if a.merge_extra_users:
        rules.append({**OWNER_RULE, "owner": False, "owner_agents": False, "users": a.merge_extra_users, "agents": []})
    r = c.put(f"/agents/{ids['bakeoff-merge']}/addressing-policy", json={"policy": {"rules": rules}})
    print("bakeoff-merge", r.status_code, r.text[:200] if r.status_code >= 400 else "")


def cmd_rooms(c, a):
    r = c.get("/rooms")
    data = r.json()
    for room in data.get("rooms", data) if isinstance(data, dict) else data:
        print(room.get("id"), room.get("name"))


def cmd_read(c, a):
    r = c.get(f"/chats/{a.room}/messages")
    msgs = r.json().get("messages", [])
    for m in msgs[-a.last:]:
        s = m.get("sender", {})
        print(f"[{m.get('seq')}] {s.get('name')} ({s.get('kind')}): {m.get('body', '')[:a.width]}")


def cmd_say(c, a):
    ids = agent_ids(c) if a.mention else {}
    body = {"requestId": str(uuid.uuid4()), "body": a.text, "mentionAgentIds": [ids[m] for m in a.mention]}
    r = c.post(f"/chats/{a.room}/messages", json=body)
    print(r.status_code, r.text[:300])


def cmd_join(c, a):
    me = c.get("/auth/session").json()
    uid = me.get("user", me).get("id")
    print(c.post(f"/chats/{a.room}/members", json={"userId": uid}).status_code)


def cmd_slack(c, a):
    """Connect a Slack workspace (Socket Mode) as the default messaging app. Tokens come from the environment."""
    bot, app = os.environ["SLACK_BOT_TOKEN"], os.environ["SLACK_APP_TOKEN"]
    r = c.post("/collaborations/setup/slack/check", json={"bot_token": bot, "app_token": app})
    print("check", r.status_code, r.text[:300])
    r.raise_for_status()
    ws = a.workspace or r.json().get("workspace_id") or r.json().get("team_id")
    r = c.post("/collaborations", json={
        "bridge_type": "slack", "display_name": a.name, "set_as_default": True, "channel_creation_enabled": True,
        "connection_config": {"bot_token": bot, "app_token": app, "workspace_id": ws}})
    print("connect", r.status_code, r.text[:300])


def cmd_users(c, a):
    """Chat accounts Switch has seen on a bridge, with the ids addressing rules use."""
    for path in ("/users", "/collaborations"):
        r = c.get(path)
        print(path, r.status_code, json.dumps(r.json(), indent=1)[:2500])
    if a.bridge:
        r = c.get(f"/collaborations/{a.bridge}/identities/unconfirmed")
        print("unconfirmed", r.status_code, r.text[:2500])


def cmd_approvals(c, a):
    print(json.dumps(c.get("/agent-sessions/approvals").json(), indent=1)[:4000])


def cmd_answer(c, a):
    r = c.post(f"/agent-sessions/{a.agent}/{a.session}/approvals/{a.request}/answer", json={"answer": a.option})
    print(r.status_code, r.text[:400])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("policies"); p.add_argument("--intake", default="bakeoff-intake")
    p.add_argument("--merge-extra-users", nargs="*", default=[])
    sub.add_parser("rooms")
    p = sub.add_parser("read"); p.add_argument("room"); p.add_argument("--last", type=int, default=30)
    p.add_argument("--width", type=int, default=400)
    p = sub.add_parser("say"); p.add_argument("room"); p.add_argument("text"); p.add_argument("--mention", nargs="*", default=[])
    p = sub.add_parser("join"); p.add_argument("room")
    sub.add_parser("approvals")
    p = sub.add_parser("slack"); p.add_argument("--name", default="Slack"); p.add_argument("--workspace", default="")
    p = sub.add_parser("users"); p.add_argument("--bridge", default="")
    p = sub.add_parser("answer")
    for k in ("agent", "session", "request", "option"):
        p.add_argument(k)
    a = ap.parse_args()
    globals()[f"cmd_{a.cmd}"](client(), a)


if __name__ == "__main__":
    main()
