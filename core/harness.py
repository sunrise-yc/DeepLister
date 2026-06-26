"""Minimal DeepLister Harness orchestration for the web demo."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.arbitrator import arbitrate
from core.detector import detect_signals
from core.generator import generate_reply, strategy_label
from core.verifier import verify_reply
from shared.types import DecisionLogEntry


@dataclass
class ConversationState:
    """Session-level state for the demo conversation."""

    turn_id: int = 0
    follow_up_count: int = 0
    recent_assistant_replies: list[str] = field(default_factory=list)
    decision_logs: list[DecisionLogEntry] = field(default_factory=list)
    summary: str = ""


@dataclass
class TurnOutput:
    """UI-friendly result for one conversation turn."""

    assistant_reply: str
    strategy_label: str
    user_visible_reason: str
    decision_log: DecisionLogEntry


class DeepListerHarness:
    """Run detect → arbitrate → generate → verify for each user reply."""

    def __init__(self, state: ConversationState | None = None):
        self.state = state or ConversationState()

    def opening_question(self) -> str:
        return "最近一周睡眠怎么样？有没有入睡困难、早醒或者睡不踏实的情况？"

    def process_reply(self, user_reply: str) -> TurnOutput:
        self.state.turn_id += 1
        detection = detect_signals(user_reply, self.state.summary)
        arbitration = arbitrate(detection, self.state.follow_up_count)
        reply = generate_reply(arbitration, user_reply, self.state.turn_id)
        verification = verify_reply(reply, self.state.recent_assistant_replies)

        if not verification.passed and verification.correction_direction:
            reply = "我换个更简单的问法：最近一周睡眠大概能打几分？"
            verification = verify_reply(reply, self.state.recent_assistant_replies)

        log = DecisionLogEntry(
            turn_id=self.state.turn_id,
            user_reply=user_reply,
            detection_result=detection,
            arbitration_result=arbitration,
            generated_reply=reply,
            verification_result=verification,
        )

        self.state.follow_up_count = arbitration.follow_up_count
        if arbitration.strategy == "ask_next_sub_question":
            self.state.follow_up_count = 0
        self.state.recent_assistant_replies.append(reply)
        self.state.decision_logs.append(log)
        self.state.summary = f"{self.state.summary}\n用户：{user_reply}\nAI：{reply}".strip()

        return TurnOutput(
            assistant_reply=reply,
            strategy_label=strategy_label(arbitration.strategy),
            user_visible_reason=self._reason_for(log),
            decision_log=log,
        )

    @staticmethod
    def _reason_for(log: DecisionLogEntry) -> str:
        strategy = log.arbitration_result.strategy
        if strategy == "comprehension_correction":
            return "你的回答比较概括，我会先帮你把感受具体化。"
        if strategy == "depth_mining":
            return "你已经说出现象了，我会继续了解背后的原因。"
        if strategy == "safety_protocol":
            return "当前优先级是安全支持，而不是继续问卷。"
        if strategy == "consistency_confirmation":
            return "我发现前后信息可能不一致，需要先确认。"
        return "当前维度信息基本足够，我会推进到下一个问题。"
