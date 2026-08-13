import os
import unittest
from unittest.mock import patch

from sakugis.app_settings import load_runtime_settings, save_runtime_settings
from sakugis.candidate_retrieval import HybridCandidateRetriever
from sakugis.credentials import (
    configured_brave_timeout,
    configured_candidate_limit,
    configured_prompt_char_limit,
    configured_qwen_temperature,
    configured_qwen_timeout,
    configured_kimi_reasoning_effort,
    configured_kimi_timeout,
)
from sakugis.kimi_client import KimiClient
from sakugis.model_provider import QWEN, configured_provider
from sakugis.qwen_client import QwenClient


class MemorySettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class DisabledPostGIS:
    enabled = False


class FakeOSM:
    pass


class SettingsTests(unittest.TestCase):
    def test_qwen_remains_the_default_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_provider(), QWEN)

    def test_runtime_numeric_settings_are_validated_and_clamped(self):
        environment = {
            "SAKUGIS_QWEN_TEMPERATURE": "2.5",
            "SAKUGIS_QWEN_TIMEOUT": "5",
            "SAKUGIS_QWEN_MAX_PROMPT_CHARS": "999999",
            "SAKUGIS_AGENT_CANDIDATE_LIMIT": "0",
            "SAKUGIS_BRAVE_TIMEOUT": "not-a-number",
            "SAKUGIS_KIMI_REASONING_EFFORT": "unsupported",
            "SAKUGIS_KIMI_TIMEOUT": "9999",
        }
        with patch.dict(os.environ, environment, clear=False):
            self.assertEqual(configured_qwen_temperature(), 1.0)
            self.assertEqual(configured_qwen_timeout(), 30)
            self.assertEqual(configured_prompt_char_limit(), 120000)
            self.assertEqual(configured_candidate_limit(), 1)
            self.assertEqual(configured_brave_timeout(), 5)
            self.assertEqual(configured_kimi_reasoning_effort(), "high")
            self.assertEqual(configured_kimi_timeout(), 600)

    def test_saved_settings_apply_to_new_clients_without_restart(self):
        settings = MemorySettings()
        values = {
            "provider": "qwen",
            "base_url": "https://example.invalid/compatible-mode/v1",
            "model": "qwen-settings-test",
            "temperature": 0.25,
            "qwen_timeout": 90,
            "max_prompt_chars": 32000,
            "candidate_limit": 6,
            "brave_timeout": 9,
            "kimi_base_url": "https://api.example.invalid/v1",
            "kimi_model": "kimi-settings-test",
            "kimi_reasoning_effort": "max",
            "kimi_timeout": 240,
        }
        environment_keys = {
            "SAKUGIS_QWEN_BASE_URL": "",
            "SAKUGIS_QWEN_MODEL": "",
            "SAKUGIS_QWEN_TEMPERATURE": "",
            "SAKUGIS_QWEN_TIMEOUT": "",
            "SAKUGIS_QWEN_MAX_PROMPT_CHARS": "",
            "SAKUGIS_AGENT_CANDIDATE_LIMIT": "",
            "SAKUGIS_BRAVE_TIMEOUT": "",
            "SAKUGIS_MODEL_PROVIDER": "",
            "SAKUGIS_KIMI_BASE_URL": "",
            "SAKUGIS_KIMI_MODEL": "",
            "SAKUGIS_KIMI_REASONING_EFFORT": "",
            "SAKUGIS_KIMI_TIMEOUT": "",
        }
        with patch.dict(os.environ, environment_keys, clear=False):
            save_runtime_settings(settings, values)
            client = QwenClient(api_key="test-key-not-a-secret")
            retriever = HybridCandidateRetriever(
                osm=FakeOSM(), postgis=DisabledPostGIS()
            )
            kimi = KimiClient(api_key="test-key-not-a-secret")

            self.assertEqual(client.base_url, values["base_url"])
            self.assertEqual(client.model, values["model"])
            self.assertEqual(client.temperature, values["temperature"])
            self.assertEqual(client.timeout, values["qwen_timeout"])
            self.assertEqual(
                client.max_prompt_chars, values["max_prompt_chars"]
            )
            self.assertEqual(
                retriever.maximum_queries, values["candidate_limit"]
            )
            self.assertEqual(configured_brave_timeout(), 9)
            self.assertEqual(configured_provider(), "qwen")
            self.assertEqual(kimi.base_url, values["kimi_base_url"])
            self.assertEqual(kimi.model, values["kimi_model"])
            self.assertEqual(kimi.reasoning_effort, "max")
            self.assertEqual(kimi.timeout, 240)
            self.assertEqual(
                settings.values["sakugis/qwen/model"],
                values["model"],
            )

    def test_launch_environment_has_priority_over_persisted_values(self):
        settings = MemorySettings(
            {
                "sakugis/qwen/model": "saved-model",
                "sakugis/model/provider": "kimi",
                "sakugis/agents/candidate_limit": "4",
            }
        )
        with patch.dict(
            os.environ,
            {
                "SAKUGIS_QWEN_MODEL": "launch-model",
                "SAKUGIS_AGENT_CANDIDATE_LIMIT": "",
                "SAKUGIS_MODEL_PROVIDER": "qwen",
            },
            clear=False,
        ):
            os.environ.pop("SAKUGIS_AGENT_CANDIDATE_LIMIT", None)
            loaded = load_runtime_settings(settings)
            self.assertEqual(loaded["model"], "saved-model")
            self.assertEqual(loaded["provider"], "kimi")
            self.assertEqual(os.environ["SAKUGIS_MODEL_PROVIDER"], "qwen")
            self.assertEqual(os.environ["SAKUGIS_QWEN_MODEL"], "launch-model")
            self.assertEqual(
                os.environ["SAKUGIS_AGENT_CANDIDATE_LIMIT"], "4"
            )


if __name__ == "__main__":
    unittest.main()
