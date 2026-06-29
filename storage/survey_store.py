import json
from pathlib import Path

from shared.config import Config
from shared.survey_models import Campaign, DeveloperFeedbackRecord, DeveloperLogPackage, ResponseRecord
from storage.cloud_storage import CreatorProjectStorage, DeveloperFeedbackStorage


class SurveyStore:
    def create_campaign(self, campaign: Campaign) -> Campaign:
        raise NotImplementedError

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        raise NotImplementedError

    def get_campaign_by_code(self, invite_code: str) -> Campaign | None:
        raise NotImplementedError

    def list_campaigns(self) -> list[Campaign]:
        raise NotImplementedError

    def save_response(self, response: ResponseRecord) -> None:
        raise NotImplementedError

    def list_responses(self, campaign_id: str) -> list[ResponseRecord]:
        raise NotImplementedError

    def list_all_responses(self) -> list[ResponseRecord]:
        raise NotImplementedError

    def save_developer_feedback(self, record: DeveloperFeedbackRecord) -> None:
        raise NotImplementedError

    def list_developer_feedback(self) -> list[DeveloperFeedbackRecord]:
        raise NotImplementedError

    def save_result_export(self, campaign: Campaign, responses: list[ResponseRecord], metrics: dict) -> None:
        raise NotImplementedError

    def creator_storage_descriptor(self, campaign_id: str) -> dict:
        raise NotImplementedError

    def developer_storage_descriptor(self) -> dict:
        raise NotImplementedError

    def save_developer_log(self, package: DeveloperLogPackage) -> None:
        raise NotImplementedError

    def list_developer_logs(self) -> list[DeveloperLogPackage]:
        raise NotImplementedError


class LocalSurveyStore(SurveyStore):
    """JSON-backed store used for local demo and development."""

    def __init__(self, base_dir: str | Path | None = None):
        Config.ensure_dirs()
        self.base_dir = Path(base_dir or Config.DATA_DIR)
        self.campaign_dir = self.base_dir / "campaigns"
        self.response_dir = self.base_dir / "responses"
        self.developer_dir = self.base_dir / "developer_logs"
        self.creator_storage = CreatorProjectStorage(self.base_dir / "cloud" / "creators")
        self.developer_feedback_storage = DeveloperFeedbackStorage(self.base_dir / "cloud" / "developer")
        for path in [self.campaign_dir, self.response_dir, self.developer_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def create_campaign(self, campaign: Campaign) -> Campaign:
        if not campaign.creator_storage:
            campaign.creator_storage = self.creator_storage.storage_descriptor(campaign.campaign_id)
        self._write_json(self.campaign_dir / f"{campaign.campaign_id}.json", campaign.model_dump(mode="json"))
        self.creator_storage.save_campaign(campaign)
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        path = self.campaign_dir / f"{campaign_id}.json"
        if not path.exists():
            return None
        return Campaign.model_validate(self._read_json(path))

    def get_campaign_by_code(self, invite_code: str) -> Campaign | None:
        normalized = invite_code.strip().upper()
        for campaign in self.list_campaigns():
            if campaign.invite_code.upper() == normalized:
                return campaign
        return None

    def list_campaigns(self) -> list[Campaign]:
        campaigns = []
        for path in sorted(self.campaign_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                campaigns.append(Campaign.model_validate(self._read_json(path)))
            except Exception:
                continue
        return campaigns

    def save_response(self, response: ResponseRecord) -> None:
        if not response.campaign_id.startswith("system_"):
            self.creator_storage.save_response(response)
            return
        target_dir = self.response_dir / response.campaign_id
        target_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(target_dir / f"{response.response_id}.json", response.model_dump(mode="json"))

    def list_responses(self, campaign_id: str) -> list[ResponseRecord]:
        if not campaign_id.startswith("system_"):
            creator_responses = self.creator_storage.list_responses(campaign_id)
            if creator_responses:
                return creator_responses
        target_dir = self.response_dir / campaign_id
        if not target_dir.exists():
            return []
        responses = []
        for path in sorted(target_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                responses.append(ResponseRecord.model_validate(self._read_json(path)))
            except Exception:
                continue
        return responses

    def list_all_responses(self) -> list[ResponseRecord]:
        responses = []
        for campaign_dir in self.response_dir.glob("*"):
            if campaign_dir.is_dir():
                responses.extend(self.list_responses(campaign_dir.name))
        for campaign in self.list_campaigns():
            responses.extend(self.creator_storage.list_responses(campaign.campaign_id))
        return sorted(responses, key=lambda item: item.completed_at, reverse=True)

    def save_developer_feedback(self, record: DeveloperFeedbackRecord) -> None:
        self.developer_feedback_storage.save_feedback(record)

    def list_developer_feedback(self) -> list[DeveloperFeedbackRecord]:
        return self.developer_feedback_storage.list_feedback()

    def save_result_export(self, campaign: Campaign, responses: list[ResponseRecord], metrics: dict) -> None:
        self.creator_storage.write_result_export(campaign, responses, metrics)

    def creator_storage_descriptor(self, campaign_id: str) -> dict:
        return self.creator_storage.storage_descriptor(campaign_id)

    def developer_storage_descriptor(self) -> dict:
        return self.developer_feedback_storage.storage_descriptor()

    def save_developer_log(self, package: DeveloperLogPackage) -> None:
        self._write_json(self.developer_dir / f"{package.log_id}.json", package.model_dump(mode="json"))

    def list_developer_logs(self) -> list[DeveloperLogPackage]:
        packages = []
        for path in sorted(self.developer_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                packages.append(DeveloperLogPackage.model_validate(self._read_json(path)))
            except Exception:
                continue
        return packages

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_survey_store() -> SurveyStore:
    return LocalSurveyStore()
