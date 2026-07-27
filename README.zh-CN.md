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
- 多照片 Case 工作区：可联合分析最多 6 张同一地点照片，同时兼容单照片
  和纯文本查询；每张照片分别发送一次视觉请求，证据在本机合并，避免多图
  同时上传造成上下文失败，并保留照片来源、合并跨照片重复线索
- 三阶段千问流水线：证据提取、候选生成、候选核验与重排
- Agent 2/3 的真实 GIS 核验：OSM Nominatim 地点反查、Overpass 空间约束，
  以及可选的本地 PostGIS 后端
- GIS 核验分数与数据覆盖率分开显示；超时或缺失数据不会被当成匹配
- 候选都市圈去重与全球多样性选择，避免多个近邻地点挤占候选列表
- 证据强度和 GIS 覆盖率分别校正排序；国家、通行方向及用户必需空间约束
  的硬冲突会限制候选上限
- 海岸线等线状要素按最近线段距离连续评分，并支持跨日期变更线查询
- 将候选点和候选范围作为 QGIS 图层显示并支持双击定位
- 候选位置图层组可展开；候选表格与点击对比面板分别显示综合评分、证据
  复核、照片覆盖、GIS 分数和覆盖率，双击候选即可定位
- 单击候选列表、候选图层或地图标记，会在地图下方打开地点详情；面板整合
  本地 GIS 证据、Brave Search 网页介绍、网络照片及可点击的原始来源
- 中文 / English 运行时界面切换（“语言 / Language”菜单）
- 浅色 / 深色外观切换并记住用户选择
- 启动地图默认定位到湖北省武汉市
- 深色“城市观测台”界面、首次使用引导、地图 HUD 和三阶段进度提示
- 将完整查询、证据、候选与 GIS 核验导出为中英文 Markdown 报告

## 界面截图

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/wuhan-light-workspace.webp" alt="SakuGIS 浅色模式武汉工作区">
      <br><sub><b>浅色工作区</b>——从武汉启动，在同一窗口管理地图图层、最多 6 张 Case 照片、查询文本、千问状态和 OSM/PostGIS 核验。</sub>
    </td>
    <td width="50%">
      <img src="docs/images/global-candidates.webp" alt="SakuGIS 全球候选位置">
      <br><sub><b>全球候选位置</b>——生成具有地理多样性的假设，并作为可展开、可检查的 QGIS 图层展示。</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/satellite-verification.webp" alt="SakuGIS 横滨卫星影像核验">
      <br><sub><b>卫星影像核验</b>——不离开候选分析即可切换影像图层并检查空间环境。</sub>
    </td>
    <td width="50%">
      <img src="docs/images/gis-verification-detail.webp" alt="SakuGIS 开普敦 GIS 核验详情">
      <br><sub><b>GIS 核验详情</b>——检查地点反查、空间约束、综合评分、覆盖率和数据来源。</sub>
    </td>
  </tr>
  <tr>
    <td colspan="2">
      <img src="docs/images/place-details-web-photos.webp" alt="SakuGIS 地点详情与网络照片">
      <br><sub><b>地点详情与网络照片</b>——单击候选后，在地图下方联合查看 GIS 分数、地点介绍、Brave Search 相关照片和原始来源。</sub>
    </td>
  </tr>
</table>

### 真实全球案例

以下截图均来自打包后的 Apple Silicon 应用。每个案例都完整执行了三 Agent
千问流水线、OSM/GIS 核验、候选比较和基于 Brave Search 的地点照片检索。
当前分数仍是未经校准的排序信号。

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/beijing-palace-museum.webp" alt="SakuGIS 北京故宫博物院结果">
      <br><sub><b>北京故宫博物院</b>——在北京、台北和沈阳候选中正确排名第一，综合评分 83.9，GIS 覆盖率 100%。</sub>
    </td>
    <td width="50%">
      <img src="docs/images/paris-eiffel-tower.webp" alt="SakuGIS 巴黎埃菲尔铁塔结果">
      <br><sub><b>巴黎埃菲尔铁塔</b>——将巴黎地标与拉斯维加斯复制品区分开，综合评分 88.8，GIS 分数 78.0。</sub>
    </td>
  </tr>
  <tr>
    <td colspan="2">
      <img src="docs/images/sydney-opera-house.webp" alt="SakuGIS 悉尼歌剧院结果">
      <br><sub><b>悉尼歌剧院</b>——将悉尼排在第一并压低哥本哈根、奥斯陆误识候选；详情面板加载了 5 条介绍和 8 张带来源链接的照片。</sub>
    </td>
  </tr>
</table>

## 开发环境

- Apple Silicon Mac（M1 或更新芯片）；不支持 Intel Mac
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
SAKUGIS_QWEN_MAX_PROMPT_CHARS=48000 \
./scripts/run-dev.sh
```

如需使用业务空间专属地址，可通过 `SAKUGIS_QWEN_BASE_URL` 在运行时覆盖；
不要将该地址或业务空间配置提交到公开仓库。

千问请求不保留对话历史：每个阶段只发送一条系统消息和当前 Case 的输入，
不会带入上一次定位。照片会先在本机读取元数据和缩放，再由 Agent 1 每次仅
发送一张；Agent 2/3 只接收压缩后的结构化 JSON。三个阶段的提示预算分别为
12,000 / 18,000 / 32,000 字符，客户端另有 48,000 字符总保护；不同模型可
通过 `SAKUGIS_QWEN_MAX_PROMPT_CHARS` 调整最后一道保护。当前候选评分是用于
比较候选的探索排序分数，尚未经过独立地理验证集校准，因此不是统计概率。

## 地点介绍与网络照片

候选地点详情使用 Brave Search 的 Web Search 和 Image Search 接口。网络检索
在后台进行，不会阻塞地图拖动；网页与照片均保留可点击的原始来源。照片只是
搜索相关结果，不代表已经由 SakuGIS 确认拍摄位置，版权归原始发布者所有。
搜索结果和缩略图只在当前会话内短暂缓存，不写入磁盘。图片检索会扩大初始
候选池，过滤明显的零售商品、酒类、玩具、模型和购物页面，并限制同一来源
页面重复出现的数量，以提高来源多样性。该过滤属于启发式规则，不能替代
用户对原始来源的检查。

项目不会保存 Brave Key。可从本地文本文件安全导入 macOS 钥匙串：

```bash
./scripts/import-brave-key.py /path/to/brave-key.txt
```

钥匙串服务名为 `net.urbancomp.sakugis.brave`。开发时也可临时使用
`SAKUGIS_BRAVE_API_KEY` 或 `BRAVE_SEARCH_API_KEY` 环境变量。

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
