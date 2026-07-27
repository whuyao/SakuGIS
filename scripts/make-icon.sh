#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$PROJECT_DIR/resources/icon.svg"
ICONSET="$PROJECT_DIR/build/SakuGIS.iconset"
PREVIEW_DIR="$PROJECT_DIR/build/icon-preview"
OUTPUT="$PROJECT_DIR/resources/SakuGIS.icns"

rm -rf "$ICONSET"
rm -rf "$PREVIEW_DIR"
mkdir -p "$ICONSET" "$PREVIEW_DIR"

qlmanage -t -s 1024 -o "$PREVIEW_DIR" "$SOURCE" >/dev/null
MASTER="$PREVIEW_DIR/icon.svg.png"

if [[ ! -f "$MASTER" ]]; then
  echo "无法从 SVG 生成图标预览" >&2
  exit 1
fi

render() {
  local size="$1"
  local filename="$2"
  sips \
    --resampleHeightWidth "$size" "$size" \
    --setProperty format png \
    "$MASTER" \
    --out "$ICONSET/$filename" >/dev/null
}

render 16 icon_16x16.png
render 32 icon_16x16@2x.png
render 32 icon_32x32.png
render 64 icon_32x32@2x.png
render 128 icon_128x128.png
render 256 icon_128x128@2x.png
render 256 icon_256x256.png
render 512 icon_256x256@2x.png
render 512 icon_512x512.png
render 1024 icon_512x512@2x.png

iconutil --convert icns "$ICONSET" --output "$OUTPUT"
echo "已生成：$OUTPUT"
