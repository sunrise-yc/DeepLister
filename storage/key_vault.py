_CAMPAIGN_KEYS: dict[str, str] = {}


def put_campaign_api_key(campaign_id: str, api_key: str) -> None:
    if api_key:
        _CAMPAIGN_KEYS[campaign_id] = api_key


def get_campaign_api_key(campaign_id: str | None) -> str:
    if not campaign_id:
        return ""
    return _CAMPAIGN_KEYS.get(campaign_id, "")
