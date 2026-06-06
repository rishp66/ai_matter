from dataclasses import dataclass, field
from enum import Enum


class VerdictKind(str, Enum):
    AUTO_SEND = "AUTO_SEND"
    DRAFT = "DRAFT"


@dataclass
class Message:
    id: str
    channel_id: str
    root_id: str
    user_id: str
    text: str
    is_from_bot: bool


@dataclass
class GraphNResult:
    text: str
    grounded: bool
    confidence: float
    sources: list[str]
    private_hits: int = 0


@dataclass
class Verdict:
    kind: VerdictKind
    reply: str = ""
    reason: str = ""
    provenance: list[str] = field(default_factory=list)
