"""Small dependency-free client for Alibaba Cloud's OpenAI-compatible API."""

from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from sakugis.credentials import (
    configured_base_url,
    configured_model,
    get_api_key,
)
from sakugis.i18n import tr


class QwenApiError(RuntimeError):
    """A safe, user-facing API error that never contains credentials."""


def extract_json_object(text: str) -> Dict[str, Any]:
    """Decode a JSON object even when a model wraps it in Markdown fences."""

    candidate = text.strip()
    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        last_fence = candidate.rfind("```")
        if first_newline >= 0 and last_fence > first_newline:
            candidate = candidate[first_newline + 1 : last_fence].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise QwenApiError(tr("error.no_json"))
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise QwenApiError(tr("error.invalid_json")) from exc
    if not isinstance(value, dict):
        raise QwenApiError(tr("error.not_json_object"))
    return value


def _safe_image_data_url(path: str) -> str:
    """Resize input to a predictable JPEG before Base64 upload."""

    source = Path(path)
    if not source.is_file():
        raise QwenApiError(tr("error.image_missing"))
    if source.stat().st_size > 100 * 1024 * 1024:
        raise QwenApiError(tr("error.image_too_large"))

    with tempfile.TemporaryDirectory(prefix="sakugis-image-") as temp_dir:
        output = Path(temp_dir) / "upload.jpg"
        try:
            result = subprocess.run(
                [
                    "/usr/bin/sips",
                    "-Z",
                    "2048",
                    "--setProperty",
                    "format",
                    "jpeg",
                    "--setProperty",
                    "formatOptions",
                    "82",
                    str(source),
                    "--out",
                    str(output),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise QwenApiError(tr("error.image_process")) from exc
        if result.returncode != 0 or not output.is_file():
            mime = mimetypes.guess_type(str(source))[0] or ""
            if mime not in {"image/jpeg", "image/png", "image/webp"}:
                raise QwenApiError(tr("error.image_format"))
            raw = source.read_bytes()
            mime_type = mime
        else:
            raw = output.read_bytes()
            mime_type = "image/jpeg"

    encoded = base64.b64encode(raw).decode("ascii")
    if len(encoded) > 10 * 1024 * 1024:
        raise QwenApiError(tr("error.image_api_limit"))
    return f"data:{mime_type};base64,{encoded}"


class QwenClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or configured_base_url()).rstrip("/")
        self.model = model or configured_model()
        self.timeout = timeout

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str = "",
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        user_content: Any = user_prompt
        if image_path:
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {"url": _safe_image_data_url(image_path)},
                },
                {"type": "text", "text": user_prompt},
            ]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.15,
            "max_tokens": max_tokens,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
        }
        response = self._post("/chat/completions", payload)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenApiError(tr("error.api_content")) from exc
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str):
            raise QwenApiError(tr("error.api_message_format"))
        return extract_json_object(content)

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
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + route,
            data=body,
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
            if exc.code == 401:
                message = tr("error.api_unauthorized")
            elif exc.code == 429:
                message = tr("error.api_rate_limit")
            else:
                message = tr("error.api_http", code=exc.code)
            raise QwenApiError(message) from exc
        except urllib.error.URLError as exc:
            raise QwenApiError(tr("error.api_network")) from exc
        except TimeoutError as exc:
            raise QwenApiError(tr("error.api_timeout")) from exc
        except (ValueError, OSError) as exc:
            raise QwenApiError(tr("error.api_response")) from exc
        if not isinstance(payload, dict):
            raise QwenApiError(tr("error.api_invalid_response"))
        return payload
