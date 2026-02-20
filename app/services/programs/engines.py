"""
Program engines implementing the strategy pattern for different program types.

Each engine handles type-specific progress logic (add, redeem, milestone detection).
"""

from abc import ABC, abstractmethod
import logging

from app.services.programs.types import EventModifiers

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """Abstract base class for program type engines."""

    @abstractmethod
    def add_progress(
        self,
        enrollment: dict,
        config: dict,
        amount: int = 1,
        modifiers: EventModifiers | None = None,
    ) -> tuple[dict, int, list[str], bool]:
        """
        Add progress to an enrollment.

        Returns:
            (new_progress, actual_delta, milestones_triggered, reward_earned)
        """
        ...

    @abstractmethod
    def redeem(
        self,
        enrollment: dict,
        config: dict,
        reward_index: int = 0,
    ) -> tuple[dict, str]:
        """
        Redeem a reward from an enrollment.

        Returns:
            (new_progress, reward_name)
        """
        ...

    @abstractmethod
    def check_milestones(
        self,
        enrollment: dict,
        config: dict,
        value_before: int,
        value_after: int,
    ) -> list[str]:
        """Check for milestone triggers based on progress change."""
        ...

    @abstractmethod
    def get_display_value(self, enrollment: dict, config: dict) -> str:
        """Get display string for current progress (e.g. '7 / 10')."""
        ...

    @abstractmethod
    def can_redeem(self, enrollment: dict, config: dict) -> bool:
        """Check if enrollment is eligible for redemption."""
        ...


class StampEngine(BaseEngine):
    """Engine for stamp-based loyalty programs."""

    def add_progress(
        self,
        enrollment: dict,
        config: dict,
        amount: int = 1,
        modifiers: EventModifiers | None = None,
    ) -> tuple[dict, int, list[str], bool]:
        modifiers = modifiers or EventModifiers()
        progress = dict(enrollment.get("progress", {}))
        total_stamps = config.get("total_stamps", 10)

        current = progress.get("stamps", 0)
        # Apply modifiers
        effective_amount = int(amount * modifiers.multiplier) + modifiers.bonus
        new_value = min(current + effective_amount, total_stamps)
        actual_delta = new_value - current

        progress["stamps"] = new_value
        reward_earned = new_value >= total_stamps

        milestones = self.check_milestones(enrollment, config, current, new_value)

        return progress, actual_delta, milestones, reward_earned

    def redeem(
        self,
        enrollment: dict,
        config: dict,
        reward_index: int = 0,
    ) -> tuple[dict, str]:
        progress = dict(enrollment.get("progress", {}))
        auto_reset = config.get("auto_reset_on_redeem", True)

        reward_name = config.get("reward_name", "Reward")

        if auto_reset:
            progress["stamps"] = 0

        return progress, reward_name

    def check_milestones(
        self,
        enrollment: dict,
        config: dict,
        value_before: int,
        value_after: int,
    ) -> list[str]:
        total = config.get("total_stamps", 10)
        milestones = []

        # Check percentage milestones
        for pct in [50, 80]:
            threshold = int(total * pct / 100)
            if value_before < threshold <= value_after:
                milestones.append(f"milestone_{pct}")

        if value_before < total <= value_after:
            milestones.append("reward_earned")

        return milestones

    def get_display_value(self, enrollment: dict, config: dict) -> str:
        stamps = enrollment.get("progress", {}).get("stamps", 0)
        total = config.get("total_stamps", 10)
        return f"{stamps} / {total}"

    def can_redeem(self, enrollment: dict, config: dict) -> bool:
        stamps = enrollment.get("progress", {}).get("stamps", 0)
        total = config.get("total_stamps", 10)
        return stamps >= total


class PointsEngine(BaseEngine):
    """Engine for points-based loyalty programs."""

    def add_progress(
        self,
        enrollment: dict,
        config: dict,
        amount: int = 1,
        modifiers: EventModifiers | None = None,
    ) -> tuple[dict, int, list[str], bool]:
        modifiers = modifiers or EventModifiers()
        progress = dict(enrollment.get("progress", {}))

        points_per_visit = config.get("points_per_visit", 10)
        base_points = amount * points_per_visit
        effective_points = int(base_points * modifiers.multiplier) + modifiers.bonus

        current = progress.get("points", 0)
        lifetime = progress.get("lifetime_points", 0)

        new_value = current + effective_points
        progress["points"] = new_value
        progress["lifetime_points"] = lifetime + effective_points

        # Check if any reward threshold is reached
        rewards = config.get("rewards", [])
        reward_earned = any(new_value >= r.get("points_required", 0) for r in rewards)

        milestones = self.check_milestones(enrollment, config, current, new_value)

        return progress, effective_points, milestones, reward_earned

    def redeem(
        self,
        enrollment: dict,
        config: dict,
        reward_index: int = 0,
    ) -> tuple[dict, str]:
        progress = dict(enrollment.get("progress", {}))
        rewards = config.get("rewards", [])

        if reward_index >= len(rewards):
            raise ValueError(f"Invalid reward index: {reward_index}")

        reward = rewards[reward_index]
        points_required = reward.get("points_required", 0)
        reward_name = reward.get("name", "Reward")

        current_points = progress.get("points", 0)
        if current_points < points_required:
            raise ValueError(f"Not enough points: {current_points} < {points_required}")

        progress["points"] = current_points - points_required
        return progress, reward_name

    def check_milestones(
        self,
        enrollment: dict,
        config: dict,
        value_before: int,
        value_after: int,
    ) -> list[str]:
        milestones = []
        rewards = config.get("rewards", [])

        for reward in rewards:
            threshold = reward.get("points_required", 0)
            if value_before < threshold <= value_after:
                milestones.append(f"reward_available_{reward.get('name', 'reward')}")

        return milestones

    def get_display_value(self, enrollment: dict, config: dict) -> str:
        points = enrollment.get("progress", {}).get("points", 0)
        return f"{points} pts"

    def can_redeem(self, enrollment: dict, config: dict) -> bool:
        points = enrollment.get("progress", {}).get("points", 0)
        rewards = config.get("rewards", [])
        return any(points >= r.get("points_required", 0) for r in rewards)


class TieredEngine(BaseEngine):
    """Engine for tiered loyalty programs."""

    def add_progress(
        self,
        enrollment: dict,
        config: dict,
        amount: int = 1,
        modifiers: EventModifiers | None = None,
    ) -> tuple[dict, int, list[str], bool]:
        modifiers = modifiers or EventModifiers()
        progress = dict(enrollment.get("progress", {}))

        points_per_visit = config.get("points_per_visit", 10)
        base_points = amount * points_per_visit
        effective_points = int(base_points * modifiers.multiplier) + modifiers.bonus

        current = progress.get("points", 0)
        lifetime = progress.get("lifetime_points", 0)

        new_value = current + effective_points
        new_lifetime = lifetime + effective_points
        progress["points"] = new_value
        progress["lifetime_points"] = new_lifetime

        # Evaluate tier
        tiers = config.get("tiers", [])
        old_tier = progress.get("current_tier", "")
        new_tier = self._evaluate_tier(new_lifetime, tiers)
        progress["current_tier"] = new_tier

        milestones = []
        reward_earned = False

        if new_tier != old_tier:
            old_idx = self._tier_index(old_tier, tiers)
            new_idx = self._tier_index(new_tier, tiers)
            if new_idx > old_idx:
                milestones.append(f"tier_upgrade_{new_tier}")
            elif new_idx < old_idx:
                milestones.append(f"tier_downgrade_{new_tier}")

        return progress, effective_points, milestones, reward_earned

    def redeem(
        self,
        enrollment: dict,
        config: dict,
        reward_index: int = 0,
    ) -> tuple[dict, str]:
        # Tiered programs typically don't have point redemption,
        # but we support it for flexibility
        progress = dict(enrollment.get("progress", {}))
        return progress, "Tier Benefit"

    def check_milestones(
        self,
        enrollment: dict,
        config: dict,
        value_before: int,
        value_after: int,
    ) -> list[str]:
        tiers = config.get("tiers", [])
        milestones = []
        for tier in tiers:
            threshold = tier.get("threshold", 0)
            if value_before < threshold <= value_after:
                milestones.append(f"tier_reached_{tier.get('name', 'tier')}")
        return milestones

    def get_display_value(self, enrollment: dict, config: dict) -> str:
        tier = enrollment.get("progress", {}).get("current_tier", "Bronze")
        points = enrollment.get("progress", {}).get("points", 0)
        return f"{tier} ({points} pts)"

    def can_redeem(self, enrollment: dict, config: dict) -> bool:
        return False  # Tiers don't have standard redemption

    def _evaluate_tier(self, lifetime_points: int, tiers: list[dict]) -> str:
        """Determine tier based on lifetime points."""
        current_tier = tiers[0].get("name", "Bronze") if tiers else "Bronze"
        for tier in sorted(tiers, key=lambda t: t.get("threshold", 0)):
            if lifetime_points >= tier.get("threshold", 0):
                current_tier = tier.get("name", current_tier)
        return current_tier

    def _tier_index(self, tier_name: str, tiers: list[dict]) -> int:
        """Get the index of a tier by name."""
        for i, tier in enumerate(sorted(tiers, key=lambda t: t.get("threshold", 0))):
            if tier.get("name") == tier_name:
                return i
        return 0
