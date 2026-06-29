import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.harness import HarnessEngine, HarnessSession
from memory.profile_manager import ProfileManager
from shared.types import Questionnaire, Topic


def main() -> None:
    questionnaire = Questionnaire(
        title="测试问卷",
        description="测试正式分层引擎",
        topics=[
            Topic(
                topic_id="sleep",
                topic_name="睡眠质量",
                description="了解睡眠",
                core_dimensions=["睡眠质量"],
                opening_question="最近睡眠怎么样？",
                sub_questions=[],
            )
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = HarnessEngine(questionnaire, profile_manager=ProfileManager(tmpdir))
        state = HarnessSession()

        first = engine.process_reply(state, "test_user", "还行")
        assert first["needs_follow_up"] is True
        assert state.pending_followup
        assert first["decision_log"].arbitration_result.strategy == "comprehension_correction"

        second = engine.process_reply(state, "test_user", "主要是工作压力大，晚上总想着项目，睡不着")
        assert second["needs_follow_up"] is False
        assert second["all_completed"] is True
        assert state.pending_followup is None
        assert len(state.logs) == 2
        assert state.logs[-1].evaluation["engine"] == "HarnessEngine"

    print("Harness engine OK")


def test_harness_engine_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
