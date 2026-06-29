from shared.config import Config
from shared.types import ArbitrationResult, SignalDetection


class Arbitrator:
    """Chooses the next strategy with deterministic priority rules."""

    def arbitrate(
        self,
        detection: SignalDetection,
        follow_up_count: int,
        consecutive_vague: int = 0,
        allow_follow_up: bool = True,
    ) -> ArbitrationResult:
        if detection.safety.triggered:
            return ArbitrationResult(
                strategy="safety_protocol",
                priority="P0",
                follow_up_count=follow_up_count,
            )

        if not allow_follow_up:
            return ArbitrationResult(
                strategy="proceed",
                priority="P4",
                follow_up_count=follow_up_count,
                force_proceed=True,
            )

        if follow_up_count >= Config.MAX_FOLLOW_UP_PER_TOPIC:
            return ArbitrationResult(
                strategy="proceed",
                priority="P4",
                follow_up_count=follow_up_count,
                force_proceed=True,
            )

        if consecutive_vague >= Config.MAX_CONSECUTIVE_VAGUE:
            return ArbitrationResult(
                strategy="proceed",
                priority="P4",
                follow_up_count=follow_up_count,
                force_proceed=True,
            )

        if detection.comprehension.triggered:
            return ArbitrationResult(
                strategy="comprehension_correction",
                priority="P1",
                follow_up_count=follow_up_count,
            )

        if detection.consistency.triggered:
            return ArbitrationResult(
                strategy="consistency_confirmation",
                priority="P2",
                follow_up_count=follow_up_count,
            )

        if detection.sufficiency.triggered:
            return ArbitrationResult(
                strategy="depth_mining",
                priority="P3",
                follow_up_count=follow_up_count,
            )

        return ArbitrationResult(
            strategy="proceed",
            priority="P4",
            follow_up_count=follow_up_count,
        )
