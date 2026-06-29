import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_import_campaign_from_upload, make_invite_agent, stable_invite_code_for_questionnaire
from storage.survey_store import LocalSurveyStore


def main() -> None:
    questionnaire = {
        "title": "真实上传问卷",
        "description": "用于验证上传后会落盘并能被邀请码找回。",
        "topics": [
            {
                "topic_id": "usage",
                "topic_name": "使用体验",
                "opening_question": "你最近一次使用时整体感觉怎么样？",
                "sub_questions": [
                    {"question_id": "usage_1", "text": "哪个步骤最不顺？"},
                ],
            }
        ],
    }
    file_bytes = json.dumps(questionnaire, ensure_ascii=False).encode("utf-8")
    expected_code = stable_invite_code_for_questionnaire(questionnaire)

    tmpdir = Path(tempfile.mkdtemp(prefix="deeplister-import-"))
    store = LocalSurveyStore(tmpdir)
    campaign = create_import_campaign_from_upload("survey.json", file_bytes, store=store)
    same_campaign = create_import_campaign_from_upload("renamed.json", file_bytes, store=store)

    assert campaign.invite_code == expected_code
    assert same_campaign.campaign_id == campaign.campaign_id

    loaded = store.get_campaign_by_code(expected_code.lower())
    assert loaded is not None
    assert loaded.campaign_id == campaign.campaign_id
    assert loaded.agent["questionnaire"]["title"] == "真实上传问卷"
    assert loaded.agent["questions"][0]["question"] == "你最近一次使用时整体感觉怎么样？"
    assert loaded.agent["questions"][1]["question"] == "哪个步骤最不顺？"

    invited_agent = make_invite_agent(expected_code.lower(), store=store)
    assert invited_agent["kind"] == "campaign"
    assert invited_agent["campaign_id"] == campaign.campaign_id
    assert invited_agent["questionnaire"]["title"] == "真实上传问卷"
    assert invited_agent["questions"][1]["question"] == "哪个步骤最不顺？"

    creator_project_dir = tmpdir / "cloud" / "creators" / campaign.campaign_id
    assert (tmpdir / "campaigns" / f"{campaign.campaign_id}.json").exists()
    assert (creator_project_dir / "campaign.json").exists()

    try:
        broken_store = LocalSurveyStore(tempfile.mkdtemp(prefix="deeplister-import-bad-"))
        create_import_campaign_from_upload("broken.json", b'{"title": "bad"', store=broken_store)
    except ValueError as error:
        assert "JSON 格式不正确" in str(error)
    else:
        raise AssertionError("broken JSON should show a clear conversion error")

    print("Import campaign OK")


def test_import_campaign_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
