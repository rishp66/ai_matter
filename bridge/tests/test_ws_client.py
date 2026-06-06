import json
import pytest
from unittest.mock import patch, MagicMock

# Patch config before importing ws_client so KeyError doesn't fire
with patch.dict("os.environ", {
    "MM_BOT_TOKEN": "test-token",
    "MM_BOT_USER_ID": "bot-user-id",
    "MM_DEMO_CHANNEL_ID": "demo-ch",
    "GRAPHN_GATEWAY_URL": "http://graphn.test",
    "GRAPHN_API_KEY": "test-key",
    "GRAPHN_WORKSPACE_ID": "ws_test",
    "GRAPHN_WF_PUBLIC": "wf-pub",
    "GRAPHN_WF_PRIVATE": "wf-priv",
}):
    from bridge.ws_client import parse_posted_event
from bridge.models import Message


def make_post(**overrides) -> str:
    base = {
        "id": "p1",
        "channel_id": "c1",
        "root_id": "",
        "user_id": "u1",
        "message": "hello",
        "type": "",
        "props": {},
    }
    return json.dumps({**base, **overrides})


def make_event(post_json: str) -> dict:
    return {"event": "posted", "data": {"post": post_json}}


def test_parses_human_post():
    msg = parse_posted_event(make_event(make_post()))
    assert msg is not None
    assert msg.text == "hello"
    assert msg.is_from_bot is False
    assert msg.channel_id == "c1"
    assert msg.user_id == "u1"


def test_marks_bot_post_as_from_bot():
    post_json = make_post(props={"from_bot": "true"})
    msg = parse_posted_event(make_event(post_json))
    assert msg is not None
    assert msg.is_from_bot is True


def test_returns_none_for_non_posted_event():
    assert parse_posted_event({"event": "channel_viewed", "data": {}}) is None


def test_returns_none_for_system_message():
    post_json = make_post(type="system_join_channel")
    assert parse_posted_event(make_event(post_json)) is None


def test_root_id_preserved():
    post_json = make_post(root_id="r1")
    msg = parse_posted_event(make_event(post_json))
    assert msg.root_id == "r1"
