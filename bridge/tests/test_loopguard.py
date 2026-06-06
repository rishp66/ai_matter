import os
os.environ.setdefault("MM_BOT_TOKEN", "fake-token")
os.environ.setdefault("MM_BOT_USER_ID", "fake-bot-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "fake-channel")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://fake")
os.environ.setdefault("GRAPHN_API_KEY", "fake-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from bridge import loopguard


def _clear():
    loopguard._depth.clear()


def test_human_turn_never_halts():
    _clear()
    assert loopguard.record_turn("root-1", is_from_bot=False) is False


def test_human_turn_resets_counter():
    _clear()
    # Two bot turns, then a human turn — human resets the count
    loopguard.record_turn("root-2", is_from_bot=True)
    loopguard.record_turn("root-2", is_from_bot=True)
    loopguard.record_turn("root-2", is_from_bot=False)
    # depth should be 0 now; a bot turn after this should NOT halt
    assert loopguard.record_turn("root-2", is_from_bot=True) is False


def test_first_bot_turn_does_not_halt():
    _clear()
    assert loopguard.record_turn("root-3", is_from_bot=True) is False


def test_second_bot_turn_does_not_halt():
    _clear()
    loopguard.record_turn("root-4", is_from_bot=True)
    assert loopguard.record_turn("root-4", is_from_bot=True) is False


def test_third_consecutive_bot_turn_halts():
    _clear()
    loopguard.record_turn("root-5", is_from_bot=True)
    loopguard.record_turn("root-5", is_from_bot=True)
    assert loopguard.record_turn("root-5", is_from_bot=True) is True


def test_human_turn_between_bot_turns_resets():
    _clear()
    # Bot turn 1 + 2, then human, then bot turn 1 again — should NOT halt
    loopguard.record_turn("root-6", is_from_bot=True)
    loopguard.record_turn("root-6", is_from_bot=True)
    loopguard.record_turn("root-6", is_from_bot=False)  # reset
    loopguard.record_turn("root-6", is_from_bot=True)   # 1 again
    loopguard.record_turn("root-6", is_from_bot=True)   # 2
    assert loopguard.record_turn("root-6", is_from_bot=True) is True  # 3 → halt
