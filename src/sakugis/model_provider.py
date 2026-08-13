"""Select the configured multimodal model provider without exposing secrets."""

from __future__ import annotations

import os
from typing import Any, Optional

from sakugis.credentials import (
    configured_kimi_reasoning_effort,
    configured_kimi_model,
    configured_model,
    has_api_key,
    has_kimi_api_key,
)

QWEN = "qwen"
KIMI = "kimi"


def configured_provider() -> str:
    value = os.environ.get("SAKUGIS_MODEL_PROVIDER", QWEN).strip().lower()
    return value if value in {QWEN, KIMI} else QWEN


def provider_display_name(provider: Optional[str] = None) -> str:
    return "Kimi" if (provider or configured_provider()) == KIMI else "Qwen"


def configured_active_model() -> str:
    if configured_provider() == KIMI:
        return (
            f"{configured_kimi_model()} "
            f"({configured_kimi_reasoning_effort()})"
        )
    return configured_model()


def has_active_api_key() -> bool:
    return has_kimi_api_key() if configured_provider() == KIMI else has_api_key()


def create_model_client() -> Any:
    if configured_provider() == KIMI:
        from sakugis.kimi_client import KimiClient

        return KimiClient()
    from sakugis.qwen_client import QwenClient

    return QwenClient()
