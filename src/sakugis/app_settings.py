"""Persistent non-secret application settings and runtime overrides."""

from __future__ import annotations

import os
from typing import Any, Dict

from sakugis.credentials import (
    DEFAULT_BASE_URL,
    DEFAULT_BRAVE_TIMEOUT,
    DEFAULT_CANDIDATE_LIMIT,
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_MODEL,
    DEFAULT_QWEN_TEMPERATURE,
    DEFAULT_QWEN_TIMEOUT,
)


SETTING_SPECS = {
    "base_url": (
        "sakugis/qwen/base_url",
        "SAKUGIS_QWEN_BASE_URL",
        DEFAULT_BASE_URL,
    ),
    "model": (
        "sakugis/qwen/model",
        "SAKUGIS_QWEN_MODEL",
        DEFAULT_MODEL,
    ),
    "temperature": (
        "sakugis/qwen/temperature",
        "SAKUGIS_QWEN_TEMPERATURE",
        DEFAULT_QWEN_TEMPERATURE,
    ),
    "qwen_timeout": (
        "sakugis/qwen/timeout",
        "SAKUGIS_QWEN_TIMEOUT",
        DEFAULT_QWEN_TIMEOUT,
    ),
    "max_prompt_chars": (
        "sakugis/qwen/max_prompt_chars",
        "SAKUGIS_QWEN_MAX_PROMPT_CHARS",
        DEFAULT_MAX_PROMPT_CHARS,
    ),
    "candidate_limit": (
        "sakugis/agents/candidate_limit",
        "SAKUGIS_AGENT_CANDIDATE_LIMIT",
        DEFAULT_CANDIDATE_LIMIT,
    ),
    "brave_timeout": (
        "sakugis/brave/timeout",
        "SAKUGIS_BRAVE_TIMEOUT",
        DEFAULT_BRAVE_TIMEOUT,
    ),
}


def load_runtime_settings(settings: Any) -> Dict[str, str]:
    """Hydrate environment-backed runtime configuration from QGIS settings.

    Explicit launch environment variables retain priority. Values saved from
    the settings dialog are used when no launch override exists.
    """

    loaded: Dict[str, str] = {}
    for name, (setting_key, environment_key, default) in SETTING_SPECS.items():
        value = str(settings.value(setting_key, default)).strip()
        if not value:
            value = str(default)
        loaded[name] = value
        os.environ.setdefault(environment_key, value)
    return loaded


def save_runtime_settings(settings: Any, values: Dict[str, Any]) -> None:
    """Persist non-secret values and apply them to the running process."""

    for name, (setting_key, environment_key, default) in SETTING_SPECS.items():
        value = str(values.get(name, default)).strip()
        if not value:
            value = str(default)
        settings.setValue(setting_key, value)
        os.environ[environment_key] = value
