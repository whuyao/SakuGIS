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
    configured_prompt_char_limit,
    configured_qwen_temperature,
    configured_qwen_timeout,
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


def _safe_image_data_url(path: str, max_dimension: int = 2048) -> str:
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
                    str(max_dimension),
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
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_prompt_chars: Optional[int] = None,
    ):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or configured_base_url()).rstrip("/")
        self.model = model or configured_model()
        self.timeout = (
            max(30, min(300, int(timeout)))
            if timeout is not None
            else configured_qwen_timeout()
        )
        self.temperature = (
            max(0.0, min(1.0, float(temperature)))
            if temperature is not None
            else configured_qwen_temperature()
        )
        self.max_prompt_chars = (
            max(128, int(max_prompt_chars))
            if max_prompt_chars is not None
            else configured_prompt_char_limit()
        )
        self.last_request_stats: Dict[str, int] = {}

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
        user_content: Any = user_prompt
        paths = list(image_paths or ())
        if image_path and image_path not in paths:
            paths.insert(0, image_path)
        paths = list(dict.fromkeys(path for path in paths if path))
        image_dimension = _image_dimension_for_count(len(paths))
        if paths:
            user_content = []
            for index, path in enumerate(paths, 1):
                user_content.extend(
                    [
                        {
                            "type": "text",
                            "text": f"[Attached image {index}]",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _safe_image_data_url(
                                    path, image_dimension
                                )
                            },
                        },
                    ]
                )
            user_content.append({"type": "text", "text": user_prompt})

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
        }
        self.last_request_stats = {
            "prompt_chars": prompt_chars,
            "image_count": len(paths),
            "image_max_dimension": image_dimension if paths else 0,
            "max_output_tokens": int(max_tokens),
            "message_count": 2,
            "retry_count": 0,
        }
        for attempt in range(2):
            response = self._post("/chat/completions", payload)
            try:
                return extract_json_object(_response_text(response))
            except QwenApiError:
                if attempt:
                    raise
                self.last_request_stats["retry_count"] = 1
                payload["temperature"] = 0
                payload["max_tokens"] = min(
                    8192, max(int(max_tokens), 4096)
                )
                retry_instruction = (
                    "\n\nThe previous response was not valid complete JSON. "
                    "Retry once with compact strings and a complete JSON object. "
                    "Do not add Markdown or commentary."
                )
                if prompt_chars + len(retry_instruction) <= self.max_prompt_chars:
                    payload["messages"][0]["content"] = (
                        system_prompt + retry_instruction
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
            error_body = ""
            try:
                error_body = exc.read(4096).decode("utf-8", errors="ignore")
            except (AttributeError, OSError):
                pass
            if exc.code == 401:
                message = tr("error.api_unauthorized")
            elif exc.code == 429:
                message = tr("error.api_rate_limit")
            elif exc.code in {400, 413, 422} and _is_context_error(
                error_body
            ):
                message = tr("error.api_context_length")
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

def _response_text(response: Dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise QwenApiError(tr("error.api_content")) from exc
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict)
        )
    if not isinstance(content, str):
        raise QwenApiError(tr("error.api_message_format"))
    return content


def _image_dimension_for_count(image_count: int) -> int:
    if image_count <= 1:
        return 2048
    if image_count == 2:
        return 1792
    if image_count <= 4:
        return 1536
    return 1280


def _is_context_error(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "context length",
            "maximum context",
            "max context",
            "too many tokens",
            "prompt is too long",
            "input is too long",
            "上下文",
            "令牌过多",
        )
    )
