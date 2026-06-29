import json
from pathlib import Path

from shared.config import Config
from shared.types import ConsistencyFlag, SessionRecord, TopicStatus, UserProfile


class ProfileManager:
    """Reads and writes the lightweight user profile used by the Harness engine."""

    def __init__(self, profile_dir: str | None = None):
        Config.ensure_dirs()
        self.profile_dir = Path(profile_dir or Config.PROFILE_DIR)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def get_profile(self, user_id: str) -> UserProfile:
        path = self._path(user_id)
        if not path.exists():
            return UserProfile(user_id=user_id)
        try:
            return UserProfile.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return UserProfile(user_id=user_id)

    def save_profile(self, profile: UserProfile) -> None:
        self._path(profile.user_id).write_text(
            profile.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def update_topic_status(self, user_id: str, topic_id: str, updates: dict) -> UserProfile:
        profile = self.get_profile(user_id)
        status = profile.topics_status.get(topic_id, TopicStatus())
        for key, value in updates.items():
            if hasattr(status, key):
                setattr(status, key, value)
        profile.topics_status[topic_id] = status
        self.save_profile(profile)
        return profile

    def add_key_signal(self, user_id: str, topic_id: str, signal: str) -> UserProfile:
        profile = self.get_profile(user_id)
        status = profile.topics_status.get(topic_id, TopicStatus())
        if signal and signal not in status.key_signals:
            status.key_signals.append(signal)
        profile.topics_status[topic_id] = status
        self.save_profile(profile)
        return profile

    def increment_follow_up(self, user_id: str, topic_id: str) -> UserProfile:
        profile = self.get_profile(user_id)
        status = profile.topics_status.get(topic_id, TopicStatus())
        status.follow_up_count += 1
        profile.topics_status[topic_id] = status
        self.save_profile(profile)
        return profile

    def add_consistency_flag(self, user_id: str, flag: ConsistencyFlag) -> UserProfile:
        profile = self.get_profile(user_id)
        profile.consistency_flags.append(flag)
        self.save_profile(profile)
        return profile

    def update_cognitive_level(self, user_id: str, level: str) -> UserProfile:
        profile = self.get_profile(user_id)
        profile.cognitive_level = level
        self.save_profile(profile)
        return profile

    def add_session_record(self, user_id: str, record: SessionRecord) -> UserProfile:
        profile = self.get_profile(user_id)
        profile.session_history.append(record)
        self.save_profile(profile)
        return profile

    def get_topic_status(self, user_id: str, topic_id: str) -> TopicStatus | None:
        return self.get_profile(user_id).topics_status.get(topic_id)

    def _path(self, user_id: str) -> Path:
        safe_user_id = "".join(ch for ch in user_id if ch.isalnum() or ch in {"_", "-"}).strip()
        return self.profile_dir / f"{safe_user_id or 'anonymous'}.json"
