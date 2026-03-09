"""Data types for the program service layer."""

from dataclasses import dataclass, field


@dataclass
class EventModifiers:
    """Modifiers applied by active promotional events."""
    multiplier: float = 1.0
    bonus: int = 0


@dataclass
class ProgressResult:
    """Result of adding progress to an enrollment."""
    enrollment: dict
    delta: int  # actual amount added (after modifiers)
    value_before: int
    value_after: int
    milestones: list[str] = field(default_factory=list)
    reward_earned: bool = False
    transaction_id: str | None = None


@dataclass
class RedeemResult:
    """Result of redeeming a reward."""
    enrollment: dict
    value_before: int
    value_after: int
    reward_name: str = ""
    transaction_id: str | None = None
