"""Secure API credential handling for the project-specific Qwen service."""

from __future__ import annotations

import csv
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


KEYCHAIN_SERVICE = "net.urbancomp.sakugis.qwen"
KEYCHAIN_ACCOUNT = "UrbanComp"
POSTGIS_KEYCHAIN_SERVICE = "net.urbancomp.sakugis.postgis"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"


class CredentialError(RuntimeError):
    """Raised when a credential cannot be read or stored."""


@dataclass(frozen=True)
class ApiProfile:
    api_key: str
    base_url: str
    workspace_id: str = ""


def _read_profile_values(path: str) -> Dict[str, str]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise CredentialError("找不到 API 配置 CSV。")

    values: Dict[str, str] = {}
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2:
                    values[row[0].strip()] = row[1].strip()
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CredentialError("无法读取 API 配置 CSV。") from exc
    return values


def load_profile_csv(path: str) -> ApiProfile:
    """Read the Alibaba Cloud profile without logging any secret values."""

    values = _read_profile_values(path)
    api_key = values.get("apiKey", "")
    base_url = values.get("openAiCompatible", "") or DEFAULT_BASE_URL
    if len(api_key) < 20:
        raise CredentialError("CSV 中没有有效的 apiKey。")
    if not base_url.startswith("https://"):
        raise CredentialError("CSV 中的 OpenAI 兼容地址无效。")
    return ApiProfile(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        workspace_id=values.get("workspaceId", ""),
    )


def store_api_key(api_key: str) -> None:
    """Store the API key in the current user's macOS Keychain."""

    key = api_key.strip()
    if len(key) < 20 or "\n" in key or "\r" in key:
        raise CredentialError("API Key 格式无效。")
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
                key,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CredentialError("无法访问 macOS 钥匙串。") from exc
    if result.returncode != 0:
        raise CredentialError("API Key 写入 macOS 钥匙串失败。")


def import_profile_csv(path: str) -> ApiProfile:
    profile = load_profile_csv(path)
    store_api_key(profile.api_key)
    return profile


def get_api_key() -> str:
    """Resolve a key from the environment first, then macOS Keychain."""

    environment_key = os.environ.get("SAKUGIS_QWEN_API_KEY") or os.environ.get(
        "DASHSCOPE_API_KEY"
    )
    if environment_key:
        return environment_key.strip()

    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CredentialError("无法访问 macOS 钥匙串。") from exc

    key = result.stdout.strip() if result.returncode == 0 else ""
    if not key:
        raise CredentialError("尚未配置千问 API Key。")
    return key


def has_api_key() -> bool:
    try:
        return bool(get_api_key())
    except CredentialError:
        return False


def configured_base_url() -> str:
    return os.environ.get("SAKUGIS_QWEN_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def configured_model() -> str:
    return os.environ.get("SAKUGIS_QWEN_MODEL", DEFAULT_MODEL).strip()


def store_postgis_dsn(dsn: str) -> None:
    value = dsn.strip()
    if not value or "\n" in value or "\r" in value:
        raise CredentialError("PostGIS DSN 格式无效。")
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                POSTGIS_KEYCHAIN_SERVICE,
                "-w",
                value,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CredentialError("无法访问 macOS 钥匙串。") from exc
    if result.returncode != 0:
        raise CredentialError("PostGIS 配置写入 macOS 钥匙串失败。")


def get_postgis_dsn() -> str:
    configured = os.environ.get("SAKUGIS_POSTGIS_DSN")
    if configured:
        return configured.strip()
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                POSTGIS_KEYCHAIN_SERVICE,
                "-w",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def has_postgis_dsn() -> bool:
    return bool(get_postgis_dsn())
