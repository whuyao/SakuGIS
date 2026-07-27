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
│   ├── Agent 2：候选生成 + 空间约束规划
│   └── Agent 3：GIS 证据约束下的候选核验
└── Provider adapters
    ├── OSM XYZ（地图显示）
    ├── Nominatim / Overpass（在线地点反查与空间核验）
    ├── PostGIS（可选的本地 OSM 核验）
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

Geo Agents 通过后台 `QThread` 调用千问 OpenAI 兼容 API，避免阻塞地图界面。
三个阶段交换严格 JSON，并使用 dataclass 进行经纬度、分数和证据校验。API
Key 存放在 macOS 钥匙串，既不进入 QGIS 工程，也不进入应用源码。

Agent 2 生成候选后，规则规划器把结构化证据和查询文本转换成受限的 OSM
标签、半径与国家规则。GIS 验证器优先查询已配置的 PostGIS；否则使用
Nominatim 反查地点，并用 Overpass 查询候选周边真实 OSM 要素。Agent 3
只能在这些查询结果上解释和重排，`matched=null` 明确表示数据不可用。
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

第一阶段直接使用 QGIS `.qgz`，避免复制成熟的图层、样式、坐标系和路径
序列化能力。需要产品专属元数据时，可写入 QGIS 工程的自定义属性。

三 Agent 定位流水线、数据来源和置信度定义详见
[`geolocation-agents.md`](geolocation-agents.md)。

界面文字通过轻量运行时词典集中管理，用户可在“语言 / Language”菜单中
切换中文和 English，选择会写入 QGIS 用户设置。

### 界面系统

`ui_theme.py` 提供可持久化的浅色与深色外观、青色主操作、洋红候选和绿色
已验证状态。用户可在“外观 / Appearance”菜单中即时切换，选择写入 QGIS
用户设置。`ui_components.py` 提供首次使用引导和不阻挡地图交互的 HUD。
图层侧栏维持两级层次；Agent 工作区用三阶段状态表达后台流程，并在产生
结果后压缩输入区。新建空白工作区默认以湖北省武汉市为地图中心。

### 报告

`reporting.py` 将 `GeoAnalysisResult` 确定性渲染为 UTF-8 Markdown，不再
调用模型。报告沿用当前界面语言，保留原始证据、GIS 数据来源和不可用状态，
并明确标记综合评分尚未校准。
