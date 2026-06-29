import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.github_auth import (
    DEFAULT_DEVELOPER_USER_ID,
    GitHubOAuthConfig,
    GitHubUser,
    build_github_authorize_url,
    is_allowed_developer,
    load_github_oauth_config,
)


def main() -> None:
    config = GitHubOAuthConfig(
        client_id="client-id",
        client_secret="client-secret",
        allowed_login="sunrise-yc",
        allowed_user_id=DEFAULT_DEVELOPER_USER_ID,
    )

    authorize_url = build_github_authorize_url(config, "http://localhost:8503/?page=developer", "state-123")
    params = parse_qs(urlsplit(authorize_url).query)
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == ["http://localhost:8503/?page=developer"]
    assert params["state"] == ["state-123"]
    assert params["allow_signup"] == ["false"]

    assert is_allowed_developer(config, GitHubUser(login="sunrise-yc", user_id=292528736))
    assert not is_allowed_developer(config, GitHubUser(login="someone-else", user_id=292528736))
    assert not is_allowed_developer(config, GitHubUser(login="sunrise-yc", user_id=1))

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "developer_auth.json"
        config_file.write_text(
            json.dumps(
                {
                    "github_oauth": {
                        "client_id": "file-client",
                        "client_secret": "file-secret",
                        "redirect_uri": "http://localhost:8503/?page=developer",
                    }
                }
            ),
            encoding="utf-8",
        )
        loaded = load_github_oauth_config(config_file, secrets={}, env={})
        assert loaded is not None
        assert loaded.client_id == "file-client"
        assert loaded.client_secret == "file-secret"
        assert loaded.allowed_login == "sunrise-yc"
        assert loaded.allowed_user_id == 292528736

        env_loaded = load_github_oauth_config(
            Path(tmpdir) / "missing.json",
            secrets={},
            env={
                "DEEPLISTER_GITHUB_CLIENT_ID": "env-client",
                "DEEPLISTER_GITHUB_CLIENT_SECRET": "env-secret",
                "DEEPLISTER_DEVELOPER_GITHUB_LOGIN": "sunrise-yc",
                "DEEPLISTER_DEVELOPER_GITHUB_ID": "292528736",
            },
        )
        assert env_loaded is not None
        assert env_loaded.client_id == "env-client"
        assert env_loaded.client_secret == "env-secret"

    print("GitHub auth OK")


if __name__ == "__main__":
    main()
