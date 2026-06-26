import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.mock_engine import DemoState, MockHarnessEngine


def main() -> None:
    sample_path = ROOT / "data" / "sample_scl90.json"
    questionnaire = json.loads(sample_path.read_text(encoding="utf-8"))
    engine = MockHarnessEngine.from_json(questionnaire)
    state = DemoState()

    opening = engine.get_opening(state)
    assert "睡眠" in opening

    replies = [
        "还行吧",
        "4分，不太容易睡着",
        "主要是工作压力大",
        "一晚醒两三次",
        "白天经常犯困",
    ]
    for reply in replies:
        result = engine.process_reply(state, reply)
        assert result["reply"]
        assert result["decision_log"] is not None

    assert state.logs
    assert any(log.detection_result.comprehension.triggered for log in state.logs)
    print("Demo engine OK")


if __name__ == "__main__":
    main()
