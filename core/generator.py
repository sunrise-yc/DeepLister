from shared.config import Config
from shared.llm_client import LLMClient
from shared.types import ArbitrationResult, Topic


class Generator:
    """Generates the user-facing next prompt from an already chosen strategy."""

    def __init__(self, llm_client: LLMClient | None = None, use_llm: bool | None = None):
        self.llm_client = llm_client or LLMClient()
        self.use_llm = Config.USE_LLM if use_llm is None else use_llm

    def generate(
        self,
        arbitration: ArbitrationResult,
        topic: Topic,
        current_question: str,
        user_reply: str,
        topic_context: dict,
        next_question: str | None = None,
        next_topic: Topic | None = None,
    ) -> str:
        if self.use_llm and arbitration.strategy in {
            "comprehension_correction",
            "consistency_confirmation",
            "depth_mining",
        }:
            try:
                text = self._generate_with_llm(arbitration, topic, current_question, user_reply, topic_context)
                if text:
                    return text
            except Exception:
                pass
        return self._generate_with_rules(arbitration, topic, current_question, next_question, next_topic)

    def _generate_with_llm(
        self,
        arbitration: ArbitrationResult,
        topic: Topic,
        current_question: str,
        user_reply: str,
        topic_context: dict,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 DeepLister 的追问生成层。只根据给定策略生成一句自然追问，"
                    "不要诊断，不要安慰过度，不要超过两句话。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"策略：{arbitration.strategy}\n"
                    f"话题：{topic.topic_name}\n"
                    f"当前问题：{current_question}\n"
                    f"用户回答：{user_reply}\n"
                    f"上下文：{topic_context}"
                ),
            },
        ]
        return self.llm_client.chat(
            messages,
            temperature=Config.TEMPERATURE_GENERATE,
            max_tokens=120,
        ).strip()

    def _generate_with_rules(
        self,
        arbitration: ArbitrationResult,
        topic: Topic,
        current_question: str,
        next_question: str | None,
        next_topic: Topic | None,
    ) -> str:
        strategy = arbitration.strategy
        if strategy == "safety_protocol":
            return "听起来你现在很难受。这个话题我们先暂停，如果有伤害自己的想法，请马上联系身边可信任的人或当地紧急求助热线。"

        if strategy == "comprehension_correction":
            return self._concrete_question(topic, current_question)

        if strategy == "consistency_confirmation":
            return "我想确认一下：你刚才的意思和前面说的有点不一样，是状态发生变化了，还是我理解偏了？"

        if strategy == "depth_mining":
            return "是什么让这种情况更明显？可以说一个最近发生的具体场景。"

        if next_question:
            return f"明白了。{next_question}"

        if next_topic:
            return f"{topic.topic_name}这块我了解了。接下来聊聊{next_topic.topic_name}：{next_topic.opening_question}"

        return "谢谢你，主要话题已经完成。我整理出了一份结构化结果和每轮决策日志。"

    def _concrete_question(self, topic: Topic, current_question: str) -> str:
        name = topic.topic_name
        if "睡" in name:
            return "如果用 1 到 10 分表示睡眠状态，你大概会给几分？最近一次睡不好是什么时候？"
        if "焦虑" in name or "压力" in name:
            return "如果用 1 到 10 分表示紧张或压力程度，你大概在哪个位置？通常是什么事情触发的？"
        if "情绪" in name or "低落" in name:
            return "如果按最近一周来看，这种感觉大概出现了几天？有没有一个最近的例子？"
        if "MBTI" in name or "人格" in name:
            return "如果按第一感觉选，你会更偏同意还是不同意？不用想得太复杂。"
        return f"围绕“{current_question}”，能不能用一个最近发生的小例子来说说？"
