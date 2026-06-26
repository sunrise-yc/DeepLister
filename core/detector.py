"""Rule-based signal detector for the DeepLister demo."""

from __future__ import annotations

from shared.types import SignalDetection, SignalResult

VAGUE_KEYWORDS = {"还行", "一般", "还好", "凑合", "不知道", "说不清", "没啥", "可以吧", "差不多"}
SLEEP_ISSUE_KEYWORDS = {"睡不着", "不容易睡", "不太容易睡", "容易睡着", "入睡困难", "早醒", "睡不好", "睡不踏实", "失眠", "醒"}
REASON_KEYWORDS = {"压力", "工作", "学习", "想事", "想事情", "焦虑", "身体", "疼", "不舒服", "孩子", "家庭", "加班"}
SAFETY_KEYWORDS = {"不想活", "自杀", "轻生", "伤害自己", "活不下去", "撑不住", "崩溃"}


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def detect_signals(user_reply: str, previous_summary: str = "") -> SignalDetection:
    """Detect conversation signals using deterministic demo rules."""
    normalized = user_reply.strip().lower()

    safety = SignalResult(triggered=False)
    comprehension = SignalResult(triggered=False)
    consistency = SignalResult(triggered=False)
    sufficiency = SignalResult(triggered=False)

    if _contains_any(normalized, SAFETY_KEYWORDS):
        safety = SignalResult(
            triggered=True,
            type="self_harm_or_crisis",
            detail="用户表达中出现明显危机或自伤风险信号。",
            confidence=0.95,
        )

    if not safety.triggered and (len(normalized) <= 4 or _contains_any(normalized, VAGUE_KEYWORDS)):
        comprehension = SignalResult(
            triggered=True,
            type="vague_answer",
            detail="用户回答较模糊，暂时无法判断睡眠质量的具体程度。",
            confidence=0.84,
        )

    has_sleep_issue = _contains_any(normalized, SLEEP_ISSUE_KEYWORDS)
    has_reason = _contains_any(normalized, REASON_KEYWORDS)
    if not safety.triggered and not comprehension.triggered and has_sleep_issue and not has_reason:
        sufficiency = SignalResult(
            triggered=True,
            type="no_reason",
            detail="用户说明了睡眠问题，但还没有说明造成问题的原因。",
            confidence=0.8,
        )

    if previous_summary and "睡得很好" in previous_summary and ("4分" in normalized or "很差" in normalized):
        consistency = SignalResult(
            triggered=True,
            type="contradicts_current_topic",
            detail="用户当前描述和前文睡眠状态存在明显不一致。",
            confidence=0.7,
        )

    return SignalDetection(
        safety=safety,
        comprehension=comprehension,
        consistency=consistency,
        sufficiency=sufficiency,
    )
