# SakuGIS

中文说明 · [English](README.md)

SakuGIS 是一款面向 macOS 的轻量桌面 GIS 应用。当前版本以 QGIS LTR
作为 GIS 内核，提供在线底图、本地 GIS 数据加载、图层管理、地图漫游和
QGIS 工程保存能力。由 [UrbanComp 团队](https://urbancomp.net)开发。

## 当前功能

- OpenStreetMap 在线底图
- 可叠加的 Google 遥感影像自定义 XYZ 底图
- 鼠标拖动、滚轮缩放、放大、缩小和全图显示
- 图层显示、隐藏、拖动排序、重命名和透明度调整
- 打开 GeoJSON、GeoPackage、Shapefile、KML 和 GeoTIFF 等常见数据
- 打开和保存 `.qgz` / `.qgs` 工程
- 状态栏显示经纬度、比例尺和渲染状态
- OSM 版权署名与合规的应用 User-Agent
- Geo Agents 面板：照片/自然语言输入、结构化证据和全球候选位置
- 三阶段千问流水线：证据提取、候选生成、候选核验与重排
- Agent 2/3 的真实 GIS 核验：OSM Nominatim 地点反查、Overpass 空间约束，
  以及可选的本地 PostGIS 后端
- GIS 核验分数与数据覆盖率分开显示；超时或缺失数据不会被当成匹配
- 候选都市圈去重与全球多样性选择，避免多个近邻地点挤占候选列表
- 证据强度和 GIS 覆盖率分别校正排序；国家、通行方向及用户必需空间约束
  的硬冲突会限制候选上限
- 海岸线等线状要素按最近线段距离连续评分，并支持跨日期变更线查询
- 将候选点和候选范围作为 QGIS 图层显示并支持双击定位
- 候选位置图层组可展开；每个候选节点显示综合评分、GIS 分数和覆盖率，
  单击节点即可定位
- 中文 / English 运行时界面切换（“语言 / Language”菜单）
- 深色“城市观测台”界面、首次使用引导、地图 HUD 和三阶段进度提示
- 将完整查询、证据、候选与 GIS 核验导出为中英文 Markdown 报告

## 开发环境

- macOS 13 或更高版本
- QGIS 3.40 或更高版本（推荐 3.44 LTR）
- QGIS 自带的 Python、PyQt 和 PyQGIS

无需单独安装 Python 包。开发运行：

```bash
./scripts/run-dev.sh
```

如果 QGIS 不在默认位置：

```bash
QGIS_APP=/Applications/QGIS.app ./scripts/run-dev.sh
```

## 千问 API

SakuGIS 默认使用阿里云 Model Studio 北京地域的公开 OpenAI 兼容地址，默认
模型为 `qwen3.7-plus`。项目不包含 API Key、业务空间 ID 或项目专属地址，
也不会把 Key 写入配置文件。首次使用时可在 Geo Agents 面板点击“导入
API Key…”，或运行：

```bash
./scripts/import-api-key.py /path/to/阿里云-apiKey.csv
```

Key 会保存到当前用户的 macOS 钥匙串，服务名为
`net.urbancomp.sakugis.qwen`。也可以通过环境变量临时覆盖：

```bash
SAKUGIS_QWEN_API_KEY=... \
SAKUGIS_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
SAKUGIS_QWEN_MODEL=qwen3.7-plus \
./scripts/run-dev.sh
```

如需使用业务空间专属地址，可通过 `SAKUGIS_QWEN_BASE_URL` 在运行时覆盖；
不要将该地址或业务空间配置提交到公开仓库。

照片会先在本机读取元数据并缩放，再发送给千问。当前候选评分是用于比较候选
的探索排序分数，尚未经过独立地理验证集校准，因此不是统计概率。

## GIS 核验后端

无需额外配置时，Agent 2/3 会使用真实的 OSM 服务：

- Nominatim 对每个候选坐标进行国家、地区和地点反查；
- Overpass 在有界候选范围内验证海岸线、火山、葡萄园、河流、车站等
  OSM 标签约束；
- 请求只在用户主动分析时发出，带应用 User-Agent，并进行速率控制和磁盘缓存；
- 公共服务超时或限流时，相应检查显示为“不可用”，不会推断为匹配。

生产或批量场景可连接已导入 OSM 数据的 PostgreSQL + PostGIS。Geo Agents
面板中的“PostGIS…”按钮会把 DSN 保存到 macOS 钥匙串；连接成功后使用
`ST_Covers` 做行政区反查，使用 `ST_DWithin` / `ST_Distance` 做米制空间核验，
失败时回退到 OSM 在线服务。数据库结构和导入要求见
[`docs/postgis.md`](docs/postgis.md)。

## 界面与报告

首次打开会显示四个清晰入口：开始定位、添加遥感影像、打开本地 GIS 数据和
进入地图。Geo Agents 使用“证据 → 候选 → GIS 核验”三阶段状态，分析完成后
自动收起照片区，把空间留给结果。

完成分析后，可在 Geo Agents 面板点击“导出报告”，或使用“文件 → 导出定位
报告…”。报告采用当前界面语言，包含结构化证据、GIS 查询约束、候选综合评分、
数据覆盖率、地点反查、逐项核验、来源和不确定性说明。格式说明见
[`docs/reporting.md`](docs/reporting.md)。

## Google 遥感影像

“图层”菜单和主工具栏可添加用户指定的自定义 XYZ 源：

```text
http://mt2.google.cn/vt/lyrs=s&hl=zh-hk&g0=hk&x={x}&y={y}&z={z}
```

该源被隔离为可替换的底图定义，并显示 Google Maps 署名。它仅用于交互地图
可视化，不会送入 Geo Agents、OSM/PostGIS 核验或离线分析。此地址不是当前
Google Maps Tile API 官方文档中的受支持端点，其可用性和使用授权需由部署者
确认；正式发布可替换为带 API Key 和会话令牌的官方 Map Tiles API。
当 `mt2.google.cn` 在当前网络无法解析时，应用使用相同瓦片路径的
`https://mt2.google.com` 作为兼容回退。

## 开发阶段运行

开发阶段直接运行可执行脚本即可，不需要重复制作 DMG：

```bash
./scripts/run-dev.sh
```

三 Agent 全球图像定位的设计见
[`docs/geolocation-agents.md`](docs/geolocation-agents.md)。

## 最终发布

功能稳定后，打包脚本会复制官方 QGIS `.app` 中的运行时，生成用户无需
预装 QGIS 的独立应用和 DMG：

仓库不保存生成的 `.app`、DMG、QGIS 运行时或 `.icns` 二进制文件。打包脚本
会在需要时根据 `resources/icon.svg` 自动生成应用图标。

开发阶段只生成可双击运行的 `.app`：

```bash
./scripts/package-macos.sh \
  --qgis-app /Applications/QGIS.app \
  --output-dir ./build \
  --app-only
```

最终生成 DMG：

```bash
./scripts/package-macos.sh \
  --qgis-app /Applications/QGIS.app \
  --output-dir ./dist
```

未提供签名身份时会使用 ad-hoc 签名，适合本机测试。正式发布需要 Apple
Developer ID Application 证书：

```bash
./scripts/package-macos.sh \
  --qgis-app /Applications/QGIS.app \
  --output-dir ./dist \
  --sign-identity "Developer ID Application: Example (TEAMID)"
```

公证需要另行配置 Apple 的 `notarytool` 凭据，详见
[`docs/packaging.md`](docs/packaging.md)。

## 项目结构

```text
src/sakugis/        应用源码
resources/          macOS Info.plist 与应用资源
scripts/            开发、打包和验证脚本
tests/              不依赖 GUI 的单元测试
docs/               架构与发布说明
```

## 许可证

SakuGIS 使用 GNU GPL v2 或更高版本发布。QGIS 及打包运行时中各组件的
许可证文件会随独立应用一同分发。公开发布时还需遵循
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 中的源代码提供要求。

## 安全说明

本仓库不包含 API Key、PostGIS DSN、`.env` 文件、阿里云配置 CSV、用户照片
或查询导出数据。密钥仅从 macOS 钥匙串或环境变量读取。提交代码前请参阅
[`SECURITY.md`](SECURITY.md)。
