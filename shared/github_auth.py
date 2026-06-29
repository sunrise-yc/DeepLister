import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

import requests


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
DEFAULT_DEVELOPER_LOGIN = "sunrise-yc"
DEFAULT_DEVELOPER_USER_ID = 292528736


class GitHubOAuthError(Exception):
    """Raised when GitHub OAuth cannot be completed safely."""


@dataclass(frozen=True)
class GitHubOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str = ""
    allowed_login: str = DEFAULT_DEVELOPER_LOGIN
    allowed_user_id: int = DEFAULT_DEVELOPER_USER_ID


@dataclass(frozen=True)
class GitHubUser:
    login: str
    user_id: int
    html_url: str = ""


def _mapping_get(source: Mapping[str, Any] | None, key: str, default: Any = "") -> Any:
    if source is None:
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def _load_json_config(config_file: Path) -> dict:
    if not config_file.exists():
        return {}
    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_github_oauth_config(
    config_file: Path,
    secrets: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> GitHubOAuthConfig | None:
    env = os.environ if env is None else env
    file_data = _load_json_config(config_file)
    file_group = file_data.get("github_oauth", file_data)
    secret_group = _mapping_get(secrets, "github_oauth", {})

    client_id = (
        env.get("DEEPLISTER_GITHUB_CLIENT_ID")
        or _mapping_get(secret_group, "client_id")
        or _mapping_get(file_group, "client_id")
    )
    client_secret = (
        env.get("DEEPLISTER_GITHUB_CLIENT_SECRET")
        or _mapping_get(secret_group, "client_secret")
        or _mapping_get(file_group, "client_secret")
    )
    if not client_id or not client_secret:
        return None

    redirect_uri = (
        env.get("DEEPLISTER_GITHUB_REDIRECT_URI")
        or _mapping_get(secret_group, "redirect_uri")
        or _mapping_get(file_group, "redirect_uri")
        or ""
    )
    allowed_login = (
        env.get("DEEPLISTER_DEVELOPER_GITHUB_LOGIN")
        or _mapping_get(secret_group, "allowed_login")
        or _mapping_get(file_group, "allowed_login")
        or DEFAULT_DEVELOPER_LOGIN
    )
    allowed_user_id = _as_int(
        env.get("DEEPLISTER_DEVELOPER_GITHUB_ID")
        or _mapping_get(secret_group, "allowed_user_id")
        or _mapping_get(file_group, "allowed_user_id"),
        DEFAULT_DEVELOPER_USER_ID,
    )

    return GitHubOAuthConfig(
        client_id=str(client_id),
        client_secret=str(client_secret),
        redirect_uri=str(redirect_uri),
        allowed_login=str(allowed_login).strip().lower(),
        allowed_user_id=allowed_user_id,
    )


def build_github_authorize_url(config: GitHubOAuthConfig, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "allow_signup": "false",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(config: GitHubOAuthConfig, code: str, redirect_uri: str) -> str:
    try:
        response = requests.post(
            GITHUB_ACCESS_TOKEN_URL,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise GitHubOAuthError("无法连接 GitHub 完成授权。") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise GitHubOAuthError("GitHub 返回了无法解析的授权结果。") from exc

    if response.status_code >= 400 or payload.get("error"):
        message = payload.get("error_description") or payload.get("error") or "GitHub 授权失败。"
        raise GitHubOAuthError(str(message))

    token = payload.get("access_token")
    if not token:
        raise GitHubOAuthError("GitHub 没有返回 access token。")
    return str(token)


def fetch_authenticated_user(access_token: str) -> GitHubUser:
    try:
        response = requests.get(
            GITHUB_USER_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=12,
        )
    except requests.RequestException as exc:
        raise GitHubOAuthError("无法读取 GitHub 当前用户。") from exc

    if response.status_code >= 400:
        raise GitHubOAuthError("GitHub 当前用户校验失败。")

    try:
        payload = response.json()
    except ValueError as exc:
        raise GitHubOAuthError("GitHub 返回了无法解析的用户信息。") from exc

    login = str(payload.get("login", "")).strip()
    user_id = _as_int(payload.get("id"), 0)
    if not login or not user_id:
        raise GitHubOAuthError("GitHub 用户信息不完整。")
    return GitHubUser(login=login, user_id=user_id, html_url=str(payload.get("html_url", "")))


def is_allowed_developer(config: GitHubOAuthConfig, user: GitHubUser) -> bool:
    return user.login.lower() == config.allowed_login.lower() and user.user_id == config.allowed_user_id
