from dataclasses import dataclass, field

from core.questionnaire_parser import parse_questionnaire
from shared.types import (
    ArbitrationResult,
    DecisionLogEntry,
    Questionnaire,
    SignalDetection,
    SignalResult,
    Topic,
    VerificationResult,
)


@dataclass
class DemoState:
    topic_index: int = 0
    turn_id: int = 0
    follow_up_count: int = 0
    answered_in_topic: int = 0
    completed_topics: list[str] = field(default_factory=list)
    logs: list[DecisionLogEntry] = field(default_factory=list)


class MockHarnessEngine:
    """A deterministic demo engine that shows the Harness flow without an API key."""

    def __init__(self, questionnaire: Questionnaire):
        self.questionnaire = questionnaire

    @classmethod
    def from_json(cls, json_data: dict) -> "MockHarnessEngine":
        return cls(parse_questionnaire(json_data))

    def get_opening(self, state: DemoState) -> str:
        topic = self.current_topic(state)
        if topic is None:
            return "感谢你的参与，今天的访谈已经完成。"
        return topic.opening_question

    def current_topic(self, state: DemoState) -> Topic | None:
        if state.topic_index >= len(self.questionnaire.topics):
            return None
        return self.questionnaire.topics[state.topic_index]

    def get_status(self, state: DemoState) -> dict:
        topic = self.current_topic(state)
        total = len(self.questionnaire.topics)
        completed = min(state.topic_index, total)
        return {
            "completed": completed,
            "total": total,
            "topic_name": topic.topic_name if topic else "已完成",
            "progress": completed / total if total else 1,
        }

    def process_reply(self, state: DemoState, user_reply: str) -> dict:
        topic = self.current_topic(state)
        if topic is None:
            return {"reply": "已经完成啦，感谢你的参与。", "all_completed": True, "decision_log": None}

        detection = self._detect(user_reply)
        arbitration = self._arbitrate(detection, state.follow_up_count)
        reply, topic_completed = self._generate(topic, state, arbitration, user_reply)
        verification = VerificationResult(passed=True)

        state.turn_id += 1
        if arbitration.strategy in {"comprehension_correction", "depth_mining"}:
            state.follow_up_count += 1
        else:
            state.answered_in_topic += 1

        if topic_completed:
            state.completed_topics.append(topic.topic_id)
            state.topic_index += 1
            state.follow_up_count = 0
            state.answered_in_topic = 0

        log = DecisionLogEntry(
            turn_id=state.turn_id,
            user_reply=user_reply,
            detection_result=detection,
            arbitration_result=arbitration,
            generated_reply=reply,
            verification_result=verification,
            evaluation={
                "topic": topic.topic_name,
                "demo_note": "Mock 模式：用固定规则稳定展示 Harness 四步链路。",
            },
        )
        state.logs.append(log)

        return {
            "reply": reply,
            "topic_completed": topic_completed,
            "all_completed": state.topic_index >= len(self.questionnaire.topics),
            "decision_log": log,
        }

    def _detect(self, text: str) -> SignalDetection:
        normalized = text.strip().lower()
        safety_words = ["不想活", "自杀", "伤害自己", "活不下去", "崩溃"]
        vague_words = ["还行", "一般", "差不多", "不好说", "有时候", "还好"]
        reason_words = ["因为", "主要", "压力", "工作", "学习", "家里", "身体", "疼", "担心"]

        safety = any(word in normalized for word in safety_words)
        vague = len(normalized) <= 8 or any(word in normalized for word in vague_words)
        has_reason = any(word in normalized for word in reason_words)
        has_state = any(word in normalized for word in ["睡", "紧张", "焦虑", "低落", "困", "醒", "出门"])

        return SignalDetection(
            safety=SignalResult(
                triggered=safety,
                type="emotional_crisis" if safety else None,
                detail="出现强烈危机表达" if safety else None,
                confidence=0.9 if safety else 0.02,
            ),
            comprehension=SignalResult(
                triggered=not safety and vague,
                type="vague_reply" if not safety and vague else None,
                detail="回答比较短或比较含糊，暂时难以提取稳定信息" if not safety and vague else None,
                confidence=0.82 if not safety and vague else 0.12,
            ),
            consistency=SignalResult(triggered=False, confidence=0.08),
            sufficiency=SignalResult(
                triggered=not safety and not vague and has_state and not has_reason,
                type="conclusion_without_reason" if not safety and not vague and has_state and not has_reason else None,
                detail="已经表达了状态，但还缺少原因、场景或影响" if not safety and not vague and has_state and not has_reason else None,
                confidence=0.76 if not safety and not vague and has_state and not has_reason else 0.2,
            ),
        )

    def _arbitrate(self, detection: SignalDetection, follow_up_count: int) -> ArbitrationResult:
        if detection.safety.triggered:
            return ArbitrationResult(strategy="safety_protocol", priority="P0", follow_up_count=follow_up_count)
        if follow_up_count >= 2:
            return ArbitrationResult(strategy="proceed", priority="P4", follow_up_count=follow_up_count, force_proceed=True)
        if detection.comprehension.triggered:
            return ArbitrationResult(strategy="comprehension_correction", priority="P1", follow_up_count=follow_up_count)
        if detection.sufficiency.triggered:
            return ArbitrationResult(strategy="depth_mining", priority="P3", follow_up_count=follow_up_count)
        return ArbitrationResult(strategy="proceed", priority="P4", follow_up_count=follow_up_count)

    def _generate(
        self,
        topic: Topic,
        state: DemoState,
        arbitration: ArbitrationResult,
        user_reply: str,
    ) -> tuple[str, bool]:
        if arbitration.strategy == "safety_protocol":
            return "听起来你现在很难受。这个话题我们先暂停，如果有伤害自己的想法，请马上联系身边可信任的人或当地紧急求助热线。", True

        if arbitration.strategy == "comprehension_correction":
            return self._concrete_question(topic), False

        if arbitration.strategy == "depth_mining":
            return "是什么让这种情况更明显？可以说一个最近发生的具体场景。", False

        next_question_index = state.answered_in_topic
        if next_question_index < len(topic.sub_questions):
            return f"明白了。{topic.sub_questions[next_question_index].text}", False

        next_topic_index = state.topic_index + 1
        if next_topic_index < len(self.questionnaire.topics):
            next_topic = self.questionnaire.topics[next_topic_index]
            return f"{topic.topic_name}这块我了解了。接下来聊聊{next_topic.topic_name}：{next_topic.opening_question}", True

        return "谢谢你，主要话题已经完成。我整理出了一份结构化画像和每轮决策日志。", True

    def _concrete_question(self, topic: Topic) -> str:
        if "睡眠" in topic.topic_name:
            return "如果用 1 到 10 分表示睡眠状态，你大概会给几分？最近一次睡不好是什么时候？"
        if "焦虑" in topic.topic_name:
            return "如果用 1 到 10 分表示紧张程度，你大概在哪个位置？通常是什么事情触发的？"
        if "情绪" in topic.topic_name:
            return "如果按一周来看，这种低落大概出现了几天？有没有一个最近的例子？"
        return "能不能用一个最近发生的小例子来说说？这样我更容易理解你的感受。"
