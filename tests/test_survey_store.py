import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.survey_models import Campaign, DeveloperFeedbackRecord, ResponseRecord
from storage.survey_store import LocalSurveyStore


def main() -> None:
    agent = {
        "kind": "manual",
        "title": "产品体验调研",
        "subtitle": "测试答卷回收",
        "questions": [
            {
                "dimension": "产品体验",
                "question": "第一次使用时最困惑的地方是什么？",
                "why": "测试",
                "followup": "能举个例子吗？",
                "options": [],
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalSurveyStore(tmpdir)
        campaign = store.create_campaign(
            Campaign(
                invite_code="DL-TEST",
                title="产品体验调研",
                agent=agent,
                max_respondents=2,
            )
        )

        loaded = store.get_campaign_by_code("dl-test")
        assert loaded is not None
        assert loaded.campaign_id == campaign.campaign_id
        assert loaded.creator_storage["provider"] == "local_simulated_cloud"
        assert loaded.developer_feedback_enabled is True
        assert loaded.developer_raw_access_allowed is True
        creator_project_dir = Path(tmpdir) / "cloud" / "creators" / campaign.campaign_id
        assert (creator_project_dir / "campaign.json").exists()

        response = ResponseRecord(
            campaign_id=campaign.campaign_id,
            respondent_id="u1",
            answers=[{"question": "Q", "answer": "A"}],
            decision_logs=[{"arbitration_result": {"strategy": "proceed"}}],
        )
        store.save_response(response)

        responses = store.list_responses(campaign.campaign_id)
        assert len(responses) == 1
        assert responses[0].respondent_id == "u1"
        assert responses[0].source == "campaign"
        assert (creator_project_dir / "responses" / f"{response.response_id}.json").exists()
        assert not (Path(tmpdir) / "responses" / campaign.campaign_id / f"{response.response_id}.json").exists()

        feedback = DeveloperFeedbackRecord(
            feedback_id=f"campaign_{campaign.campaign_id}",
            source="campaign",
            campaign_id=campaign.campaign_id,
            title=campaign.title,
            response_count=1,
            raw_access_allowed=True,
            creator_storage=loaded.creator_storage,
        )
        store.save_developer_feedback(feedback)
        feedback_records = store.list_developer_feedback()
        assert len(feedback_records) == 1
        assert feedback_records[0].response_count == 1
        assert feedback_records[0].creator_storage["provider"] == "local_simulated_cloud"

    print("Survey store OK")


def test_survey_store_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
