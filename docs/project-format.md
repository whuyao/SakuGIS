# SakuGIS `.sgd` 工程格式 / Project Format

`.sgd` 是 SakuGIS 的可移植、可复盘单文件工程格式。它的物理结构是受约束的
ZIP 容器，但扩展名固定为 `.sgd`，媒体类型预留为
`application/vnd.urbancomp.sakugis-project`。

`.sgd` is SakuGIS's portable, replayable single-file project format. Its
physical representation is a constrained ZIP container with the `.sgd`
extension. The reserved media type is
`application/vnd.urbancomp.sakugis-project`.

## Version 1 layout

```text
manifest.json
case/case.json
case/query.txt
photos/P1.jpg
analysis/result.json
analysis/process.json
places/details.json
places/<candidate-id>/thumbnail-1.img
map/state.json
layers/<layer-id>/...
styles/<layer-id>.qml
report/report.md
```

- `manifest.json`：格式版本、应用版本、入口文件、隐私声明，以及每个载荷文件
  的字节数和 SHA-256。
- `case/`：用户查询、照片编号和 Case 模式。
- `photos/`：原始输入照片的完整副本，不保留原计算机的绝对路径。
- `analysis/result.json`：证据、候选、真实地点检索、空间约束、GIS 检查、
  综合评分、覆盖率、结论和限制说明。
- `analysis/process.json`：三个阶段的完成状态、模型与 GIS 后端、对象计数和
  保存时间，用于复盘导航。
- `places/`：已经取得的 Brave 网页介绍、图片元数据、原始来源链接，以及
  已下载并显示过的照片缩略图。复盘不需要 Brave Key；“重新检索”仍可按需
  获取最新资料。
- `map/state.json`：地图 CRS、WGS84 范围、图层顺序、可见性、透明度及受控
  底图标识。
- `layers/` 与 `styles/`：支持的本地 GIS 数据、Shapefile 伴随文件和 QML
  样式。当前支持 GeoJSON、GeoPackage、Shapefile、KML、GPX、GeoTIFF 和
  Erdas IMG。
- `report/`：保存时生成的人类可读 Markdown 快照。

The same records contain the query, original photos, structured outputs from
all three Agents, deterministic GIS verification, map state, supported local
data and QML styles, plus a human-readable report. Replaying a project is a
local deterministic operation and does not invoke Qwen, Kimi, Brave, Nominatim,
Overpass, or PostGIS.

## Loading and integrity

读取器必须先检查 `manifest.json` 和 `format_version`，再验证归档路径、条目数、
解压总量、逐文件大小和 SHA-256。版本 1 拒绝绝对路径、`..`、反斜杠、重复条目、
符号链接、未登记文件和超过 8 GiB 的解压载荷。写入采用同目录临时文件加原子
替换，避免中途失败破坏已有工程。

Readers validate the manifest and format version before extraction. Version 1
rejects absolute paths, `..`, backslashes, duplicate entries, symbolic links,
unindexed entries, more than 5,000 entries, or more than 8 GiB of extracted
payload. Writers use an adjacent temporary file and atomic replacement.

## Privacy and portability

以下内容永远不写入 `.sgd`：Qwen/Kimi API Key、Brave API Key、PostGIS DSN、钥匙串
项目、环境变量和用户设置。数据库、网络服务或其他远程图层不会保存连接字符串；
它们会被列入警告并跳过。OSM 与 Google XYZ 只保存 SakuGIS 内置底图 ID，瓦片
不会离线打包。这样既避免泄露密钥，也避免产生不受控的巨大工程文件和影像缓存。

Qwen, Kimi and Brave keys, PostGIS DSNs, Keychain items, environment variables and
user settings are never stored. Database and arbitrary remote layer connection
strings are omitted. Built-in OSM and Google XYZ layers store only a controlled
provider ID; tiles are not cached in the project.

## Compatibility

`format_version` 只在发生不向后兼容的结构变化时增加。旧版本读取器必须拒绝
未知版本；新版本读取器应提供显式迁移。`application_version` 仅用于诊断，
不决定兼容性。SakuGIS 仍可打开和另存为 QGIS `.qgz` / `.qgs`，但这些格式
不保证包含 SakuGIS 的照片和 Agent 复盘数据。

`format_version` changes only for incompatible schema revisions. Older readers
must reject unknown versions and newer readers should implement explicit
migrations. `application_version` is diagnostic and does not determine
compatibility. QGIS `.qgz` / `.qgs` remain available, but do not guarantee the
SakuGIS photo and Agent replay records.
