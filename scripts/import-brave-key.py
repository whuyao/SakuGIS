#!/usr/bin/env python3
"""Import a Brave Search API key from a local text file into Keychain."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sakugis.credentials import (  # noqa: E402
    CredentialError,
    store_brave_api_key,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "用法：scripts/import-brave-key.py <Brave Key 文本文件>",
            file=sys.stderr,
        )
        return 2
    try:
        key = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
        store_brave_api_key(key)
    except (CredentialError, OSError, UnicodeError) as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        return 1
    print("Brave Search API Key 已安全保存到 macOS 钥匙串。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
