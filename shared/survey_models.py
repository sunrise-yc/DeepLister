from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Campaign(BaseModel):
    """A survey project created by a researcher and shared with respondents."""

    campaign_id: str = Field(default_factory=lambda: new_id("camp"))
    invite_code: str
    manage_token: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    description: str = ""
    agent: dict[str, Any]
    max_respondents: int = 20
    llm_enabled: bool = False
    max_llm_calls_per_response: int = 0
    storage_mode: str = "local"
    creator_storage: dict[str, Any] = Field(default_factory=dict)
    developer_feedback_enabled: bool = True
    developer_raw_access_allowed: bool = True
    developer_feedback_synced_at: str = ""
    created_at: str = Field(default_factory=now_iso)


class ResponseRecord(BaseModel):
    """A single completed survey response."""

    response_id: str = Field(default_factory=lambda: new_id("resp"))
    campaign_id: str
    respondent_id: str
    source: str = "campaign"
    agent_title: str = ""
    invite_code: str = ""
    topic: str = ""
    question_count: int = 0
    llm_enabled: bool = False
    engine_mode: str = "rules"
    answers: list[dict[str, Any]] = Field(default_factory=list)
    decision_logs: list[dict[str, Any]] = Field(default_factory=list)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    llm_call_count: int = 0
    completed_at: str = Field(default_factory=now_iso)


class DeveloperLogPackage(BaseModel):
    """A user-authorized package for developer review."""

    log_id: str = Field(default_factory=lambda: new_id("devlog"))
    source: str
    campaign_id: str | None = None
    response_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    labels: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class DeveloperFeedbackRecord(BaseModel):
    """Anonymous product feedback synced into the developer storage."""

    feedback_id: str
    source: str
    campaign_id: str | None = None
    invite_code: str = ""
    title: str = ""
    topic: str = ""
    response_count: int = 0
    respondent_count: int = 0
    answer_count: int = 0
    turn_count: int = 0
    followup_count: int = 0
    followup_rate: float = 0.0
    vague_rate: float = 0.0
    llm_call_count: int = 0
    topics: dict[str, int] = Field(default_factory=dict)
    strategies: dict[str, int] = Field(default_factory=dict)
    trace_summary: list[dict[str, Any]] = Field(default_factory=list)
    raw_access_allowed: bool = False
    creator_storage: dict[str, Any] = Field(default_factory=dict)
    synced_at: str = Field(default_factory=now_iso)
