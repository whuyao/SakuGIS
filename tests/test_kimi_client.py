import io
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from sakugis.kimi_client import KimiClient
from sakugis.qwen_client import QwenApiError, QwenClient


class RecordingKimiClient(KimiClient):
    def __init__(self, effort="high"):
        super().__init__(
            api_key="test-key-not-a-secret",
            base_url="https://example.invalid/v1",
            model="kimi-k3",
            reasoning_effort=effort,
        )
        self.payloads = []

    def _post(self, route, payload):
        self.payloads.append((route, payload.copy()))
        return {"choices": [{"message": {"content": '{"ok":true}'}}]}


class RetryingKimiClient(RecordingKimiClient):
    def _post(self, route, payload):
        self.payloads.append((route, payload.copy()))
        if len(self.payloads) == 1:
            return {"choices": [{"message": {"content": '{"partial":'}}]}
        return {"choices": [{"message": {"content": '{"ok":true}'}}]}


class KimiClientTests(unittest.TestCase):
    def test_high_uses_reasoning_effort_and_reserves_output_budget(self):
        client = RecordingKimiClient("high")
        self.assertEqual(client.chat_json("system", "user", max_tokens=1000), {"ok": True})
        route, payload = client.payloads[0]
        self.assertEqual(route, "/chat/completions")
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(payload["max_tokens"], 6144)
        self.assertNotIn("enable_thinking", payload)
        self.assertNotIn("temperature", payload)

    def test_max_reserves_larger_output_budget(self):
        client = RecordingKimiClient("max")
        client.chat_json("system", "user", max_tokens=3072)
        self.assertEqual(client.payloads[0][1]["max_tokens"], 8192)

    def test_invalid_json_retries_statelessly_with_larger_budget(self):
        client = RetryingKimiClient("high")
        self.assertEqual(client.chat_json("system", "user"), {"ok": True})
        self.assertEqual(len(client.payloads), 2)
        first = client.payloads[0][1]
        second = client.payloads[1][1]
        self.assertEqual(len(first["messages"]), 2)
        self.assertEqual(len(second["messages"]), 2)
        self.assertEqual(second["max_tokens"], 12288)
        self.assertEqual(client.last_request_stats["retry_count"], 1)

    def test_invalid_key_and_network_failures_have_distinct_messages(self):
        unauthorized = urllib.error.HTTPError(
            "https://example.invalid/v1/models",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{}'),
        )
        client = KimiClient(
            api_key="test-key-not-a-secret",
            base_url="https://example.invalid/v1",
        )
        request = urllib.request.Request("https://example.invalid/v1/models")
        with patch("urllib.request.urlopen", side_effect=unauthorized):
            with self.assertRaises(QwenApiError) as invalid_context:
                client._open(request)
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(QwenApiError) as network_context:
                client._open(request)
        self.assertIn("Kimi", str(invalid_context.exception))
        self.assertIn("无效", str(invalid_context.exception))
        self.assertIn("无法连接", str(network_context.exception))
        self.assertNotEqual(
            str(invalid_context.exception), str(network_context.exception)
        )

    def test_qwen_treats_forbidden_as_invalid_credentials(self):
        forbidden = urllib.error.HTTPError(
            "https://example.invalid/v1/models",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{}'),
        )
        client = QwenClient(
            api_key="test-key-not-a-secret",
            base_url="https://example.invalid/v1",
        )
        request = urllib.request.Request("https://example.invalid/v1/models")
        with patch("urllib.request.urlopen", side_effect=forbidden):
            with self.assertRaises(QwenApiError) as context:
                client._open(request)
        self.assertIn("Qwen", str(context.exception))
        self.assertIn("无效", str(context.exception))


if __name__ == "__main__":
    unittest.main()
