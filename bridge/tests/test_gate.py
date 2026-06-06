import pytest
from unittest.mock import patch
import os

os.environ.setdefault("MM_BOT_TOKEN", "test-token")
os.environ.setdefault("MM_BOT_USER_ID", "bot-user-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "demo-ch")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://graphn.test")
os.environ.setdefault("GRAPHN_API_KEY", "test-key")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from bridge.gate import decide
from bridge.models import Message, VerdictKind, GraphNResult


def msg(**overrides) -> Message:
    base = dict(
        id="p1", channel_id="c1", root_id="", user_id="u1",
        text="When are office hours?", is_from_bot=False,
    )
    return Message(**{**base, **overrides})


def pub_ok(confidence=0.9) -> GraphNResult:
    return GraphNResult(
        text="Office hours Mon/Wed 2-4pm.", grounded=True,
        confidence=confidence, sources=["chunk_001"], private_hits=0,
    )


def pub_miss() -> GraphNResult:
    return GraphNResult(
        text="", grounded=False, confidence=0.1, sources=[], private_hits=0,
    )


def priv_ok(private_hits=1) -> GraphNResult:
    return GraphNResult(
        text="Your salary is $120k.", grounded=True,
        confidence=0.95, sources=["pub_c", "priv_c"], private_hits=private_hits,
    )


def test_bot_origin_forces_draft_without_calling_graphn():
    m = msg(is_from_bot=True)
    with patch("bridge.gate.graphn_client.run_workflow") as mock_run:
        verdict = decide(m)
    assert verdict.kind == VerdictKind.DRAFT
    assert verdict.reason == "bot origin"
    mock_run.assert_not_called()


def test_auto_send_when_public_grounded_and_confident():
    with patch("bridge.gate.graphn_client.run_workflow", return_value=pub_ok()):
        verdict = decide(msg())
    assert verdict.kind == VerdictKind.AUTO_SEND
    assert verdict.reply == "Office hours Mon/Wed 2-4pm."


def test_draft_when_public_not_grounded():
    with patch("bridge.gate.graphn_client.run_workflow",
               side_effect=[pub_miss(), priv_ok()]):
        verdict = decide(msg(text="What is my salary?"))
    assert verdict.kind == VerdictKind.DRAFT
    assert "1 private sources" in verdict.reason


def test_draft_when_public_confidence_below_threshold():
    with patch("bridge.gate.graphn_client.run_workflow",
               side_effect=[pub_ok(confidence=0.3), priv_ok()]):
        verdict = decide(msg(text="What is in my notes?"))
    assert verdict.kind == VerdictKind.DRAFT


def test_private_escalation_calls_both_workflows():
    with patch("bridge.gate.graphn_client.run_workflow",
               side_effect=[pub_miss(), priv_ok(private_hits=2)]) as mock_run:
        decide(msg(text="Tell me my salary"))
    assert mock_run.call_count == 2


def test_auto_send_calls_only_public_workflow():
    with patch("bridge.gate.graphn_client.run_workflow",
               return_value=pub_ok()) as mock_run:
        decide(msg())
    assert mock_run.call_count == 1


def test_provenance_attached_on_auto_send():
    with patch("bridge.gate.graphn_client.run_workflow", return_value=pub_ok()):
        verdict = decide(msg())
    assert verdict.provenance == ["chunk_001"]
