"""Rule-based reply verifier for the DeepLister demo."""

from __future__ import annotations

from shared.types import VerificationResult


def verify_reply(reply: str, recent_replies: list[str] | None = None) -> VerificationResult:
    """Check that the generated reply is short, safe, and non-repetitive."""
    recent_replies = recent_replies or []
    sentence_count = sum(reply.count(mark) for mark in "。？！?!")
    length_check = sentence_count <= 2 or len(reply) <= 80
    repetition_check = reply not in recent_replies[-2:]
    safety_check = "诊断" not in reply and "你有病" not in reply
    passed = length_check and repetition_check and safety_check

    correction_direction = None
    if not length_check:
        correction_direction = "回复需要压缩到两句话以内。"
    elif not repetition_check:
        correction_direction = "回复和最近两轮重复，需要换一个问法。"
    elif not safety_check:
        correction_direction = "回复包含不合适的诊断或评价，需要改为支持性表达。"

    return VerificationResult(
        passed=passed,
        length_check=length_check,
        repetition_check=repetition_check,
        safety_check=safety_check,
        correction_direction=correction_direction,
    )
