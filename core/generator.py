"""Template-based response generator for the offline demo."""

from __future__ import annotations

from shared.types import ArbitrationResult

STRATEGY_LABELS = {
    "safety_protocol": "安全优先",
    "comprehension_correction": "理解纠偏",
    "consistency_confirmation": "一致性确认",
    "depth_mining": "深度挖掘",
    "ask_next_sub_question": "推进问题",
}


def generate_reply(arbitration: ArbitrationResult, user_reply: str, turn_id: int) -> str:
    """Generate a short mobile-friendly assistant reply."""
    strategy = arbitration.strategy

    if strategy == "safety_protocol":
        return "听起来你现在很难受，我很在意你的安全。请尽快联系身边可信任的人；如果有立即危险，请联系当地紧急服务。"

    if strategy == "comprehension_correction":
        return "“还行”有点难判断。 如果用 1 到 10 分打分，最近一周睡眠大概在几分？"

    if strategy == "consistency_confirmation":
        return "我想确认一下：你前面说睡得还不错，现在又提到比较差。哪一种更接近最近一周的真实情况？"

    if strategy == "depth_mining":
        return "是什么让你不容易睡着？ 是脑子里想事情，还是身体不舒服？"

    if turn_id <= 1:
        return "最近一周睡眠怎么样？有没有入睡困难、早醒或者睡不踏实的情况？"

    if "压力" in user_reply or "工作" in user_reply or "想事" in user_reply or "想事情" in user_reply:
        return "明白了，压力确实会影响入睡。 白天会觉得精力不够吗？"

    return "我了解了。 白天会觉得精力不够，或者注意力不太集中吗？"


def strategy_label(strategy: str) -> str:
    """Return a concise Chinese label for a strategy."""
    return STRATEGY_LABELS.get(strategy, "继续访谈")
