"""
ProgramService: Central orchestrator for loyalty program operations.

Delegates to type-specific engines (StampEngine, PointsEngine, TieredEngine)
and coordinates with NotificationService, EventService, and wallet services.
"""

import logging
from datetime import datetime, timezone

from app.repositories.program import ProgramRepository
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.customer import CustomerRepository
from app.repositories.transaction import TransactionRepository
from app.services.programs.engines import BaseEngine, StampEngine, PointsEngine, TieredEngine
from app.services.programs.types import ProgressResult, RedeemResult, EventModifiers

logger = logging.getLogger(__name__)

# Engine registry
_ENGINES: dict[str, BaseEngine] = {
    "stamp": StampEngine(),
    "points": PointsEngine(),
    "tiered": TieredEngine(),
}


class ProgramService:
    """Central orchestrator for loyalty program operations."""

    def _get_engine(self, program_type: str) -> BaseEngine:
        engine = _ENGINES.get(program_type)
        if not engine:
            raise ValueError(f"Unknown program type: {program_type}")
        return engine

    def get_default_program(self, business_id: str) -> dict | None:
        return ProgramRepository.get_default(business_id)

    def get_or_create_enrollment(self, customer_id: str, program_id: str, program_type: str = "stamp") -> dict:
        return EnrollmentRepository.get_or_create(customer_id, program_id, program_type)

    async def add_progress(
        self,
        customer_id: str,
        business_id: str,
        program_id: str | None = None,
        amount: int = 1,
        employee_id: str | None = None,
        source: str = "scanner",
        modifiers: EventModifiers | None = None,
    ) -> ProgressResult:
        """
        Add progress to a customer's enrollment in a program.

        If program_id is None, uses the default program for the business.
        """
        # 1. Resolve program
        if program_id:
            program = ProgramRepository.get_by_id(program_id)
        else:
            program = ProgramRepository.get_default(business_id)

        if not program:
            raise ValueError(f"No program found for business {business_id}")

        if not program.get("is_active"):
            raise ValueError(f"Program {program['id']} is not active")

        program_id = program["id"]
        program_type = program["type"]
        config = program.get("config", {})

        # 2. Get or create enrollment
        enrollment = self.get_or_create_enrollment(customer_id, program_id, program_type)

        if enrollment.get("status") != "active":
            raise ValueError(f"Enrollment {enrollment['id']} is not active")

        # 3. Apply modifiers (from promotional events)
        modifiers = modifiers or EventModifiers()

        # 4. Resolve engine and add progress
        engine = self._get_engine(program_type)
        value_before = self._get_current_value(enrollment, program_type)

        new_progress, actual_delta, milestones, reward_earned = engine.add_progress(
            enrollment=enrollment,
            config=config,
            amount=amount,
            modifiers=modifiers,
        )

        # 5. Update enrollment in database
        EnrollmentRepository.update_progress(enrollment["id"], new_progress)
        enrollment["progress"] = new_progress

        value_after = self._get_current_value(enrollment, program_type)

        # 6. Log transaction
        transaction_id = None
        try:
            # Map transaction type based on program type
            txn_type = "stamp_added" if program_type == "stamp" else "points_earned"
            txn = TransactionRepository.create(
                business_id=business_id,
                customer_id=customer_id,
                type=txn_type,
                stamp_delta=actual_delta,
                stamps_before=value_before,
                stamps_after=value_after,
                employee_id=employee_id,
                source=source,
                metadata={
                    "program_id": program_id,
                    "enrollment_id": enrollment["id"],
                    "modifiers": {
                        "multiplier": modifiers.multiplier,
                        "bonus": modifiers.bonus,
                    } if modifiers.multiplier != 1.0 or modifiers.bonus != 0 else {},
                },
            )
            if txn:
                transaction_id = txn["id"]
        except Exception:
            logger.error("[ProgramService] Failed to log transaction", exc_info=True)

        # 7. Also update legacy customers.stamps for backward compat (dual-write)
        if program_type == "stamp":
            try:
                CustomerRepository.update(customer_id, stamps=value_after)
            except Exception:
                logger.warning("[ProgramService] Failed to dual-write customers.stamps", exc_info=True)

        return ProgressResult(
            enrollment=enrollment,
            delta=actual_delta,
            value_before=value_before,
            value_after=value_after,
            milestones=milestones,
            reward_earned=reward_earned,
            transaction_id=transaction_id,
        )

    async def redeem_reward(
        self,
        enrollment_id: str,
        business_id: str,
        reward_index: int = 0,
        employee_id: str | None = None,
    ) -> RedeemResult:
        """Redeem a reward from an enrollment."""
        enrollment = EnrollmentRepository.get_by_id(enrollment_id)
        if not enrollment:
            raise ValueError(f"Enrollment {enrollment_id} not found")

        program = ProgramRepository.get_by_id(enrollment["program_id"])
        if not program:
            raise ValueError(f"Program not found for enrollment {enrollment_id}")

        program_type = program["type"]
        config = program.get("config", {})
        engine = self._get_engine(program_type)

        if not engine.can_redeem(enrollment, config):
            raise ValueError("Not eligible for redemption")

        value_before = self._get_current_value(enrollment, program_type)

        new_progress, reward_name = engine.redeem(enrollment, config, reward_index)

        # Update enrollment
        EnrollmentRepository.update_progress(enrollment["id"], new_progress)
        EnrollmentRepository.increment_redemptions(enrollment["id"])
        enrollment["progress"] = new_progress

        value_after = self._get_current_value(enrollment, program_type)

        # Log transaction
        transaction_id = None
        try:
            txn = TransactionRepository.create(
                business_id=business_id,
                customer_id=enrollment["customer_id"],
                type="reward_redeemed",
                stamp_delta=-(value_before - value_after),
                stamps_before=value_before,
                stamps_after=value_after,
                employee_id=employee_id,
                source="scanner",
                metadata={
                    "program_id": program["id"],
                    "enrollment_id": enrollment_id,
                    "reward_name": reward_name,
                },
            )
            if txn:
                transaction_id = txn["id"]
        except Exception:
            logger.error("[ProgramService] Failed to log redeem transaction", exc_info=True)

        # Dual-write for backward compat
        if program_type == "stamp":
            try:
                CustomerRepository.update(enrollment["customer_id"], stamps=value_after)
                CustomerRepository.increment_redemptions(enrollment["customer_id"])
            except Exception:
                logger.warning("[ProgramService] Failed to dual-write redemption", exc_info=True)

        return RedeemResult(
            enrollment=enrollment,
            value_before=value_before,
            value_after=value_after,
            reward_name=reward_name,
            transaction_id=transaction_id,
        )

    def _get_current_value(self, enrollment: dict, program_type: str) -> int:
        """Extract the primary progress value from an enrollment."""
        progress = enrollment.get("progress", {})
        if program_type == "stamp":
            return progress.get("stamps", 0)
        return progress.get("points", 0)
