"""Dependency-free client for Moonshot's OpenAI-compatible Kimi API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from sakugis.credentials import (
    configured_kimi_base_url,
    configured_kimi_model,
    configured_kimi_reasoning_effort,
    configured_kimi_timeout,
    configured_prompt_char_limit,
    get_kimi_api_key,
)
from sakugis.i18n import tr
from sakugis.qwen_client import (
    QwenApiError,
    _image_dimension_for_count,
    _response_text,
    _safe_image_data_url,
    extract_json_object,
)


class KimiClient:
    """K3 adapter with explicit reasoning effort and safe JSON retries."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        timeout: Optional[int] = None,
        max_prompt_chars: Optional[int] = None,
    ):
        self.api_key = api_key or get_kimi_api_key()
        self.base_url = (base_url or configured_kimi_base_url()).rstrip("/")
        self.model = model or configured_kimi_model()
        effort = (reasoning_effort or configured_kimi_reasoning_effort()).lower()
        self.reasoning_effort = (
            effort if effort in {"low", "high", "max"} else "high"
        )
        self.model_description = f"{self.model} ({self.reasoning_effort})"
        self.timeout = (
            max(30, min(600, int(timeout)))
            if timeout is not None
            else configured_kimi_timeout()
        )
        self.max_prompt_chars = (
            max(128, int(max_prompt_chars))
            if max_prompt_chars is not None
            else configured_prompt_char_limit()
        )
        self.last_request_stats: Dict[str, int | str] = {}

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str = "",
        image_paths: Optional[List[str]] = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        prompt_chars = len(system_prompt) + len(user_prompt)
        if prompt_chars > self.max_prompt_chars:
            raise QwenApiError(
                tr(
                    "error.prompt_too_long",
                    actual=prompt_chars,
                    maximum=self.max_prompt_chars,
                )
            )

        paths = list(image_paths or ())
        if image_path and image_path not in paths:
            paths.insert(0, image_path)
        paths = list(dict.fromkeys(path for path in paths if path))
        image_dimension = _image_dimension_for_count(len(paths))
        user_content: Any = user_prompt
        if paths:
            user_content = []
            for index, path in enumerate(paths, 1):
                user_content.extend(
                    [
                        {"type": "text", "text": f"[Attached image {index}]"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _safe_image_data_url(path, image_dimension)
                            },
                        },
                    ]
                )
            user_content.append({"type": "text", "text": user_prompt})

        # K3 is a thinking-only model. Reserve enough output space for hidden
        # reasoning so a valid JSON answer is not truncated before it begins.
        minimum_budget = 8192 if self.reasoning_effort == "max" else 6144
        effective_tokens = max(int(max_tokens), minimum_budget)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": effective_tokens,
            "response_format": {"type": "json_object"},
        }
        self.last_request_stats = {
            "prompt_chars": prompt_chars,
            "image_count": len(paths),
            "image_max_dimension": image_dimension if paths else 0,
            "max_output_tokens": effective_tokens,
            "message_count": 2,
            "retry_count": 0,
            "reasoning_effort": self.reasoning_effort,
        }
        for attempt in range(2):
            response = self._post("/chat/completions", payload)
            try:
                return extract_json_object(_response_text(response))
            except QwenApiError:
                if attempt:
                    raise
                self.last_request_stats["retry_count"] = 1
                payload["max_tokens"] = max(effective_tokens, 12288)
                payload["messages"][0]["content"] = (
                    system_prompt
                    + "\n\nReturn one compact, complete JSON object. "
                    "Do not add Markdown or commentary."
                )
        raise QwenApiError(tr("error.invalid_json"))

    def list_models(self) -> List[str]:
        request = urllib.request.Request(self.base_url + "/models")
        request.add_header("Authorization", "Bearer " + self.api_key)
        response = self._open(request)
        return sorted(
            item["id"]
            for item in response.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )

    def _post(self, route: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + route,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        request.add_header("Authorization", "Bearer " + self.api_key)
        request.add_header("Content-Type", "application/json")
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                message = tr("error.api_unauthorized", provider="Kimi")
            elif exc.code == 429:
                message = tr("error.api_rate_limit", provider="Kimi")
            else:
                message = tr("error.api_http", provider="Kimi", code=exc.code)
            raise QwenApiError(message) from exc
        except urllib.error.URLError as exc:
            raise QwenApiError(
                tr("error.api_network", provider="Kimi")
            ) from exc
        except TimeoutError as exc:
            raise QwenApiError(
                tr("error.api_timeout", provider="Kimi")
            ) from exc
        except (ValueError, OSError) as exc:
            raise QwenApiError(
                tr("error.api_response", provider="Kimi")
            ) from exc
        if not isinstance(payload, dict):
            raise QwenApiError(
                tr("error.api_invalid_response", provider="Kimi")
            )
        return payload
