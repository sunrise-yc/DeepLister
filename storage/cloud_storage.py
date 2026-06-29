import json
from pathlib import Path

from shared.config import Config
from shared.survey_models import Campaign, DeveloperFeedbackRecord, ResponseRecord


class CreatorProjectStorage:
    """Storage owned by the survey creator. V1 uses local folders to simulate cloud drive space."""

    provider = "local_simulated_cloud"

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or Path(Config.DATA_DIR) / "cloud" / "creators")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def storage_descriptor(self, campaign_id: str) -> dict:
        return {
            "provider": self.provider,
            "label": "发起者云盘（本地模拟）",
            "path": str(self.project_dir(campaign_id)),
        }

    def project_dir(self, campaign_id: str) -> Path:
        return self.base_dir / campaign_id

    def save_campaign(self, campaign: Campaign) -> None:
        project_dir = self.project_dir(campaign.campaign_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(project_dir / "campaign.json", campaign.model_dump(mode="json"))

    def save_response(self, response: ResponseRecord) -> None:
        response_dir = self.project_dir(response.campaign_id) / "responses"
        response_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(response_dir / f"{response.response_id}.json", response.model_dump(mode="json"))

    def list_responses(self, campaign_id: str) -> list[ResponseRecord]:
        response_dir = self.project_dir(campaign_id) / "responses"
        if not response_dir.exists():
            return []
        responses = []
        for path in sorted(response_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                responses.append(ResponseRecord.model_validate(self._read_json(path)))
            except Exception:
                continue
        return responses

    def write_result_export(self, campaign: Campaign, responses: list[ResponseRecord], metrics: dict) -> None:
        export_dir = self.project_dir(campaign.campaign_id) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            export_dir / "latest_result_summary.json",
            {
                "campaign": campaign.model_dump(mode="json"),
                "metrics": metrics,
                "responses": [response.model_dump(mode="json") for response in responses],
            },
        )

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class DeveloperFeedbackStorage:
    """Anonymous product feedback storage owned by the developer."""

    provider = "local_simulated_cloud"

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or Path(Config.DATA_DIR) / "cloud" / "developer")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def storage_descriptor(self) -> dict:
        return {
            "provider": self.provider,
            "label": "开发者云盘（本地模拟）",
            "path": str(self.base_dir),
        }

    def save_feedback(self, record: DeveloperFeedbackRecord) -> None:
        self._write_json(self.base_dir / f"{record.feedback_id}.json", record.model_dump(mode="json"))

    def list_feedback(self) -> list[DeveloperFeedbackRecord]:
        records = []
        for path in sorted(self.base_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                records.append(DeveloperFeedbackRecord.model_validate(self._read_json(path)))
            except Exception:
                continue
        return records

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
