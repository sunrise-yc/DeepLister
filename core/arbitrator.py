"""Deterministic strategy arbitration for DeepLister."""

from __future__ import annotations

from shared.config import Config
from shared.types import ArbitrationResult, SignalDetection


def arbitrate(detection: SignalDetection, follow_up_count: int) -> ArbitrationResult:
    """Choose the next strategy with safety-first priority."""
    if detection.safety.triggered:
        return ArbitrationResult(
            strategy="safety_protocol",
            priority="P0",
            follow_up_count=follow_up_count,
        )

    if follow_up_count >= Config.MAX_FOLLOW_UP_PER_TOPIC:
        return ArbitrationResult(
            strategy="ask_next_sub_question",
            priority="P4",
            follow_up_count=follow_up_count,
            force_proceed=True,
        )

    if detection.comprehension.triggered:
        return ArbitrationResult(
            strategy="comprehension_correction",
            priority="P1",
            follow_up_count=follow_up_count + 1,
        )

    if detection.consistency.triggered:
        return ArbitrationResult(
            strategy="consistency_confirmation",
            priority="P2",
            follow_up_count=follow_up_count + 1,
        )

    if detection.sufficiency.triggered:
        return ArbitrationResult(
            strategy="depth_mining",
            priority="P3",
            follow_up_count=follow_up_count + 1,
        )

    return ArbitrationResult(
        strategy="ask_next_sub_question",
        priority="P4",
        follow_up_count=follow_up_count,
    )
