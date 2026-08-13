# SakuGIS 架构

## 目标

第一阶段提供可靠的桌面地图浏览和图层管理能力，同时保留向完整 GIS
工作流与三 Agent 全球图像定位扩展的路径。SakuGIS 由 UrbanComp 团队开发。

## 组件

```text
Native Mach-O launcher
        ↓
SakuGIS UI (PyQt)
├── MainWindow
├── MapCanvas / MapTools
├── LayerPanel
├── Geo Agents Panel
│   ├── Agent 1：证据提取
│   ├── Agent 2：候选假设 + 真实地点检索 + 空间约束规划
│   └── Agent 3：GIS 证据约束下的候选核验
└── Provider adapters
    ├── Qwen / Kimi K3（可切换的多模态 Agent 模型，Qwen 默认）
    ├── OSM XYZ（地图显示）
    ├── Nominatim Search / Reverse + Overpass（地点解析与空间核验）
    ├── PostGIS（可选的本地 OSM 地名检索与空间核验）
    └── Google 遥感影像自定义 XYZ（仅地图显示，可替换）
        ↓
PyQGIS API
        ↓
QGIS Core / GUI
├── GDAL / OGR
├── PROJ
├── GEOS
└── Qt
```

Geo Agents 通过后台 `QThread` 调用可切换的 Qwen 或 Kimi K3 OpenAI 兼容 API，
避免阻塞地图界面。Qwen 保持默认；用户只需完整配置当前所选提供商。三个阶段
交换严格 JSON，并使用 dataclass 进行经纬度、分数和证据校验。两个提供商的
API Key 使用独立的 macOS 钥匙串条目，既不进入 QGIS 工程，也不进入应用源码。

API 调用是无状态的，不保存或重放此前定位的消息。多照片 Case 在 Agent 1
拆成逐张视觉请求，每个请求仅含一张经缩放的照片；证据随后在本机去重、按
照片公平取样，再以压缩 JSON 交给 Agent 2/3。三个阶段分别限制为 12k、18k、
32k 字符，客户端在发送前还有默认 48k 总提示保护；GIS 明细优先保留必需项
与失败项，完整 GIS 分数和覆盖率始终由本地确定性逻辑计算。
若服务偶发返回截断或格式不完整的 JSON，客户端只进行一次无历史重试，
不回传破损内容。Qwen 重试时降低温度；Kimi K3 是强制推理模型，使用独立
`reasoning_effort` 与更大的输出预留，避免内部推理挤占最终 JSON。首次返回
有效 JSON 时不会产生额外调用。

Agent 2 先提出带正式检索词的宽候选。`HybridCandidateRetriever` 随后优先
在已配置的 PostGIS OSM 地名索引中搜索；未配置或无结果时使用带速率限制和
磁盘缓存的 Nominatim Search。检索层根据名称、地区、国家、坐标接近度和
地名重要度选择真实记录，并用其坐标替换模型坐标。无法访问检索服务时保留
模型候选，但在结果中明确标记为回退，不能伪装成已解析地点。

规则规划器再把结构化证据和查询文本转换成受限的 OSM 标签、半径与国家规则。
GIS 验证器优先查询已配置的 PostGIS；否则使用 Nominatim Reverse 反查地点，
并用 Overpass 查询候选周边真实 OSM 要素。Agent 3 只能在这些查询结果上解释
和重排，`matched=null` 明确表示数据不可用。
最终排序对 GIS 分数按实际数据覆盖率衰减，避免公共服务超时产生虚假高分。
候选宽召回后先按 20 km 都市圈去重，再用位置新颖度保留全球不同假设。
Agent 3 只输出非 GIS 的证据复核分；确定性融合器分别对模型分按证据强度、
GIS 分按数据覆盖率向 0.5 收缩，避免缺失数据和重复计票扭曲排序。国家反查
冲突、通行方向冲突或用户必需空间约束失败等硬矛盾会限制最终分数上限。
有查询约束时，GIS 分的 75% 分配给空间约束，地点反查仅用于候选身份核验。
每个候选保留评分分解供界面提示与报告审计。

## 设计决策

### 使用 PyQGIS 自定义应用

官方 macOS QGIS 安装包提供完整运行时和 Python 绑定，但通常不提供构建
自定义 C++ 应用所需的开发头文件。使用 PyQGIS 能直接复用官方签名运行时，
减少自建 QGIS 工具链和依赖树的维护成本。

应用包的 `CFBundleExecutable` 是一个只依赖 macOS 系统库的原生 Mach-O
启动器。它设置内嵌运行时路径后启动 QGIS 自带的 Python，避免使用 shell
脚本作为正式应用入口，并确保代码签名和 Gatekeeper 可以正确识别应用。

应用业务逻辑保持模块化。未来若测量、空间分析或大数据加载出现性能瓶颈，
可以用 C++/SIP 扩展替换局部模块，而无需重写界面和项目模型。

### 在线地图提供器隔离

OSM 是标准 XYZ 图层。当前按部署者指定地址提供隔离的 Google 遥感影像
自定义 XYZ 可视化层，不把影像用于 Agent、数据提取或离线分析。该地址不是
当前官方 Map Tiles API 端点；正式切换官方 API 时，需要增加处理会话令牌、
动态版权、缓存头和密钥管理的 `GoogleMapTilesProvider`。

### 工程格式

SakuGIS 默认使用自己的 `.sgd` 单文件复盘工程。它是带清单、版本号和逐文件
SHA-256 的受控 ZIP 容器，保存 Case 输入、原始照片、三 Agent 结构化输出、
GIS 核验、候选排序、地图视图、可移植本地数据和 QML 样式。加载时不重新调用
模型，而是反序列化结果并确定性重建候选点、范围图层和 Agent 面板。已经
取得的 Brave 介绍、来源链接和界面照片缩略图也会作为只读快照复盘。

凭据、PostGIS DSN 和远程连接字符串不进入工程包。在线底图只保存受控的
提供器标识，不缓存瓦片；远程、数据库或不支持的图层会被跳过并给出提示。
现有 `.qgz` / `.qgs` 继续作为兼容导入和另存格式。完整规范见
[`project-format.md`](project-format.md)。

三 Agent 定位流水线、数据来源和置信度定义详见
[`geolocation-agents.md`](geolocation-agents.md)。

界面文字通过轻量运行时词典集中管理。菜单栏“设置 / Settings”是统一配置
入口，用户可在“界面”页切换中文和 English，选择会写入 QGIS 用户设置。

### 界面系统

`ui_theme.py` 提供可持久化的浅色与深色外观、青色主操作、洋红候选和绿色
已验证状态。用户可在“设置 → 设置… → 界面”中即时切换，选择写入 QGIS
用户设置。`settings_dialog.py` 统一管理 API、模型与算法、GIS 和界面参数；
密钥与 DSN 写入 macOS 钥匙串，非密钥参数写入 QGIS 用户设置，保存后立即
更新运行时配置。`ui_components.py` 提供首次使用引导和不阻挡地图交互的 HUD。
图层侧栏维持两级层次；Agent 工作区用三阶段状态表达后台流程，并在产生
结果后压缩输入区。新建空白工作区默认以湖北省武汉市为地图中心。

### 报告

`reporting.py` 将 `GeoAnalysisResult` 确定性渲染为 UTF-8 Markdown，不再
调用模型。报告沿用当前界面语言，保留原始证据、GIS 数据来源和不可用状态，
并明确标记综合评分尚未校准。
