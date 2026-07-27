#!/usr/bin/env python3
"""Import a SakuGIS Alibaba Cloud API profile into macOS Keychain."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sakugis.credentials import CredentialError, import_profile_csv  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：scripts/import-api-key.py <阿里云 API 配置.csv>", file=sys.stderr)
        return 2
    try:
        import_profile_csv(sys.argv[1])
    except CredentialError as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        return 1
    print("千问 API Key 已安全保存到 macOS 钥匙串。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
