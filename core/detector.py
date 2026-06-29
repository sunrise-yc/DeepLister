from shared.config import Config
from shared.llm_client import LLMClient
from shared.types import SignalDetection, SignalResult


class Detector:
    """Detects answer quality and safety signals before the engine decides what to do."""

    def __init__(self, llm_client: LLMClient | None = None, use_llm: bool | None = None):
        self.llm_client = llm_client or LLMClient()
        self.use_llm = Config.USE_LLM if use_llm is None else use_llm

    def detect(
        self,
        user_reply: str,
        current_question: str,
        topic_context: dict,
        user_profile: dict,
    ) -> SignalDetection:
        """Return four structured signals for the current user reply."""
        if self.use_llm:
            try:
                llm_result = self._detect_with_llm(user_reply, current_question, topic_context, user_profile)
                if llm_result is not None:
                    return llm_result
            except Exception:
                pass
        return self._detect_with_rules(user_reply, topic_context)

    def _detect_with_llm(
        self,
        user_reply: str,
        current_question: str,
        topic_context: dict,
        user_profile: dict,
    ) -> SignalDetection | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 DeepLister 的信号检测层。只判断，不追问，不给建议。"
                    "请输出 JSON，包含 safety/comprehension/consistency/sufficiency 四个对象，"
                    "每个对象有 triggered、type、detail、confidence 字段。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"当前问题：{current_question}\n"
                    f"用户回答：{user_reply}\n"
                    f"话题上下文：{topic_context}\n"
                    f"用户画像：{user_profile}"
                ),
            },
        ]
        data = self.llm_client.chat_json(messages, temperature=Config.TEMPERATURE_DETECT)
        if not data:
            return None
        return SignalDetection.model_validate(data)

    def _detect_with_rules(self, user_reply: str, topic_context: dict) -> SignalDetection:
        text = user_reply.strip().lower()
        previous_replies = [str(item).strip() for item in topic_context.get("previous_replies", []) if item]

        safety_words = [
            "不想活",
            "自杀",
            "自残",
            "伤害自己",
            "活不下去",
            "撑不住",
            "崩溃",
            "结束生命",
        ]
        vague_words = ["还行", "一般", "还好", "差不多", "不好说", "有时候", "不知道", "随便"]
        reason_words = [
            "因为",
            "主要",
            "由于",
            "压力",
            "工作",
            "学习",
            "家里",
            "身体",
            "担心",
            "害怕",
            "导致",
            "所以",
        ]
        state_words = [
            "睡",
            "醒",
            "困",
            "累",
            "紧张",
            "焦虑",
            "低落",
            "难受",
            "出门",
            "效率",
            "社交",
            "压力",
        ]

        safety = any(word in text for word in safety_words)
        too_short = len(text) <= 8
        vague = not safety and (too_short or any(word in text for word in vague_words))
        has_reason = any(word in text for word in reason_words)
        has_state = any(word in text for word in state_words)
        contradiction = self._looks_contradictory(text, previous_replies)
        sufficiency = not safety and not vague and has_state and not has_reason and len(text) < 28

        return SignalDetection(
            safety=SignalResult(
                triggered=safety,
                type="emotional_crisis" if safety else None,
                detail="回答里出现了明显危机或自我伤害表达" if safety else None,
                confidence=0.92 if safety else 0.03,
            ),
            comprehension=SignalResult(
                triggered=vague,
                type="vague_reply" if vague else None,
                detail="回答过短或比较含糊，暂时难以稳定整理成问卷信息" if vague else None,
                confidence=0.84 if vague else 0.16,
            ),
            consistency=SignalResult(
                triggered=contradiction,
                type="possible_contradiction" if contradiction else None,
                detail="当前回答和同一话题里的早先表达可能不一致" if contradiction else None,
                confidence=0.72 if contradiction else 0.1,
            ),
            sufficiency=SignalResult(
                triggered=sufficiency,
                type="conclusion_without_reason" if sufficiency else None,
                detail="已经有状态描述，但还缺少原因、场景或影响" if sufficiency else None,
                confidence=0.78 if sufficiency else 0.2,
            ),
        )

    def _looks_contradictory(self, text: str, previous_replies: list[str]) -> bool:
        if not previous_replies:
            return False

        negative_markers = ["没有", "不", "从不", "完全不"]
        positive_markers = ["经常", "总是", "每天", "很", "明显", "严重"]

        previous_text = " ".join(previous_replies[-3:]).lower()
        now_negative = any(word in text for word in negative_markers)
        now_positive = any(word in text for word in positive_markers)
        before_negative = any(word in previous_text for word in negative_markers)
        before_positive = any(word in previous_text for word in positive_markers)
        return (now_negative and before_positive) or (now_positive and before_negative)
