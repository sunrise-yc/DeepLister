from dataclasses import dataclass, field

from core.arbitrator import Arbitrator
from core.detector import Detector
from core.generator import Generator
from core.verifier import Verifier
from memory.profile_manager import ProfileManager
from shared.config import Config
from shared.types import DecisionLogEntry, Questionnaire, Topic


@dataclass
class HarnessSession:
    topic_index: int = 0
    question_cursor: int = 0
    turn_id: int = 0
    follow_up_count: int = 0
    consecutive_vague: int = 0
    pending_followup: str | None = None
    stopped: bool = False
    completed_topics: list[str] = field(default_factory=list)
    recent_user_replies: list[str] = field(default_factory=list)
    recent_ai_replies: list[str] = field(default_factory=list)
    logs: list[DecisionLogEntry] = field(default_factory=list)


class HarnessEngine:
    """Production-style engine that runs detect -> arbitrate -> generate -> verify."""

    def __init__(
        self,
        questionnaire: Questionnaire,
        profile_manager: ProfileManager | None = None,
        detector: Detector | None = None,
        arbitrator: Arbitrator | None = None,
        generator: Generator | None = None,
        verifier: Verifier | None = None,
    ):
        self.questionnaire = questionnaire
        self.profile_manager = profile_manager or ProfileManager()
        self.detector = detector or Detector()
        self.arbitrator = arbitrator or Arbitrator()
        self.generator = generator or Generator()
        self.verifier = verifier or Verifier()

    def get_opening(self, state: HarnessSession) -> str:
        question = self.get_current_question(state)
        return question["text"] if question else "感谢你的参与，今天的访谈已经完成。"

    def get_current_question(self, state: HarnessSession) -> dict | None:
        topic = self.current_topic(state)
        if topic is None or state.stopped:
            return None
        if state.pending_followup:
            return {
                "topic": topic,
                "text": state.pending_followup,
                "dimension": topic.topic_name,
                "is_followup": True,
            }
        return {
            "topic": topic,
            "text": self._question_text(topic, state.question_cursor),
            "dimension": self._question_dimension(topic, state.question_cursor),
            "is_followup": False,
        }

    def current_topic(self, state: HarnessSession) -> Topic | None:
        if state.topic_index >= len(self.questionnaire.topics):
            return None
        return self.questionnaire.topics[state.topic_index]

    def get_status(self, state: HarnessSession) -> dict:
        topic = self.current_topic(state)
        total = len(self.questionnaire.topics)
        completed = min(len(state.completed_topics), total)
        return {
            "completed": completed,
            "total": total,
            "topic_name": topic.topic_name if topic else "已完成",
            "progress": completed / total if total else 1,
            "all_completed": state.stopped or state.topic_index >= total,
        }

    def process_reply(
        self,
        state: HarnessSession,
        user_id: str,
        user_reply: str,
        allow_follow_up: bool = True,
    ) -> dict:
        topic = self.current_topic(state)
        current = self.get_current_question(state)
        if topic is None or current is None or state.stopped:
            return {
                "reply": "已经完成啦，感谢你的参与。",
                "topic_completed": True,
                "all_completed": True,
                "needs_follow_up": False,
                "decision_log": None,
                "trace": None,
            }

        profile = self.profile_manager.get_profile(user_id)
        topic_context = self._topic_context(topic, state, user_id)

        detection = self.detector.detect(
            user_reply=user_reply,
            current_question=current["text"],
            topic_context=topic_context,
            user_profile=profile.model_dump(),
        )
        if detection.comprehension.triggered:
            state.consecutive_vague += 1
        else:
            state.consecutive_vague = 0

        arbitration = self.arbitrator.arbitrate(
            detection=detection,
            follow_up_count=state.follow_up_count,
            consecutive_vague=state.consecutive_vague,
            allow_follow_up=allow_follow_up,
        )

        next_question = self._peek_next_question(state)
        next_topic = self._peek_next_topic(state)
        generated = self.generator.generate(
            arbitration=arbitration,
            topic=topic,
            current_question=current["text"],
            user_reply=user_reply,
            topic_context=topic_context,
            next_question=next_question,
            next_topic=next_topic,
        )
        verification = self.verifier.verify(generated, arbitration, state.recent_ai_replies)
        if not verification.passed and arbitration.strategy != "proceed":
            fallback_arbitration = self.arbitrator.arbitrate(
                detection=detection,
                follow_up_count=Config.MAX_FOLLOW_UP_PER_TOPIC,
                consecutive_vague=Config.MAX_CONSECUTIVE_VAGUE,
                allow_follow_up=False,
            )
            generated = self.generator.generate(
                arbitration=fallback_arbitration,
                topic=topic,
                current_question=current["text"],
                user_reply=user_reply,
                topic_context=topic_context,
                next_question=next_question,
                next_topic=next_topic,
            )
            arbitration = fallback_arbitration
            verification = self.verifier.verify(generated, arbitration, state.recent_ai_replies)

        needs_follow_up = arbitration.strategy in {
            "comprehension_correction",
            "consistency_confirmation",
            "depth_mining",
        }
        if arbitration.strategy == "safety_protocol":
            state.stopped = True
            needs_follow_up = False

        previous_prompt = current["text"]
        state.turn_id += 1
        state.recent_user_replies.append(user_reply)
        state.recent_user_replies = state.recent_user_replies[-6:]
        state.recent_ai_replies.append(generated)
        state.recent_ai_replies = state.recent_ai_replies[-6:]

        topic_completed = False
        if needs_follow_up:
            state.pending_followup = generated
            state.follow_up_count += 1
            self.profile_manager.increment_follow_up(user_id, topic.topic_id)
        else:
            state.pending_followup = None
            topic_completed = self._advance_after_answer(state)
            self._update_profile_after_answer(user_id, topic, user_reply, topic_completed)

        log = DecisionLogEntry(
            turn_id=state.turn_id,
            user_reply=user_reply,
            detection_result=detection,
            arbitration_result=arbitration,
            generated_reply=generated,
            verification_result=verification,
            evaluation={
                "topic": topic.topic_name,
                "question": previous_prompt,
                "accepted_answer": not needs_follow_up,
                "engine": "HarnessEngine",
            },
        )
        state.logs.append(log)

        return {
            "reply": generated,
            "topic_completed": topic_completed,
            "all_completed": state.stopped or state.topic_index >= len(self.questionnaire.topics),
            "needs_follow_up": needs_follow_up,
            "decision_log": log,
            "trace": self._trace_dict(topic, previous_prompt, user_reply, log),
        }

    def _question_text(self, topic: Topic, cursor: int) -> str:
        if cursor == 0:
            return topic.opening_question
        index = cursor - 1
        if index < len(topic.sub_questions):
            return topic.sub_questions[index].text
        return topic.opening_question

    def _question_dimension(self, topic: Topic, cursor: int) -> str:
        if cursor == 0:
            return topic.topic_name
        index = cursor - 1
        if index < len(topic.sub_questions):
            return topic.sub_questions[index].dimension
        return topic.topic_name

    def _peek_next_question(self, state: HarnessSession) -> str | None:
        topic = self.current_topic(state)
        if topic is None:
            return None
        next_cursor = state.question_cursor + 1
        if next_cursor == 0:
            return topic.opening_question
        sub_index = next_cursor - 1
        if sub_index < len(topic.sub_questions):
            return topic.sub_questions[sub_index].text
        return None

    def _peek_next_topic(self, state: HarnessSession) -> Topic | None:
        index = state.topic_index + 1
        if index < len(self.questionnaire.topics):
            return self.questionnaire.topics[index]
        return None

    def _advance_after_answer(self, state: HarnessSession) -> bool:
        topic = self.current_topic(state)
        if topic is None:
            return True

        state.question_cursor += 1
        if state.question_cursor <= len(topic.sub_questions):
            return False

        state.completed_topics.append(topic.topic_id)
        state.topic_index += 1
        state.question_cursor = 0
        state.follow_up_count = 0
        state.consecutive_vague = 0
        return True

    def _topic_context(self, topic: Topic, state: HarnessSession, user_id: str) -> dict:
        status = self.profile_manager.get_topic_status(user_id, topic.topic_id)
        return {
            "topic_id": topic.topic_id,
            "topic_name": topic.topic_name,
            "core_dimensions": topic.core_dimensions,
            "key_signals": status.key_signals if status else [],
            "previous_replies": state.recent_user_replies[-3:],
            "question_cursor": state.question_cursor,
            "follow_up_count": state.follow_up_count,
        }

    def _update_profile_after_answer(
        self,
        user_id: str,
        topic: Topic,
        user_reply: str,
        topic_completed: bool,
    ) -> None:
        status = "completed" if topic_completed else "in_progress"
        score = 1.0 if topic_completed else 0.5
        self.profile_manager.update_topic_status(
            user_id,
            topic.topic_id,
            {"status": status, "completeness_score": score},
        )
        signal = self._extract_key_signal(user_reply)
        if signal:
            self.profile_manager.add_key_signal(user_id, topic.topic_id, signal)

    def _extract_key_signal(self, user_reply: str) -> str | None:
        text = user_reply.strip()
        if not text:
            return None
        return text[:30]

    def _trace_dict(
        self,
        topic: Topic,
        question: str,
        answer: str,
        log: DecisionLogEntry,
    ) -> dict:
        detection = log.detection_result
        triggered = []
        for label, result in [
            ("安全", detection.safety),
            ("理解", detection.comprehension),
            ("一致性", detection.consistency),
            ("信息充分度", detection.sufficiency),
        ]:
            if result.triggered:
                triggered.append(f"{label}:{result.type or 'triggered'}")
        detection_text = "；".join(triggered) if triggered else "未发现需要追问的信号"
        if triggered and detection.sufficiency.detail:
            detection_text += f"；{detection.sufficiency.detail}"
        if triggered and detection.comprehension.detail:
            detection_text += f"；{detection.comprehension.detail}"

        return {
            "dimension": topic.topic_name,
            "question": question,
            "answer": answer,
            "detection": detection_text,
            "arbitration": f"{log.arbitration_result.priority}：{log.arbitration_result.strategy}",
            "generation": log.generated_reply,
            "verification": "通过" if log.verification_result.passed else log.verification_result.correction_direction,
        }
