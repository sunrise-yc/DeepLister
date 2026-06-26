from typing import Optional

from shared.types import Questionnaire, SubQuestion, Topic


def parse_questionnaire(json_data: dict) -> Questionnaire:
    """Parse questionnaire JSON and fill missing sub-questions."""
    valid, message = validate_questionnaire(json_data)
    if not valid:
        raise ValueError(message)

    normalized = dict(json_data)
    normalized["topics"] = []
    for raw_topic in json_data["topics"]:
        topic_data = dict(raw_topic)
        if not topic_data.get("description"):
            topic_data["description"] = topic_data["topic_name"]
        sub_questions = topic_data.get("sub_questions") or []
        if not sub_questions:
            sub_questions = [
                {
                    "question_id": f"{topic_data['topic_id']}_sq{index}",
                    "text": f"关于{dimension}，能具体说说吗？",
                    "dimension": dimension,
                }
                for index, dimension in enumerate(topic_data["core_dimensions"], start=1)
            ]
        topic_data["sub_questions"] = sub_questions
        normalized["topics"].append(topic_data)

    if hasattr(Questionnaire, "model_validate"):
        return Questionnaire.model_validate(normalized)
    return Questionnaire.parse_obj(normalized)


def get_next_topic(questionnaire: Questionnaire, completed_topic_ids: list[str]) -> Optional[Topic]:
    """Return the first topic whose id is not completed."""
    completed = set(completed_topic_ids)
    for topic in questionnaire.topics:
        if topic.topic_id not in completed:
            return topic
    return None


def get_next_sub_question(topic: Topic, answered_question_ids: list[str]) -> Optional[SubQuestion]:
    """Return the first unanswered sub-question in a topic."""
    answered = set(answered_question_ids)
    for question in topic.sub_questions:
        if question.question_id not in answered:
            return question
    return None


def validate_questionnaire(json_data: dict) -> tuple[bool, str]:
    """Check whether the uploaded questionnaire has the fields the demo needs."""
    if not isinstance(json_data, dict):
        return False, "问卷必须是 JSON 对象"
    if not json_data.get("title"):
        return False, "问卷缺少 title"
    if not isinstance(json_data.get("topics"), list) or not json_data["topics"]:
        return False, "问卷至少需要一个 topic"

    required = ["topic_id", "topic_name", "opening_question", "core_dimensions"]
    for index, topic in enumerate(json_data["topics"], start=1):
        for field in required:
            if not topic.get(field):
                return False, f"第 {index} 个话题缺少 {field}"
        if not isinstance(topic["core_dimensions"], list) or not topic["core_dimensions"]:
            return False, f"第 {index} 个话题的 core_dimensions 不能为空"
    return True, ""
