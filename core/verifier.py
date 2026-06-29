from shared.config import Config
from shared.llm_client import LLMClient
from shared.types import ArbitrationResult, VerificationResult


class Verifier:
    """Checks generated prompts before they are shown to the user."""

    def __init__(self, llm_client: LLMClient | None = None, use_llm: bool | None = None):
        self.llm_client = llm_client or LLMClient()
        self.use_llm = Config.USE_LLM if use_llm is None else use_llm

    def verify(
        self,
        generated_reply: str,
        arbitration: ArbitrationResult,
        recent_ai_replies: list[str] | None = None,
    ) -> VerificationResult:
        recent_ai_replies = recent_ai_replies or []
        strategy_consistency = self._matches_strategy(generated_reply, arbitration.strategy)
        repetition_check = generated_reply not in recent_ai_replies[-2:]
        length_check = self._sentence_count(generated_reply) <= 2 and len(generated_reply) <= 120
        safety_check = not any(word in generated_reply for word in ["诊断为", "你一定是", "不用找医生"])

        passed = strategy_consistency and repetition_check and length_check and safety_check
        correction = None
        if not strategy_consistency:
            correction = "生成内容没有执行仲裁策略"
        elif not repetition_check:
            correction = "生成内容和最近追问重复"
        elif not length_check:
            correction = "生成内容过长"
        elif not safety_check:
            correction = "生成内容包含不合适的诊断或医疗承诺"

        return VerificationResult(
            passed=passed,
            strategy_consistency=strategy_consistency,
            repetition_check=repetition_check,
            length_check=length_check,
            safety_check=safety_check,
            correction_direction=correction,
        )

    def _matches_strategy(self, generated_reply: str, strategy: str) -> bool:
        if strategy == "safety_protocol":
            return "暂停" in generated_reply or "联系" in generated_reply
        if strategy == "comprehension_correction":
            return "几分" in generated_reply or "例子" in generated_reply or "具体" in generated_reply
        if strategy == "consistency_confirmation":
            return "确认" in generated_reply or "不一样" in generated_reply or "理解" in generated_reply
        if strategy == "depth_mining":
            return "什么" in generated_reply or "场景" in generated_reply or "原因" in generated_reply
        return True

    def _sentence_count(self, text: str) -> int:
        marks = ["。", "？", "！", "?", "!"]
        count = sum(text.count(mark) for mark in marks)
        return max(1, count)
