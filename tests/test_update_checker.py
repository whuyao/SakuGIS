import json
import unittest

from sakugis.update_checker import (
    UpdateCheckError,
    fetch_update_status,
    parse_release_payload,
    version_tuple,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def release(version, draft=False, asset=True):
    assets = []
    if asset:
        assets.append(
            {
                "name": f"SakuGIS-{version}-Apple-Silicon.dmg",
                "browser_download_url": (
                    "https://github.com/whuyao/SakuGIS/releases/download/"
                    f"v{version}/SakuGIS-{version}-Apple-Silicon.dmg"
                ),
            }
        )
    return {
        "tag_name": f"v{version}",
        "name": f"SakuGIS {version}",
        "draft": draft,
        "prerelease": True,
        "html_url": (
            f"https://github.com/whuyao/SakuGIS/releases/tag/v{version}"
        ),
        "assets": assets,
    }


class UpdateCheckerTests(unittest.TestCase):
    def test_semantic_versions_are_compared_numerically(self):
        self.assertGreater(version_tuple("v0.10.0"), version_tuple("0.9.9"))

    def test_latest_published_release_includes_prereleases(self):
        status = parse_release_payload(
            [
                release("0.3.1"),
                release("0.4.0", draft=True),
                release("0.3.2"),
            ],
            "0.3.1",
        )
        self.assertTrue(status.update_available)
        self.assertEqual(status.latest_version, "0.3.2")
        self.assertTrue(status.download_url.endswith("Apple-Silicon.dmg"))

    def test_current_release_is_reported_as_up_to_date(self):
        status = parse_release_payload([release("0.3.1")], "0.3.1")
        self.assertFalse(status.update_available)

    def test_fetch_uses_github_api_and_sakugis_user_agent(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["agent"] = request.get_header("User-agent")
            captured["timeout"] = timeout
            return FakeResponse([release("0.3.1")])

        status = fetch_update_status("0.3.1", timeout=4, opener=opener)
        self.assertIn("api.github.com/repos/whuyao/SakuGIS", captured["url"])
        self.assertIn("SakuGIS/0.3.1", captured["agent"])
        self.assertEqual(captured["timeout"], 4)
        self.assertFalse(status.update_available)

    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(UpdateCheckError):
            parse_release_payload({}, "0.3.1")


if __name__ == "__main__":
    unittest.main()
