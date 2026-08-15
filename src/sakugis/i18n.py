"""Lightweight runtime translations for the SakuGIS desktop UI."""

from __future__ import annotations

import os
from typing import Dict


ZH_CN = "zh_CN"
EN = "en"
SUPPORTED_LANGUAGES = (ZH_CN, EN)
_language = ZH_CN
_qgis_translator = None


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "app.error_title": {ZH_CN: "SakuGIS 发生错误", EN: "SakuGIS Error"},
    "menu.file": {ZH_CN: "文件", EN: "File"},
    "menu.map": {ZH_CN: "地图", EN: "Map"},
    "menu.layer": {ZH_CN: "图层", EN: "Layer"},
    "menu.agent": {ZH_CN: "Agent", EN: "Agents"},
    "menu.settings": {ZH_CN: "设置", EN: "Settings"},
    "menu.appearance": {ZH_CN: "外观", EN: "Appearance"},
    "menu.language": {ZH_CN: "语言", EN: "Language"},
    "menu.help": {ZH_CN: "帮助", EN: "Help"},
    "language.chinese": {ZH_CN: "中文", EN: "Chinese"},
    "language.english": {ZH_CN: "English", EN: "English"},
    "theme.light": {ZH_CN: "浅色模式", EN: "Light Mode"},
    "theme.dark": {ZH_CN: "深色模式", EN: "Dark Mode"},
    "action.open_data": {ZH_CN: "打开数据…", EN: "Open Data…"},
    "action.open_project": {ZH_CN: "打开工程…", EN: "Open Project…"},
    "action.save_project": {ZH_CN: "保存工程…", EN: "Save Project…"},
    "action.save_as": {ZH_CN: "工程另存为…", EN: "Save Project As…"},
    "action.export_report": {
        ZH_CN: "导出定位报告…",
        EN: "Export Geolocation Report…",
    },
    "action.export_map": {ZH_CN: "出图…", EN: "Export Map…"},
    "action.layer_style": {
        ZH_CN: "QGIS 符号系统…",
        EN: "QGIS Symbology…",
    },
    "action.attribute_table": {ZH_CN: "打开属性表", EN: "Open Attribute Table"},
    "action.show_welcome": {
        ZH_CN: "显示开始引导",
        EN: "Show Getting Started",
    },
    "action.exit": {ZH_CN: "退出", EN: "Quit"},
    "action.add_osm": {ZH_CN: "添加 OpenStreetMap", EN: "Add OpenStreetMap"},
    "action.add_google_satellite": {
        ZH_CN: "添加 Google 遥感影像",
        EN: "Add Google Satellite Imagery",
    },
    "action.pan": {ZH_CN: "平移", EN: "Pan"},
    "action.zoom_in": {ZH_CN: "放大", EN: "Zoom In"},
    "action.zoom_out": {ZH_CN: "缩小", EN: "Zoom Out"},
    "action.full_extent": {ZH_CN: "全图显示", EN: "Full Extent"},
    "action.initial_extent": {ZH_CN: "回到初始范围", EN: "Initial Extent"},
    "action.remove_layers": {ZH_CN: "移除选中图层", EN: "Remove Selected Layers"},
    "action.about": {ZH_CN: "关于 SakuGIS", EN: "About SakuGIS"},
    "action.settings": {ZH_CN: "设置…", EN: "Settings…"},
    "dock.layers": {ZH_CN: "图层", EN: "Layers"},
    "dock.agents": {ZH_CN: "Geo Agents", EN: "Geo Agents"},
    "dock.place_details": {ZH_CN: "地点详情", EN: "Place Details"},
    "action.place_details": {
        ZH_CN: "显示地点详情",
        EN: "Show Place Details",
    },
    "place.eyebrow": {
        ZH_CN: "PLACE EXPLORER",
        EN: "PLACE EXPLORER",
    },
    "place.empty_title": {ZH_CN: "尚未选择地点", EN: "No place selected"},
    "place.empty_hint": {
        ZH_CN: "单击候选列表、候选图层或地图上的候选点，查看地点介绍与网络照片。",
        EN: "Select a candidate, candidate layer, or map marker to view its description and web photos.",
    },
    "place.unnamed": {ZH_CN: "未命名地点", EN: "Unnamed place"},
    "place.overview": {ZH_CN: "概览", EN: "Overview"},
    "place.photos": {ZH_CN: "网络照片", EN: "Web Photos"},
    "place.sources": {ZH_CN: "来源", EN: "Sources"},
    "place.waiting": {ZH_CN: "等待选择候选地点", EN: "Waiting for a candidate"},
    "place.loading": {
        ZH_CN: "正在检索地点介绍与照片…",
        EN: "Searching for place information and photos…",
    },
    "place.checking": {
        ZH_CN: "正在核验地点身份与网络资料…",
        EN: "Checking the place identity and online material…",
    },
    "place.available": {
        ZH_CN: "已打开地点搜索结果浮窗",
        EN: "Opened the floating place-search results",
    },
    "place.ready": {
        ZH_CN: "已找到 {web} 条介绍、{photos} 张照片",
        EN: "Found {web} descriptions and {photos} photos",
    },
    "place.ready_archived": {
        ZH_CN: "正在复盘工程快照：{web} 条介绍、{photos} 张照片",
        EN: "Replaying project snapshot: {web} descriptions and {photos} photos",
    },
    "place.partial": {
        ZH_CN: "已显示部分结果 · {detail}",
        EN: "Showing partial results · {detail}",
    },
    "place.local_only": {
        ZH_CN: "测试模式：仅显示本地 GIS 信息",
        EN: "Test mode: showing local GIS information only",
    },
    "place.refresh": {ZH_CN: "重新检索", EN: "Refresh Search"},
    "place.composite_chip": {
        ZH_CN: "综合 {score}",
        EN: "Composite {score}",
    },
    "place.gis_chip": {
        ZH_CN: "GIS {score}",
        EN: "GIS {score}",
    },
    "place.reverse": {ZH_CN: "地点反查：", EN: "Reverse lookup:"},
    "place.rationale": {ZH_CN: "推理说明：", EN: "Reasoning:"},
    "place.coordinate": {ZH_CN: "坐标：", EN: "Coordinate:"},
    "place.radius": {ZH_CN: "范围：", EN: "Range:"},
    "place.coverage": {ZH_CN: "GIS 覆盖率：", EN: "GIS coverage:"},
    "place.web_intro": {
        ZH_CN: "网上找到的地点介绍",
        EN: "Place information found online",
    },
    "place.source_note": {
        ZH_CN: "网络内容与照片由 Brave Search 检索，仅作位置核验参考；点击标题或照片可访问原始网页，版权归原始来源所有。",
        EN: "Web text and photos are found via Brave Search for location-verification reference only. Open a title or photo to visit its source; rights remain with the original publisher.",
    },
    "place.no_web": {
        ZH_CN: "没有找到可靠的网页介绍。",
        EN: "No reliable web descriptions were found.",
    },
    "place.no_images": {
        ZH_CN: "没有找到可展示的相关照片。",
        EN: "No displayable related photos were found.",
    },
    "place.key_missing": {
        ZH_CN: "未配置 Brave Search Key；当前仅显示本地 GIS 信息。",
        EN: "Brave Search Key is not configured; showing local GIS information only.",
    },
    "place.hidden.gis_identity": {
        ZH_CN: "未找到具名 POI 或有效 GIS 地点说明，未显示搜索结果。",
        EN: "No named POI or valid GIS place description was found; search results were not shown.",
    },
    "place.hidden.no_material": {
        ZH_CN: "网上没有找到可展示的地点介绍或照片，未显示搜索结果。",
        EN: "No displayable place information or photos were found online; search results were not shown.",
    },
    "place.hidden.key_missing": {
        ZH_CN: "未配置 Brave Search Key，未显示网络搜索结果。",
        EN: "Brave Search is not configured, so online results were not shown.",
    },
    "place.hidden.local_only": {
        ZH_CN: "测试模式未执行网络检索，地点浮窗保持隐藏。",
        EN: "Online search is disabled in test mode; the place window remains hidden.",
    },
    "place.hidden.search_failed": {
        ZH_CN: "地点资料检索失败，未显示搜索结果；可以稍后重新选择候选重试。",
        EN: "Place lookup failed, so results were not shown. Select the candidate again to retry later.",
    },
    "place.open_source": {
        ZH_CN: "打开原始网页",
        EN: "Open source page",
    },
    "place.source_title": {ZH_CN: "标题", EN: "Title"},
    "place.source_site": {ZH_CN: "网站", EN: "Site"},
    "place.source_type": {ZH_CN: "类型", EN: "Type"},
    "place.type_web": {ZH_CN: "网页", EN: "Web"},
    "place.type_image": {ZH_CN: "图片来源", EN: "Image source"},
    "place.error.unauthorized": {
        ZH_CN: "Brave Search Key 无效或无权访问。",
        EN: "The Brave Search Key is invalid or unauthorized.",
    },
    "place.error.rate_limit": {
        ZH_CN: "Brave Search 调用已达限额，请稍后重试。",
        EN: "The Brave Search rate limit was reached. Try again later.",
    },
    "place.error.request": {
        ZH_CN: "检索参数未被服务接受。",
        EN: "The search service rejected the request parameters.",
    },
    "place.error.service": {
        ZH_CN: "Brave Search 服务暂时不可用。",
        EN: "Brave Search is temporarily unavailable.",
    },
    "place.error.network": {
        ZH_CN: "网络连接失败，当前保留本地 GIS 信息。",
        EN: "Network connection failed; local GIS information remains available.",
    },
    "place.error.response": {
        ZH_CN: "检索服务返回了无法读取的数据。",
        EN: "The search service returned an unreadable response.",
    },
    "place.error.image_url": {
        ZH_CN: "图片代理地址不安全。",
        EN: "The image proxy URL was not accepted.",
    },
    "place.error.image_format": {
        ZH_CN: "图片格式不受支持。",
        EN: "The image format is unsupported.",
    },
    "place.error.image_size": {
        ZH_CN: "图片过大或内容为空。",
        EN: "The image was too large or empty.",
    },
    "settings.title": {ZH_CN: "SakuGIS 设置", EN: "SakuGIS Settings"},
    "settings.api_tab": {ZH_CN: "API 服务", EN: "API Services"},
    "settings.model_tab": {ZH_CN: "模型与算法", EN: "Model & Algorithm"},
    "settings.gis_tab": {ZH_CN: "GIS", EN: "GIS"},
    "settings.interface_tab": {ZH_CN: "界面", EN: "Interface"},
    "settings.save": {ZH_CN: "保存", EN: "Save"},
    "settings.cancel": {ZH_CN: "取消", EN: "Cancel"},
    "settings.provider_group": {
        ZH_CN: "Agent 模型提供商",
        EN: "Agent Model Provider",
    },
    "settings.provider": {ZH_CN: "当前使用", EN: "Active provider"},
    "settings.qwen_group": {
        ZH_CN: "通义千问",
        EN: "Qwen",
    },
    "settings.kimi_group": {
        ZH_CN: "Kimi K3",
        EN: "Kimi K3",
    },
    "settings.brave_group": {
        ZH_CN: "Brave Search（可选）",
        EN: "Brave Search (Optional)",
    },
    "settings.configured": {ZH_CN: "已配置", EN: "Configured"},
    "settings.required_missing": {
        ZH_CN: "未配置，运行 Agent 前必须填写",
        EN: "Missing; required before running Agents",
    },
    "settings.optional_missing": {
        ZH_CN: "未配置（可选）",
        EN: "Not configured (optional)",
    },
    "settings.provider_missing": {
        ZH_CN: "未配置；选择该提供商后必须填写",
        EN: "Missing; required when this provider is selected",
    },
    "settings.keep_existing": {
        ZH_CN: "留空以保留当前密钥",
        EN: "Leave blank to keep the current key",
    },
    "settings.enter_required": {
        ZH_CN: "输入项目专用 API Key",
        EN: "Enter the project API key",
    },
    "settings.enter_optional": {
        ZH_CN: "可选：输入 Brave API Key",
        EN: "Optional: enter a Brave API key",
    },
    "settings.enter_kimi": {
        ZH_CN: "输入 Moonshot / Kimi API Key",
        EN: "Enter the Moonshot / Kimi API key",
    },
    "settings.status": {ZH_CN: "状态", EN: "Status"},
    "settings.qwen_key": {
        ZH_CN: "通义千问 API Key",
        EN: "Qwen API Key",
    },
    "settings.kimi_key": {
        ZH_CN: "Kimi API Key",
        EN: "Kimi API Key",
    },
    "settings.brave_key": {
        ZH_CN: "Brave API Key",
        EN: "Brave API Key",
    },
    "settings.qwen_note": {
        ZH_CN: "接口地址决定请求发送到哪个 OpenAI 兼容服务，API Key 是该服务的访问凭证，两者可独立设置。用于多模态证据提取、候选生成与综合推理。",
        EN: "The endpoint selects the OpenAI-compatible service, while the API key is its access credential; each can be configured independently. They are used for multimodal evidence extraction, candidate generation, and joint reasoning.",
    },
    "settings.kimi_note": {
        ZH_CN: "Kimi K3 支持图片、视频和强制推理。SakuGIS 当前接入图片与文字输入；High 适合作为日常默认，Max 可用于更困难的模糊案例。",
        EN: "Kimi K3 supports image, video, and mandatory reasoning. SakuGIS currently connects image and text input; High is the recommended everyday default, while Max is available for harder ambiguous cases.",
    },
    "settings.brave_note": {
        ZH_CN: "用于候选地点的网络介绍与照片检索。未配置时仍可完成 GIS 定位，但不会弹出网络搜索结果。",
        EN: "Used for candidate descriptions and web photos. GIS geolocation still works without it, but online search results will not open.",
    },
    "settings.request_timeout": {
        ZH_CN: "请求超时",
        EN: "Request timeout",
    },
    "settings.seconds_suffix": {ZH_CN: " 秒", EN: " s"},
    "settings.keychain_note": {
        ZH_CN: "API Key 只保存到当前用户的 macOS 钥匙串，不写入工程、App 或 Git 仓库。",
        EN: "API keys are stored only in the current user's macOS Keychain, never in projects, the app bundle, or Git.",
    },
    "settings.qwen_model_group": {
        ZH_CN: "通义千问模型",
        EN: "Qwen Model",
    },
    "settings.kimi_model_group": {
        ZH_CN: "Kimi K3 模型",
        EN: "Kimi K3 Model",
    },
    "settings.agent_parameters": {
        ZH_CN: "通用 Agent 参数",
        EN: "Shared Agent Parameters",
    },
    "settings.qwen_base_url": {
        ZH_CN: "Qwen 接口地址（Base URL）",
        EN: "Qwen endpoint (Base URL)",
    },
    "settings.kimi_base_url": {
        ZH_CN: "Kimi 接口地址（Base URL）",
        EN: "Kimi endpoint (Base URL)",
    },
    "settings.model": {ZH_CN: "模型", EN: "Model"},
    "settings.temperature": {
        ZH_CN: "推理温度",
        EN: "Temperature",
    },
    "settings.reasoning_effort": {
        ZH_CN: "推理强度",
        EN: "Reasoning effort",
    },
    "settings.prompt_limit": {
        ZH_CN: "最大提示字符数",
        EN: "Maximum prompt characters",
    },
    "settings.candidate_limit": {
        ZH_CN: "候选地点上限",
        EN: "Candidate limit",
    },
    "settings.model_note": {
        ZH_CN: "保存后从下一次分析立即生效，无需重启。千问建议保持较低温度；Kimi K3 建议默认使用 High，困难案例可切换 Max。",
        EN: "Changes apply to the next analysis immediately, without restarting. Keep Qwen temperature low; use High for Kimi K3 by default and Max for difficult cases.",
    },
    "settings.postgis_group": {
        ZH_CN: "PostGIS 空间验证（可选）",
        EN: "PostGIS Spatial Verification (Optional)",
    },
    "settings.postgis_placeholder": {
        ZH_CN: "可选：输入 PostgreSQL / PostGIS DSN",
        EN: "Optional: enter a PostgreSQL / PostGIS DSN",
    },
    "settings.postgis_dsn": {
        ZH_CN: "连接 DSN",
        EN: "Connection DSN",
    },
    "settings.postgis_note": {
        ZH_CN: "配置后优先使用 PostGIS 进行空间约束与核验，失败时回退到 OSM；连接串同样只保存于钥匙串。",
        EN: "When configured, PostGIS is preferred for spatial constraints and verification, with OSM as fallback. The DSN is also stored only in Keychain.",
    },
    "settings.interface_group": {
        ZH_CN: "语言与外观",
        EN: "Language and Appearance",
    },
    "settings.language": {ZH_CN: "界面语言", EN: "Interface language"},
    "settings.theme": {ZH_CN: "显示模式", EN: "Appearance"},
    "settings.interface_note": {
        ZH_CN: "语言与浅色/深色模式在保存后立即切换，并在下次启动时保留。",
        EN: "Language and light/dark mode change immediately when saved and persist across launches.",
    },
    "settings.qwen_required_title": {
        ZH_CN: "需要通义千问 API Key",
        EN: "Qwen API Key Required",
    },
    "settings.qwen_required_detail": {
        ZH_CN: "通义千问是 Agent 分析的必需服务，请输入 API Key 后保存。",
        EN: "Qwen is required for Agent analysis. Enter an API key and save the settings.",
    },
    "settings.provider_required_title": {
        ZH_CN: "需要模型 API Key",
        EN: "Model API Key Required",
    },
    "settings.provider_required_detail": {
        ZH_CN: "当前选择的 Agent 模型提供商尚未配置 API Key，请填写后保存。",
        EN: "The selected Agent model provider has no API key. Enter one and save the settings.",
    },
    "settings.invalid_title": {
        ZH_CN: "设置无效",
        EN: "Invalid Settings",
    },
    "settings.invalid_base_url": {
        ZH_CN: "OpenAI 兼容地址必须是 HTTPS 地址。",
        EN: "The OpenAI-compatible endpoint must use HTTPS.",
    },
    "settings.invalid_model": {
        ZH_CN: "模型名称不能为空。",
        EN: "The model name cannot be empty.",
    },
    "settings.save_failed": {
        ZH_CN: "无法保存安全配置",
        EN: "Could Not Save Secure Settings",
    },
    "settings.saved": {
        ZH_CN: "设置已保存并立即生效",
        EN: "Settings saved and applied immediately",
    },
    "toolbar.main": {ZH_CN: "主工具栏", EN: "Main Toolbar"},
    "status.ready": {ZH_CN: "就绪", EN: "Ready"},
    "status.rendering": {ZH_CN: "正在绘制…", EN: "Rendering…"},
    "status.coordinate": {ZH_CN: "坐标 {x}, {y}", EN: "Coordinate {x}, {y}"},
    "status.latlon": {ZH_CN: "经纬度 {x}, {y}", EN: "Lat/Lon {x}, {y}"},
    "status.coordinate_empty": {ZH_CN: "经纬度 —", EN: "Lat/Lon —"},
    "status.scale": {ZH_CN: "比例尺 1:{scale}", EN: "Scale 1:{scale}"},
    "status.scale_empty": {ZH_CN: "比例尺 —", EN: "Scale —"},
    "status.project_saved": {ZH_CN: "工程已保存", EN: "Project saved"},
    "status.layer_style_applied": {
        ZH_CN: "图层“{name}”配色已更新",
        EN: "Updated styling for layer “{name}”",
    },
    "status.map_exported": {
        ZH_CN: "地图已导出：{path}",
        EN: "Map exported: {path}",
    },
    "status.project_loaded": {
        ZH_CN: "SakuGIS 工程已加载，可在地图和 Agent 面板中复盘",
        EN: "SakuGIS project loaded and ready for map and Agent replay",
    },
    "status.report_saved": {
        ZH_CN: "Markdown 报告已保存：{path}",
        EN: "Markdown report saved: {path}",
    },
    "status.agent_layers": {
        ZH_CN: "已添加 {count} 个候选位置；GIS 已核验，评分尚未校准",
        EN: "Added {count} candidates; GIS verified, scores remain uncalibrated",
    },
    "status.candidate_selected": {
        ZH_CN: "{name} · 综合评分 {score}/100 · GIS {gis}/100 · 覆盖率 {coverage}%",
        EN: "{name} · Composite {score}/100 · GIS {gis}/100 · Coverage {coverage}%",
    },
    "dialog.basemap_failed": {ZH_CN: "无法添加底图", EN: "Cannot Add Basemap"},
    "dialog.basemap_failed_detail": {
        ZH_CN: "OpenStreetMap 图层初始化失败。请检查 QGIS WMS/XYZ 提供器。",
        EN: "OpenStreetMap failed to initialize. Check the QGIS WMS/XYZ provider.",
    },
    "dialog.google_failed": {
        ZH_CN: "无法添加 Google 遥感影像",
        EN: "Cannot Add Google Satellite Imagery",
    },
    "dialog.google_failed_detail": {
        ZH_CN: "自定义 Google XYZ 图层初始化失败。请检查网络和 QGIS WMS/XYZ 提供器。",
        EN: "The custom Google XYZ layer failed to initialize. Check the network and QGIS WMS/XYZ provider.",
    },
    "dialog.google_policy": {
        ZH_CN: "Google 影像仅用于交互地图显示，不会提供给 Agent 分析，也不会用于离线缓存。",
        EN: "Google imagery is used only for interactive map display. It is not provided to Agents or cached for offline use.",
    },
    "basemap.google_satellite": {
        ZH_CN: "Google 遥感影像（XYZ）",
        EN: "Google Satellite Imagery (XYZ)",
    },
    "dialog.open_gis": {ZH_CN: "打开 GIS 数据", EN: "Open GIS Data"},
    "dialog.gis_filter": {
        ZH_CN: "GIS 数据 (*.geojson *.json *.gpkg *.shp *.kml *.gpx *.tif *.tiff *.vrt *.img);;所有文件 (*)",
        EN: "GIS Data (*.geojson *.json *.gpkg *.shp *.kml *.gpx *.tif *.tiff *.vrt *.img);;All Files (*)",
    },
    "dialog.load_failed": {ZH_CN: "无法加载数据", EN: "Cannot Load Data"},
    "dialog.load_failed_detail": {
        ZH_CN: "无法加载：\n{path}",
        EN: "Cannot load:\n{path}",
    },
    "dialog.open_project": {
        ZH_CN: "打开 SakuGIS / QGIS 工程",
        EN: "Open SakuGIS / QGIS Project",
    },
    "dialog.project_filter": {
        ZH_CN: "SakuGIS 工程 (*.sgd);;QGIS 工程 (*.qgz *.qgs)",
        EN: "SakuGIS Projects (*.sgd);;QGIS Projects (*.qgz *.qgs)",
    },
    "dialog.save_project_filter": {
        ZH_CN: "SakuGIS 复盘工程 (*.sgd);;QGIS 工程 (*.qgz *.qgs)",
        EN: "SakuGIS Replay Projects (*.sgd);;QGIS Projects (*.qgz *.qgs)",
    },
    "dialog.project_open_failed": {ZH_CN: "工程打开失败", EN: "Project Open Failed"},
    "dialog.project_open_failed_detail": {
        ZH_CN: "无法读取工程：\n{path}",
        EN: "Cannot read project:\n{path}",
    },
    "dialog.save_failed": {ZH_CN: "保存失败", EN: "Save Failed"},
    "dialog.save_failed_detail": {
        ZH_CN: "无法保存工程：\n{path}",
        EN: "Cannot save project:\n{path}",
    },
    "dialog.sgd_save_failed_detail": {
        ZH_CN: "无法保存 .sgd 工程：\n{error}",
        EN: "Could not save the .sgd project:\n{error}",
    },
    "dialog.sgd_open_failed_detail": {
        ZH_CN: "无法验证或加载 .sgd 工程：\n{error}",
        EN: "Could not validate or load the .sgd project:\n{error}",
    },
    "dialog.save_project": {ZH_CN: "保存 SakuGIS 工程", EN: "Save SakuGIS Project"},
    "dialog.export_report": {
        ZH_CN: "导出 Markdown 定位报告",
        EN: "Export Markdown Geolocation Report",
    },
    "dialog.report_filter": {
        ZH_CN: "Markdown 文档 (*.md)",
        EN: "Markdown Documents (*.md)",
    },
    "dialog.report_failed": {
        ZH_CN: "报告导出失败",
        EN: "Report Export Failed",
    },
    "dialog.report_failed_detail": {
        ZH_CN: "无法写入报告：\n{error}",
        EN: "Could not write the report:\n{error}",
    },
    "dialog.no_report": {
        ZH_CN: "请先完成一次定位分析，再导出报告。",
        EN: "Complete a geolocation analysis before exporting a report.",
    },
    "dialog.untitled": {ZH_CN: "未命名.sgd", EN: "Untitled.sgd"},
    "sgd.warning_title": {
        ZH_CN: "工程已加载，但有图层未打包",
        EN: "Project Loaded with Unpackaged Layers",
    },
    "sgd.warning_layer_skipped": {
        ZH_CN: "图层“{name}”使用远程、数据库或暂不支持的数据源，未写入工程包。",
        EN: "Layer “{name}” uses a remote, database, or unsupported source and was not packaged.",
    },
    "dialog.unsaved": {ZH_CN: "工程尚未保存", EN: "Unsaved Project"},
    "dialog.unsaved_question": {
        ZH_CN: "是否先保存当前工程？",
        EN: "Save the current project first?",
    },
    "dialog.agent_busy": {ZH_CN: "Agent 正在运行", EN: "Agents Are Running"},
    "dialog.agent_busy_detail": {
        ZH_CN: "请等待当前分析结束后再退出 SakuGIS。",
        EN: "Wait for the current analysis to finish before quitting SakuGIS.",
    },
    "about.title": {ZH_CN: "关于 SakuGIS", EN: "About SakuGIS"},
    "about.body": {
        ZH_CN: "<h3>SakuGIS 0.5.0</h3><p>一款基于 QGIS 的轻量 macOS 桌面 GIS。</p><p>开发团队：<a href=\"https://urbancomp.net\">UrbanComp</a>。</p><p>许可证：GNU GPL v2 或更高版本。</p>",
        EN: "<h3>SakuGIS 0.5.0</h3><p>A lightweight macOS desktop GIS powered by QGIS.</p><p>Developed by the <a href=\"https://urbancomp.net\">UrbanComp team</a>.</p><p>License: GNU GPL v2 or later.</p>",
    },
    "update.check_button": {ZH_CN: "检查更新…", EN: "Check for Updates…"},
    "update.close_button": {ZH_CN: "关闭", EN: "Close"},
    "update.checking": {
        ZH_CN: "正在检查 GitHub 更新…",
        EN: "Checking GitHub for updates…",
    },
    "update.current_title": {ZH_CN: "已是最新版本", EN: "Up to Date"},
    "update.current_detail": {
        ZH_CN: "当前 SakuGIS {version} 已是 GitHub 上的最新版本。",
        EN: "SakuGIS {version} is the latest version available on GitHub.",
    },
    "update.available_title": {
        ZH_CN: "发现新版本",
        EN: "Update Available",
    },
    "update.available_detail": {
        ZH_CN: "当前版本：{current}\n最新版本：{latest}\n\n可以前往 GitHub 下载 Apple Silicon DMG。",
        EN: "Current version: {current}\nLatest version: {latest}\n\nThe Apple Silicon DMG is available from GitHub.",
    },
    "update.download_button": {ZH_CN: "下载更新", EN: "Download Update"},
    "update.notes_button": {ZH_CN: "查看版本说明", EN: "View Release Notes"},
    "update.later_button": {ZH_CN: "稍后", EN: "Later"},
    "update.error_title": {
        ZH_CN: "无法检查更新",
        EN: "Could Not Check for Updates",
    },
    "update.error_detail": {
        ZH_CN: "无法读取 GitHub Release 信息，请检查网络后重试。",
        EN: "GitHub Release information could not be read. Check the network and try again.",
    },
    "layer.opacity": {ZH_CN: "透明度 {value}%", EN: "Opacity {value}%"},
    "layer.eyebrow": {ZH_CN: "MAP CONTENTS", EN: "MAP CONTENTS"},
    "layer.workspace": {ZH_CN: "图层工作区", EN: "Layer Workspace"},
    "layer.summary": {
        ZH_CN: "{count} 个图层 · 勾选显示 · 拖动排序",
        EN: "{count} layers · Check to show · Drag to reorder",
    },
    "layer.hint": {
        ZH_CN: "候选位置可展开；单击候选即可定位。",
        EN: "Expand candidate groups; select a candidate to locate it.",
    },
    "layer.remove": {ZH_CN: "移除", EN: "Remove"},
    "layer.zoom": {ZH_CN: "缩放至图层", EN: "Zoom to Layer"},
    "layer.style": {ZH_CN: "符号系统", EN: "Symbology"},
    "layer.attribute_table": {ZH_CN: "属性表", EN: "Attributes"},
    "layer.rename": {ZH_CN: "重命名", EN: "Rename"},
    "layer.remove_menu": {ZH_CN: "移除图层", EN: "Remove Layer"},
    "attribute.title": {
        ZH_CN: "属性表 — {name}",
        EN: "Attribute Table — {name}",
    },
    "attribute.fid": {ZH_CN: "要素 ID", EN: "Feature ID"},
    "attribute.null": {ZH_CN: "空值", EN: "NULL"},
    "attribute.search_hint": {
        ZH_CN: "搜索全部属性…",
        EN: "Search all attributes…",
    },
    "attribute.count": {
        ZH_CN: "显示 {shown} / {total} 个要素",
        EN: "Showing {shown} / {total} features",
    },
    "attribute.count_limited": {
        ZH_CN: "大图层性能保护：显示前 {shown} / {total} 个要素",
        EN: "Large-layer safety limit: showing first {shown} / {total} features",
    },
    "attribute.zoom_selected": {ZH_CN: "缩放至所选", EN: "Zoom to Selection"},
    "attribute.close": {ZH_CN: "关闭", EN: "Close"},
    "attribute.no_selection_title": {ZH_CN: "尚未选择", EN: "No Selection"},
    "attribute.no_selection": {
        ZH_CN: "请先在属性表中选择一个或多个要素。",
        EN: "Select one or more feature rows first.",
    },
    "attribute.vector_required_title": {
        ZH_CN: "需要矢量图层",
        EN: "Vector Layer Required",
    },
    "attribute.vector_required": {
        ZH_CN: "请选择一个矢量图层后再打开属性表。",
        EN: "Select a vector layer before opening its attribute table.",
    },
    "style.title": {
        ZH_CN: "QGIS 图层符号系统 — {name}",
        EN: "QGIS Layer Symbology — {name}",
    },
    "style.mode": {ZH_CN: "配色方式", EN: "Style mode"},
    "style.single": {ZH_CN: "单一颜色", EN: "Single color"},
    "style.categorized": {ZH_CN: "按属性分类", EN: "Categorized by attribute"},
    "style.field": {ZH_CN: "分类属性", EN: "Attribute field"},
    "style.point_color": {ZH_CN: "点颜色", EN: "Point color"},
    "style.line_color": {ZH_CN: "线颜色", EN: "Line color"},
    "style.fill_color": {ZH_CN: "面填充色", EN: "Fill color"},
    "style.outline_color": {ZH_CN: "轮廓颜色", EN: "Outline color"},
    "style.point_size": {ZH_CN: "点大小（mm）", EN: "Point size (mm)"},
    "style.line_width": {ZH_CN: "线宽（mm）", EN: "Line width (mm)"},
    "style.outline_width": {ZH_CN: "轮廓线宽（mm）", EN: "Outline width (mm)"},
    "style.choose_color": {ZH_CN: "选择颜色", EN: "Choose Color"},
    "style.category_note": {
        ZH_CN: "分类配色按所选属性的唯一值生成稳定色带，单个字段最多支持 {limit} 类。",
        EN: "Categorized styling creates a stable palette from unique values, up to {limit} classes per field.",
    },
    "style.ok": {ZH_CN: "应用并关闭", EN: "Apply and Close"},
    "style.native_ok": {ZH_CN: "确定", EN: "OK"},
    "style.apply": {ZH_CN: "应用", EN: "Apply"},
    "style.cancel": {ZH_CN: "取消", EN: "Cancel"},
    "style.invalid_title": {ZH_CN: "无法分类配色", EN: "Cannot Categorize"},
    "style.no_field": {
        ZH_CN: "该图层没有可用于分类配色的属性字段。",
        EN: "This layer has no field available for categorized styling.",
    },
    "style.too_many_title": {ZH_CN: "类别过多", EN: "Too Many Categories"},
    "style.too_many": {
        ZH_CN: "所选属性超过 {limit} 个唯一值。请选择类别更少的属性。",
        EN: "The selected field has more than {limit} unique values. Choose a field with fewer classes.",
    },
    "style.vector_required_title": {
        ZH_CN: "需要点、线或面图层",
        EN: "Point, Line, or Polygon Layer Required",
    },
    "style.vector_required": {
        ZH_CN: "请选择一个矢量图层后再设置配色。",
        EN: "Select a vector layer before changing its style.",
    },
    "style.geometry_required": {
        ZH_CN: "当前图层不包含可配色的点、线或面几何。",
        EN: "The current layer has no styleable point, line, or polygon geometry.",
    },
    "style.renderer.single": {ZH_CN: "单一符号", EN: "Single Symbol"},
    "style.renderer.categorized": {ZH_CN: "分类", EN: "Categorized"},
    "style.renderer.graduated": {ZH_CN: "分级", EN: "Graduated"},
    "style.renderer.rule_based": {ZH_CN: "基于规则", EN: "Rule-based"},
    "style.renderer.point_displacement": {
        ZH_CN: "点位移",
        EN: "Point Displacement",
    },
    "style.renderer.point_cluster": {ZH_CN: "点聚类", EN: "Point Cluster"},
    "style.renderer.heatmap": {ZH_CN: "热力图", EN: "Heatmap"},
    "style.renderer.inverted": {ZH_CN: "反转多边形", EN: "Inverted Polygons"},
    "style.renderer.merged": {ZH_CN: "合并要素", EN: "Merged Features"},
    "style.renderer.embedded": {ZH_CN: "嵌入符号", EN: "Embedded Symbols"},
    "style.renderer.none": {ZH_CN: "无符号", EN: "No Symbols"},
    "map_export.title": {ZH_CN: "地图出图", EN: "Export Map"},
    "map_export.map_title": {ZH_CN: "地图标题", EN: "Map title"},
    "map_export.subtitle": {ZH_CN: "副标题", EN: "Subtitle"},
    "map_export.creator": {ZH_CN: "制图人", EN: "Created by"},
    "map_export.format": {ZH_CN: "输出格式", EN: "Output format"},
    "map_export.resolution": {ZH_CN: "分辨率", EN: "Resolution"},
    "map_export.default_title": {ZH_CN: "SakuGIS 地图", EN: "SakuGIS Map"},
    "map_export.default_subtitle": {
        ZH_CN: "当前地图范围",
        EN: "Current map extent",
    },
    "map_export.note": {
        ZH_CN: "生成 A4 横向专业版面，包含标题栏、图例、指北针、比例尺和制图元数据。Google XYZ 影像仅用于交互显示，不会写入导出文件。",
        EN: "Creates a professional A4 landscape composition with title block, legend, north arrow, scale bar, and map metadata. Google XYZ imagery is interactive-only and is excluded from exports.",
    },
    "map_export.continue": {ZH_CN: "选择保存位置", EN: "Choose Destination"},
    "map_export.cancel": {ZH_CN: "取消", EN: "Cancel"},
    "map_export.save_title": {ZH_CN: "保存地图", EN: "Save Map"},
    "map_export.pdf_filter": {ZH_CN: "PDF 地图 (*.pdf)", EN: "PDF Map (*.pdf)"},
    "map_export.png_filter": {ZH_CN: "PNG 地图 (*.png)", EN: "PNG Map (*.png)"},
    "map_export.legend": {ZH_CN: "图例", EN: "Legend"},
    "map_export.layer_count": {ZH_CN: "{count} 个图层", EN: "{count} layers"},
    "map_export.created_by": {ZH_CN: "制图", EN: "Created by"},
    "map_export.printed_at": {ZH_CN: "出图时间", EN: "Printed at"},
    "map_export.scale": {ZH_CN: "比例", EN: "Scale"},
    "map_export.version": {ZH_CN: "版本", EN: "Version"},
    "map_export.sheet": {ZH_CN: "图幅", EN: "Sheet"},
    "map_export.source": {ZH_CN: "数据", EN: "Source"},
    "map_export.layers": {ZH_CN: "图层", EN: "Layers"},
    "map_export.footer": {
        ZH_CN: "由 SakuGIS / UrbanComp 生成",
        EN: "Created with SakuGIS / UrbanComp",
    },
    "map_export.empty_title": {ZH_CN: "没有可出图内容", EN: "Nothing to Export"},
    "map_export.empty": {
        ZH_CN: "请先添加至少一个地图图层。",
        EN: "Add at least one map layer before exporting.",
    },
    "map_export.no_exportable_layers": {
        ZH_CN: "除仅限交互显示的 Google 影像外，没有其他可出图图层。",
        EN: "No exportable layers remain after excluding interactive-only Google imagery.",
    },
    "map_export.failed_title": {ZH_CN: "出图失败", EN: "Map Export Failed"},
    "map_export.failed": {
        ZH_CN: "无法生成地图：\n{error}",
        EN: "Could not export the map:\n{error}",
    },
    "map_export.export_failed_code": {
        ZH_CN: "QGIS 出图器返回错误代码 {code}",
        EN: "QGIS layout exporter returned error code {code}",
    },
    "map_export.google_excluded": {
        ZH_CN: "Google 影像已按使用策略排除",
        EN: "Google imagery was excluded by usage policy",
    },
    "agent.photo": {ZH_CN: "Case 照片", EN: "Case Photos"},
    "agent.photo_optional": {
        ZH_CN: "可选：添加同一地点的照片",
        EN: "Optional: add photos from the same location",
    },
    "agent.choose": {ZH_CN: "选择…", EN: "Choose…"},
    "agent.clear": {ZH_CN: "清除", EN: "Clear"},
    "agent.add_photos": {ZH_CN: "添加照片…", EN: "Add Photos…"},
    "agent.remove_selected": {ZH_CN: "移除所选", EN: "Remove Selected"},
    "agent.clear_all": {ZH_CN: "全部清除", EN: "Clear All"},
    "agent.photo_count": {
        ZH_CN: "已添加 {count}/{maximum} 张（默认同一地点）",
        EN: "{count}/{maximum} photos (same location by default)",
    },
    "agent.no_photo": {
        ZH_CN: "未添加照片；也可仅输入查询需求",
        EN: "No photos added; a text-only query is also supported",
    },
    "agent.preview_failed": {
        ZH_CN: "无法预览，仍可尝试分析",
        EN: "Preview unavailable; analysis can still be attempted",
    },
    "agent.query": {ZH_CN: "查询需求", EN: "Query"},
    "agent.query_hint": {
        ZH_CN: "例如：寻找照片可能的拍摄位置；或查询左侧通行、临海、附近有火山和葡萄园的城市。",
        EN: "Example: locate this photo, or find a coastal city with left-hand traffic, volcanoes, and vineyards nearby.",
    },
    "agent.import_key": {ZH_CN: "导入 API Key…", EN: "Import API Key…"},
    "agent.services": {ZH_CN: "服务状态", EN: "Service Status"},
    "agent.settings_hint": {
        ZH_CN: "API、模型、算法与 GIS 参数请在菜单栏“设置 → 设置…”中统一管理。",
        EN: "Manage APIs, models, algorithms, and GIS parameters from Settings → Settings… in the menu bar.",
    },
    "agent.brave_ready": {
        ZH_CN: "Brave：已配置，可检索地点介绍与照片",
        EN: "Brave: configured for place information and photos",
    },
    "agent.brave_optional": {
        ZH_CN: "Brave：未配置（可选，不显示网络资料）",
        EN: "Brave: not configured (optional; online material hidden)",
    },
    "agent.run": {ZH_CN: "开始全球定位", EN: "Start Global Search"},
    "agent.export": {ZH_CN: "导出报告", EN: "Export Report"},
    "agent.new_search": {ZH_CN: "修改输入", EN: "Edit Input"},
    "agent.view_result": {ZH_CN: "查看结果", EN: "View Result"},
    "agent.eyebrow": {
        ZH_CN: "GEOLOCATION STUDIO",
        EN: "GEOLOCATION STUDIO",
    },
    "agent.workspace_title": {
        ZH_CN: "全球位置推理",
        EN: "Global Location Reasoning",
    },
    "agent.workspace_subtitle": {
        ZH_CN: "添加最多 6 张同一地点照片或描述目标，Agent 联合推理，GIS 数据负责核验。",
        EN: "Add up to 6 same-location photos or describe the target. Agents reason jointly; GIS data verifies.",
    },
    "agent.step_evidence": {ZH_CN: "01 提取证据", EN: "01 Evidence"},
    "agent.step_candidates": {ZH_CN: "02 生成候选", EN: "02 Candidates"},
    "agent.step_verify": {ZH_CN: "03 GIS 核验", EN: "03 GIS Verify"},
    "agent.waiting": {ZH_CN: "等待输入", EN: "Waiting for input"},
    "agent.evidence": {ZH_CN: "证据", EN: "Evidence"},
    "agent.content": {ZH_CN: "内容", EN: "Content"},
    "agent.photos": {ZH_CN: "照片", EN: "Photos"},
    "agent.reliability": {ZH_CN: "可靠度", EN: "Reliability"},
    "agent.source": {ZH_CN: "来源", EN: "Source"},
    "agent.rank": {ZH_CN: "排名", EN: "Rank"},
    "agent.candidate": {ZH_CN: "候选地点", EN: "Candidate"},
    "agent.score": {ZH_CN: "GIS 综合评分", EN: "GIS Composite Score"},
    "agent.evidence_score": {ZH_CN: "证据复核", EN: "Evidence Review"},
    "agent.place_lookup": {ZH_CN: "地点检索", EN: "Place Lookup"},
    "agent.lookup_verified": {
        ZH_CN: "已解析",
        EN: "Resolved",
    },
    "agent.lookup_fallback": {
        ZH_CN: "模型坐标回退",
        EN: "Model-coordinate fallback",
    },
    "agent.photo_match": {ZH_CN: "照片覆盖", EN: "Photo Match"},
    "agent.gis_score": {ZH_CN: "GIS 分数", EN: "GIS Score"},
    "agent.coverage": {ZH_CN: "GIS 覆盖率", EN: "GIS Coverage"},
    "agent.range": {ZH_CN: "范围", EN: "Range"},
    "agent.gis_checks": {ZH_CN: "GIS 核验", EN: "GIS Checks"},
    "agent.check": {ZH_CN: "检查项", EN: "Check"},
    "agent.result": {ZH_CN: "结果", EN: "Result"},
    "agent.distance": {ZH_CN: "最近距离", EN: "Nearest"},
    "agent.passed": {ZH_CN: "通过", EN: "Pass"},
    "agent.failed": {ZH_CN: "不匹配", EN: "Mismatch"},
    "agent.unavailable": {ZH_CN: "不可用", EN: "Unavailable"},
    "agent.candidates_tab": {ZH_CN: "候选位置", EN: "Candidates"},
    "agent.summary_hint": {
        ZH_CN: "完成分析后显示 GIS 核验摘要和不确定性。",
        EN: "GIS verification and uncertainty will appear after analysis.",
    },
    "agent.choose_photo_title": {
        ZH_CN: "选择同一地点的照片（最多 6 张）",
        EN: "Choose Same-location Photos (up to 6)",
    },
    "agent.double_click_hint": {
        ZH_CN: "双击候选可在地图中定位。",
        EN: "Double-click the candidate to locate it on the map.",
    },
    "agent.image_filter": {
        ZH_CN: "图片 (*.jpg *.jpeg *.png *.webp *.heic *.tif *.tiff *.bmp)",
        EN: "Images (*.jpg *.jpeg *.png *.webp *.heic *.tif *.tiff *.bmp)",
    },
    "agent.import_title": {
        ZH_CN: "导入阿里云 API 配置",
        EN: "Import Alibaba Cloud API Profile",
    },
    "agent.csv_filter": {ZH_CN: "CSV 文件 (*.csv)", EN: "CSV Files (*.csv)"},
    "agent.key_import_failed": {
        ZH_CN: "API Key 导入失败",
        EN: "API Key Import Failed",
    },
    "agent.key_imported": {ZH_CN: "API Key 已导入", EN: "API Key Imported"},
    "agent.key_imported_detail": {
        ZH_CN: "Key 已保存到当前用户的 macOS 钥匙串，不会写入 SakuGIS 工程。",
        EN: "The key is stored in the current user's macOS Keychain and is not written to the SakuGIS project.",
    },
    "agent.key_ready": {
        ZH_CN: "{provider}：已配置 · 模型 {model}",
        EN: "{provider}: configured · Model {model}",
    },
    "agent.key_missing": {
        ZH_CN: "当前模型：未配置 API Key",
        EN: "Active model: API Key not configured",
    },
    "agent.gis_online": {
        ZH_CN: "GIS：OSM 在线核验",
        EN: "GIS: online OSM verification",
    },
    "agent.gis_postgis": {
        ZH_CN: "GIS：PostGIS 优先，OSM 回退",
        EN: "GIS: PostGIS preferred, OSM fallback",
    },
    "agent.configure_postgis": {ZH_CN: "PostGIS…", EN: "PostGIS…"},
    "agent.postgis_title": {ZH_CN: "配置 PostGIS", EN: "Configure PostGIS"},
    "agent.postgis_prompt": {
        ZH_CN: "输入连接 DSN，将安全保存到 macOS 钥匙串：\n例如 postgresql://user:password@host:5432/database",
        EN: "Enter a connection DSN. It will be stored in macOS Keychain:\nExample: postgresql://user:password@host:5432/database",
    },
    "agent.postgis_saved": {
        ZH_CN: "PostGIS 配置已保存，下次分析将优先使用本地数据库。",
        EN: "PostGIS configuration saved. The next analysis will prefer the database.",
    },
    "agent.postgis_failed": {
        ZH_CN: "PostGIS 配置保存失败",
        EN: "Could Not Save PostGIS Configuration",
    },
    "agent.input_needed": {ZH_CN: "需要输入", EN: "Input Required"},
    "agent.input_needed_detail": {
        ZH_CN: "请选择照片或输入查询需求。",
        EN: "Choose a photo or enter a query.",
    },
    "agent.key_required": {
        ZH_CN: "尚未配置 API Key",
        EN: "API Key Not Configured",
    },
    "agent.key_required_detail": {
        ZH_CN: "请先导入项目专用的阿里云 API 配置 CSV。",
        EN: "Import the Alibaba Cloud API profile CSV first.",
    },
    "agent.starting": {ZH_CN: "正在启动…", EN: "Starting…"},
    "agent.complete": {
        ZH_CN: "分析完成 · GIS 已核验 · 评分尚未校准",
        EN: "Complete · GIS verified · Scores uncalibrated",
    },
    "agent.analysis_failed": {ZH_CN: "分析失败", EN: "Analysis failed"},
    "agent.analysis_failed_title": {
        ZH_CN: "Agent 分析失败",
        EN: "Agent Analysis Failed",
    },
    "agent.unknown_error": {ZH_CN: "发生未知错误。", EN: "Unknown error."},
    "agent.verification_summary": {
        ZH_CN: "Agent 3 + GIS 核验摘要",
        EN: "Agent 3 + GIS Verification",
    },
    "agent.important": {ZH_CN: "重要：", EN: "Important:"},
    "agent.model_note": {
        ZH_CN: "模型：{model} · 地点检索：{retrieval} · GIS：{backend} · 当前分数不是统计概率。",
        EN: "Model: {model} · Place lookup: {retrieval} · GIS: {backend} · Scores are not statistical probabilities.",
    },
    "agent.layer_points": {
        ZH_CN: "Agent 候选位置（GIS 已核验）",
        EN: "Agent Candidates (GIS Verified)",
    },
    "agent.layer_group": {
        ZH_CN: "Agent 候选位置（{count}）",
        EN: "Agent Candidates ({count})",
    },
    "agent.layer_item": {
        ZH_CN: "#{rank} {name} · 综合{score} · GIS{gis} · 覆盖{coverage}%",
        EN: "#{rank} {name} · Total {score} · GIS {gis} · Cov {coverage}%",
    },
    "agent.layer_ranges": {
        ZH_CN: "Agent 候选范围（未校准）",
        EN: "Agent Candidate Ranges (Uncalibrated)",
    },
    "gis.reverse_country": {ZH_CN: "地点反查：国家", EN: "Reverse geocode: country"},
    "gis.reverse_locality": {
        ZH_CN: "地点反查：城市/地区",
        EN: "Reverse geocode: locality",
    },
    "gis.coastline": {ZH_CN: "附近海岸线", EN: "Nearby coastline"},
    "gis.volcano": {ZH_CN: "附近火山", EN: "Nearby volcano"},
    "gis.vineyard": {ZH_CN: "附近葡萄园", EN: "Nearby vineyard"},
    "gis.peak": {ZH_CN: "附近山峰", EN: "Nearby mountain peak"},
    "gis.river": {ZH_CN: "附近河流", EN: "Nearby river"},
    "gis.railway_station": {
        ZH_CN: "附近铁路站",
        EN: "Nearby railway station",
    },
    "gis.airport": {ZH_CN: "附近机场", EN: "Nearby airport"},
    "gis.university": {ZH_CN: "附近大学", EN: "Nearby university"},
    "gis.left_hand_traffic": {
        ZH_CN: "左侧通行国家/地区",
        EN: "Left-hand traffic jurisdiction",
    },
    "welcome.eyebrow": {
        ZH_CN: "SAKUGIS // URBAN INTELLIGENCE LAB",
        EN: "SAKUGIS // URBAN INTELLIGENCE LAB",
    },
    "welcome.title": {
        ZH_CN: "从一张照片，探索世界上的可能位置",
        EN: "Explore where in the world a photo might belong",
    },
    "welcome.subtitle": {
        ZH_CN: "适合课程、城市观察与探索性研究。模型提出假设，OSM / PostGIS 提供可检查的空间证据。",
        EN: "Built for classes, urban observation, and exploratory research. Models form hypotheses; OSM / PostGIS supplies inspectable spatial evidence.",
    },
    "welcome.steps": {
        ZH_CN: "① 添加照片或问题   →   ② 生成全球候选   →   ③ 用 GIS 数据核验",
        EN: "① Add a photo or question   →   ② Generate global candidates   →   ③ Verify with GIS data",
    },
    "welcome.start": {ZH_CN: "开始一次定位", EN: "Start a Search"},
    "welcome.satellite": {
        ZH_CN: "添加遥感影像",
        EN: "Add Satellite Imagery",
    },
    "welcome.open_data": {
        ZH_CN: "打开本地 GIS 数据",
        EN: "Open Local GIS Data",
    },
    "welcome.dismiss": {ZH_CN: "进入地图", EN: "Enter Map"},
    "hud.live_map": {ZH_CN: "LIVE MAP // 实时地图", EN: "LIVE MAP"},
    "hud.summary": {
        ZH_CN: "{crs} · {count} 个图层",
        EN: "{crs} · {count} layers",
    },
    "hud.hint": {
        ZH_CN: "拖动漫游 · 滚轮缩放",
        EN: "Drag to pan · Scroll to zoom",
    },
    "report.title": {
        ZH_CN: "SakuGIS 全球位置查询报告",
        EN: "SakuGIS Global Geolocation Report",
    },
    "report.generated": {ZH_CN: "生成时间", EN: "Generated"},
    "report.input": {ZH_CN: "查询输入", EN: "Query Input"},
    "report.query": {ZH_CN: "查询需求", EN: "Query"},
    "report.photo": {ZH_CN: "照片", EN: "Photo"},
    "report.photos": {ZH_CN: "Case 照片", EN: "Case Photos"},
    "report.photo_consistency": {ZH_CN: "照片覆盖", EN: "Photo Match"},
    "report.none": {ZH_CN: "无", EN: "None"},
    "report.evidence": {ZH_CN: "结构化证据", EN: "Structured Evidence"},
    "report.constraints": {ZH_CN: "GIS 查询约束", EN: "GIS Query Constraints"},
    "report.constraint": {ZH_CN: "约束", EN: "Constraint"},
    "report.importance": {ZH_CN: "权重", EN: "Weight"},
    "report.required": {ZH_CN: "必需", EN: "Required"},
    "report.yes": {ZH_CN: "是", EN: "Yes"},
    "report.no": {ZH_CN: "否", EN: "No"},
    "report.candidates": {ZH_CN: "候选位置排名", EN: "Candidate Ranking"},
    "report.rank": {ZH_CN: "排名", EN: "Rank"},
    "report.location": {ZH_CN: "位置", EN: "Location"},
    "report.coordinates": {ZH_CN: "坐标", EN: "Coordinates"},
    "report.composite": {ZH_CN: "综合评分", EN: "Composite"},
    "report.gis_score": {ZH_CN: "GIS 分数", EN: "GIS Score"},
    "report.coverage": {ZH_CN: "数据覆盖率", EN: "Data Coverage"},
    "report.radius": {ZH_CN: "候选半径", EN: "Radius"},
    "report.reliability": {ZH_CN: "可靠度", EN: "Reliability"},
    "report.source": {ZH_CN: "来源", EN: "Source"},
    "report.place_lookup": {ZH_CN: "真实地点检索", EN: "Real Place Lookup"},
    "report.lookup_backend": {
        ZH_CN: "地点检索后端",
        EN: "Place Lookup Backend",
    },
    "report.lookup_query": {
        ZH_CN: "检索词",
        EN: "Lookup Query",
    },
    "report.support": {ZH_CN: "支持证据", EN: "Supporting Evidence"},
    "report.contradictions": {ZH_CN: "矛盾项", EN: "Contradictions"},
    "report.details": {ZH_CN: "候选核验详情", EN: "Candidate Verification Details"},
    "report.reverse": {ZH_CN: "地点反查", EN: "Reverse Geocode"},
    "report.rationale": {ZH_CN: "解释", EN: "Rationale"},
    "report.score_breakdown": {
        ZH_CN: "评分分解",
        EN: "Score Breakdown",
    },
    "report.required_mismatch": {
        ZH_CN: "检测到 {count} 个必需空间约束不匹配，已限制最终评分上限。",
        EN: "{count} required spatial constraint(s) failed; the final score was capped.",
    },
    "report.required_unknown": {
        ZH_CN: "有 {count} 个必需约束因 GIS 数据不可用而未核验，已限制最终评分上限。",
        EN: "{count} required constraint(s) could not be verified because GIS data was unavailable; the final score was capped.",
    },
    "report.score_formula": {
        ZH_CN: "候选检索 {retrieval}（模型先验 {model_candidate}；地点库 {place_lookup}）× 20% + 收缩后证据复核 {effective_model} × 35%（模型原始 {model}；证据强度 {confidence}%）+ 覆盖率校正 GIS {effective_gis} × 45%（原始 {gis}；覆盖 {coverage}%）− 冲突扣分 {penalty}",
        EN: "candidate retrieval {retrieval} (model prior {model_candidate}; place index {place_lookup}) × 20% + shrunk evidence review {effective_model} × 35% (raw model {model}; evidence strength {confidence}%) + coverage-adjusted GIS {effective_gis} × 45% (raw {gis}; coverage {coverage}%) − contradiction penalty {penalty}",
    },
    "report.score_formula_multi": {
        ZH_CN: "候选检索 {retrieval}（模型先验 {model_candidate}；地点库 {place_lookup}）× 18% + 收缩后证据复核 {effective_model} × 30%（模型原始 {model}；证据强度 {confidence}%）+ 收缩后跨照片覆盖 {photo} × 10% + 覆盖率校正 GIS {effective_gis} × 42%（原始 {gis}；覆盖 {coverage}%）− 冲突扣分 {penalty}",
        EN: "candidate retrieval {retrieval} (model prior {model_candidate}; place index {place_lookup}) × 18% + shrunk evidence review {effective_model} × 30% (raw model {model}; evidence strength {confidence}%) + shrunk cross-photo coverage {photo} × 10% + coverage-adjusted GIS {effective_gis} × 42% (raw {gis}; coverage {coverage}%) − contradiction penalty {penalty}",
    },
    "report.check": {ZH_CN: "检查项", EN: "Check"},
    "report.result": {ZH_CN: "结果", EN: "Result"},
    "report.nearest": {ZH_CN: "最近距离", EN: "Nearest"},
    "report.summary": {ZH_CN: "结论与限制", EN: "Conclusion and Limits"},
    "report.backend": {ZH_CN: "GIS 后端", EN: "GIS Backend"},
    "report.model": {ZH_CN: "模型", EN: "Model"},
    "report.disclaimer": {
        ZH_CN: "注意：综合评分用于候选之间的探索性排序，尚未经过独立数据集校准，不应解释为统计概率。",
        EN: "Note: composite scores are exploratory rankings between candidates. They are not calibrated statistical probabilities.",
    },
    "report.footer": {
        ZH_CN: "由 SakuGIS 生成；开发团队：[UrbanComp](https://urbancomp.net)。",
        EN: "Generated by SakuGIS, developed by the [UrbanComp team](https://urbancomp.net).",
    },
    "progress.metadata": {
        ZH_CN: "正在读取本地照片元数据…",
        EN: "Reading local photo metadata…",
    },
    "progress.agent1": {
        ZH_CN: "Agent 1 正在提取视觉与文字证据…",
        EN: "Agent 1 is extracting visual and text evidence…",
    },
    "progress.agent1_photo": {
        ZH_CN: "Agent 1 正在分析照片 {current}/{total}…",
        EN: "Agent 1 is analyzing photo {current}/{total}…",
    },
    "progress.agent2": {
        ZH_CN: "Agent 2 正在生成全球候选位置…",
        EN: "Agent 2 is generating worldwide candidates…",
    },
    "progress.retrieval": {
        ZH_CN: "正在使用 OSM / PostGIS 检索真实地点…",
        EN: "Retrieving real places from OSM / PostGIS…",
    },
    "progress.retrieval_place": {
        ZH_CN: "正在解析候选地点 {current}/{total}…",
        EN: "Resolving candidate place {current}/{total}…",
    },
    "progress.gis": {
        ZH_CN: "正在使用 OSM / PostGIS 核验候选位置…",
        EN: "Verifying candidates with OSM / PostGIS…",
    },
    "progress.reverse": {
        ZH_CN: "OSM Nominatim 正在反查候选地点…",
        EN: "OSM Nominatim is reverse geocoding candidates…",
    },
    "progress.agent3": {
        ZH_CN: "Agent 3 正在结合真实 GIS 证据重排候选…",
        EN: "Agent 3 is reranking candidates using GIS evidence…",
    },
    "progress.complete": {ZH_CN: "分析完成", EN: "Analysis complete"},
    "error.no_json": {
        ZH_CN: "模型服务没有返回可解析的 JSON。",
        EN: "The model service did not return parseable JSON.",
    },
    "error.invalid_json": {
        ZH_CN: "模型服务返回的 JSON 格式不完整。",
        EN: "The model service returned incomplete JSON.",
    },
    "error.not_json_object": {
        ZH_CN: "模型服务返回的结果不是 JSON 对象。",
        EN: "The model service did not return a JSON object.",
    },
    "error.image_missing": {ZH_CN: "找不到所选照片。", EN: "The selected photo was not found."},
    "error.image_too_large": {
        ZH_CN: "照片文件过大，请选择小于 100 MB 的图片。",
        EN: "The photo is too large. Choose an image under 100 MB.",
    },
    "error.image_process": {ZH_CN: "无法预处理照片。", EN: "Cannot preprocess the photo."},
    "error.image_format": {
        ZH_CN: "照片格式无法转换，请改用 JPEG 或 PNG。",
        EN: "Cannot convert this image format. Use JPEG or PNG.",
    },
    "error.image_api_limit": {
        ZH_CN: "照片编码后超过 API 的 10 MB 限制。",
        EN: "The encoded photo exceeds the API's 10 MB limit.",
    },
    "error.api_content": {
        ZH_CN: "模型响应缺少消息内容。",
        EN: "The model response has no message content.",
    },
    "error.api_message_format": {
        ZH_CN: "模型响应的消息格式不受支持。",
        EN: "The model response format is unsupported.",
    },
    "error.api_unauthorized": {
        ZH_CN: "{provider} API Key 无效、已过期或没有访问该模型的权限。请在设置中更新 Key。",
        EN: "The {provider} API key is invalid, expired, or lacks model access. Update it in Settings.",
    },
    "error.api_rate_limit": {
        ZH_CN: "{provider} API 请求过于频繁或额度不足。Key 已被识别，但当前请求无法执行。",
        EN: "The {provider} API is rate-limited or has insufficient quota. The key was recognized, but the request cannot run.",
    },
    "error.prompt_too_long": {
        ZH_CN: "本次定位输入过长（{actual}/{maximum} 字符），已在发送前停止。请缩短查询文本，或提高当前模型对应的提示上限。",
        EN: "This geolocation input is too long ({actual}/{maximum} characters) and was stopped before upload. Shorten the query or raise the prompt limit for the selected model.",
    },
    "error.api_context_length": {
        ZH_CN: "当前模型拒绝了过长的上下文。SakuGIS 已限制提示长度并逐张发送照片；请缩短查询后重试，或检查当前模型的上下文限制。",
        EN: "The selected model rejected the request because its context was too long. SakuGIS already bounds prompts and sends photos one at a time; shorten the query or check the selected model's context limit.",
    },
    "error.api_http": {
        ZH_CN: "{provider} 接口返回 HTTP {code}。请检查 Base URL、模型名称或服务状态；这不是 Key 未配置提示。",
        EN: "The {provider} endpoint returned HTTP {code}. Check the Base URL, model name, or service status; this does not mean the key is missing.",
    },
    "error.api_network": {
        ZH_CN: "无法连接 {provider} 接口。API Key 已配置，但网络、DNS、代理或 Base URL 不可达。",
        EN: "Cannot connect to the {provider} endpoint. An API key is configured, but the network, DNS, proxy, or Base URL is unreachable.",
    },
    "error.api_timeout": {
        ZH_CN: "{provider} API 请求超时。Key 已配置，请检查网络或提高请求超时。",
        EN: "The {provider} API request timed out. A key is configured; check the network or increase the timeout.",
    },
    "error.api_response": {
        ZH_CN: "无法读取 {provider} API 响应。接口已连接，但返回内容不可用。",
        EN: "Cannot read the {provider} API response. The endpoint connected, but its response is unusable.",
    },
    "error.api_invalid_response": {
        ZH_CN: "{provider} API 响应格式无效。",
        EN: "The {provider} API response is invalid.",
    },
}


def normalize_language(value: str) -> str:
    lowered = (value or "").lower()
    return EN if lowered.startswith("en") else ZH_CN


def set_language(value: str) -> None:
    global _language
    _language = normalize_language(value)


def apply_qgis_translation(app=None) -> bool:
    """Keep native QGIS dialogs aligned with SakuGIS' runtime language."""

    global _qgis_translator
    try:
        from pathlib import Path

        from qgis.PyQt.QtCore import QCoreApplication, QTranslator
        from qgis.core import QgsApplication
    except ImportError:
        return False

    application = app or QCoreApplication.instance()
    if application is None:
        return False
    if _qgis_translator is not None:
        application.removeTranslator(_qgis_translator)
        _qgis_translator = None
    if get_language() == EN:
        return True

    translation_path = (
        Path(QgsApplication.pkgDataPath()) / "i18n" / "qgis_zh-Hans.qm"
    )
    translator = QTranslator(application)
    if not translation_path.is_file() or not translator.load(str(translation_path)):
        return False
    application.installTranslator(translator)
    _qgis_translator = translator
    return True


def get_language() -> str:
    configured = os.environ.get("SAKUGIS_LANGUAGE")
    return normalize_language(configured) if configured else _language


def tr(key: str, **values: object) -> str:
    language = get_language()
    translations = TRANSLATIONS.get(key)
    text = translations.get(language) if translations else None
    if text is None and translations:
        text = translations.get(ZH_CN)
    if text is None:
        text = key
    try:
        return text.format(**values)
    except (KeyError, ValueError):
        return text
