#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="0.2.0"
QGIS_APP=""
OUTPUT_DIR="$PROJECT_DIR/dist"
SIGN_IDENTITY="-"
APP_ONLY=false

usage() {
  echo "用法: $0 --qgis-app /path/to/QGIS.app [选项]"
  echo "  --output-dir DIR       输出目录，默认 ./dist"
  echo "  --app-only             仅生成 SakuGIS.app，不创建 DMG"
  echo "  --sign-identity NAME   Developer ID Application 身份，默认 ad-hoc"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --qgis-app)
      QGIS_APP="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --sign-identity)
      SIGN_IDENTITY="$2"
      shift 2
      ;;
    --app-only)
      APP_ONLY=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$QGIS_APP" || ! -d "$QGIS_APP/Contents" ]]; then
  echo "--qgis-app 必须指向有效的 QGIS.app" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
BUILD_DIR="$(mktemp -d /private/tmp/sakugis-package.XXXXXX)"
APP_PATH="$BUILD_DIR/SakuGIS.app"
DMG_STAGE="$BUILD_DIR/dmg"
DMG_PATH="$OUTPUT_DIR/SakuGIS-$VERSION.dmg"

cleanup() {
  rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

if [[ "$APP_ONLY" == false ]]; then
  mkdir -p "$DMG_STAGE"
fi

QGIS_EXECUTABLE="$QGIS_APP/Contents/MacOS/QGIS"
if [[ ! -f "$QGIS_EXECUTABLE" ]]; then
  echo "QGIS 包中缺少主程序：$QGIS_EXECUTABLE" >&2
  exit 1
fi

QGIS_ARCHITECTURES="$(lipo -archs "$QGIS_EXECUTABLE")"
if [[ " $QGIS_ARCHITECTURES " != *" arm64 "* ]]; then
  echo "SakuGIS 0.2 仅支持 Apple Silicon；QGIS 运行时缺少 arm64 架构。" >&2
  echo "检测到：$QGIS_ARCHITECTURES" >&2
  exit 1
fi

echo "复制 QGIS 运行时…"
ditto --norsrc --noqtn "$QGIS_APP" "$APP_PATH"

CONTENTS_DIR="$APP_PATH/Contents"
cp -X \
  "$CONTENTS_DIR/Info.plist" \
  "$CONTENTS_DIR/Resources/QGIS-Runtime-Info.plist"
rm -rf "$CONTENTS_DIR/_CodeSignature"
cp -X "$PROJECT_DIR/resources/Info.plist" "$CONTENTS_DIR/Info.plist"
if [[ ! -f "$PROJECT_DIR/resources/SakuGIS.icns" ]]; then
  echo "生成应用图标…"
  "$PROJECT_DIR/scripts/make-icon.sh"
fi
cp -X "$PROJECT_DIR/resources/SakuGIS.icns" "$CONTENTS_DIR/Resources/SakuGIS.icns"

echo "构建 Apple Silicon 启动器：arm64"
xcrun clang \
  -std=c11 \
  -Os \
  -Wall \
  -Wextra \
  -Werror \
  -mmacosx-version-min=13.0 \
  -arch arm64 \
  "$PROJECT_DIR/launcher/main.c" \
  -o "$CONTENTS_DIR/MacOS/SakuGIS"

rm -rf "$CONTENTS_DIR/Resources/sakugis"
mkdir -p "$CONTENTS_DIR/Resources/sakugis"
ditto --norsrc "$PROJECT_DIR/src" "$CONTENTS_DIR/Resources/sakugis"

mkdir -p "$CONTENTS_DIR/Resources/sakugis-source"
ditto --norsrc "$PROJECT_DIR/src" "$CONTENTS_DIR/Resources/sakugis-source/src"
cp -X "$PROJECT_DIR/README.md" "$CONTENTS_DIR/Resources/sakugis-source/README.md"
cp -X "$PROJECT_DIR/LICENSE" "$CONTENTS_DIR/Resources/sakugis-source/LICENSE"
cp -X \
  "$PROJECT_DIR/THIRD_PARTY_NOTICES.md" \
  "$CONTENTS_DIR/Resources/sakugis-source/THIRD_PARTY_NOTICES.md"

echo "清理 Finder 扩展属性…"
xattr -crs "$APP_PATH"

echo "签名应用…"
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --deep --sign - "$APP_PATH"
else
  codesign \
    --force \
    --deep \
    --options runtime \
    --timestamp \
    --sign "$SIGN_IDENTITY" \
    "$APP_PATH"
fi
codesign --verify --deep --strict "$APP_PATH"

if [[ "$APP_ONLY" == true ]]; then
  FINAL_APP_PATH="$OUTPUT_DIR/SakuGIS.app"
  echo "输出独立应用…"
  rm -rf "$FINAL_APP_PATH"
  mv "$APP_PATH" "$FINAL_APP_PATH"
  codesign --verify --deep --strict "$FINAL_APP_PATH"
  echo "完成：$FINAL_APP_PATH"
  exit 0
fi

echo "创建 DMG…"
ditto --norsrc "$APP_PATH" "$DMG_STAGE/SakuGIS.app"
ln -s /Applications "$DMG_STAGE/Applications"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "SakuGIS $VERSION" \
  -srcfolder "$DMG_STAGE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "完成：$DMG_PATH"
