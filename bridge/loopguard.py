"""Layer-2 loop prevention: per-thread consecutive bot-turn counter."""

_depth: dict[str, int] = {}
HALT_AT: int = 3


def record_turn(root_id: str, is_from_bot: bool) -> bool:
    """Record a message turn and return True if the bridge should HALT.

    A human turn always resets the counter to 0 and never triggers a halt.
    Consecutive bot turns increment the counter; reaching HALT_AT returns True.
    """
    if not is_from_bot:
        _depth[root_id] = 0
        return False
    _depth[root_id] = _depth.get(root_id, 0) + 1
    return _depth[root_id] >= HALT_AT
