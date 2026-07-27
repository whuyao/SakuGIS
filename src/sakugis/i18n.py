"""Lightweight runtime translations for the SakuGIS desktop UI."""

from __future__ import annotations

import os
from typing import Dict


ZH_CN = "zh_CN"
EN = "en"
SUPPORTED_LANGUAGES = (ZH_CN, EN)
_language = ZH_CN


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "app.error_title": {ZH_CN: "SakuGIS 发生错误", EN: "SakuGIS Error"},
    "menu.file": {ZH_CN: "文件", EN: "File"},
    "menu.map": {ZH_CN: "地图", EN: "Map"},
    "menu.layer": {ZH_CN: "图层", EN: "Layer"},
    "menu.agent": {ZH_CN: "Agent", EN: "Agents"},
    "menu.language": {ZH_CN: "语言", EN: "Language"},
    "menu.help": {ZH_CN: "帮助", EN: "Help"},
    "language.chinese": {ZH_CN: "中文", EN: "Chinese"},
    "language.english": {ZH_CN: "English", EN: "English"},
    "action.open_data": {ZH_CN: "打开数据…", EN: "Open Data…"},
    "action.open_project": {ZH_CN: "打开工程…", EN: "Open Project…"},
    "action.save_project": {ZH_CN: "保存工程…", EN: "Save Project…"},
    "action.save_as": {ZH_CN: "工程另存为…", EN: "Save Project As…"},
    "action.export_report": {
        ZH_CN: "导出定位报告…",
        EN: "Export Geolocation Report…",
    },
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
    "dock.layers": {ZH_CN: "图层", EN: "Layers"},
    "dock.agents": {ZH_CN: "Geo Agents", EN: "Geo Agents"},
    "toolbar.main": {ZH_CN: "主工具栏", EN: "Main Toolbar"},
    "status.ready": {ZH_CN: "就绪", EN: "Ready"},
    "status.rendering": {ZH_CN: "正在绘制…", EN: "Rendering…"},
    "status.coordinate": {ZH_CN: "坐标 {x}, {y}", EN: "Coordinate {x}, {y}"},
    "status.latlon": {ZH_CN: "经纬度 {x}, {y}", EN: "Lat/Lon {x}, {y}"},
    "status.coordinate_empty": {ZH_CN: "经纬度 —", EN: "Lat/Lon —"},
    "status.scale": {ZH_CN: "比例尺 1:{scale}", EN: "Scale 1:{scale}"},
    "status.scale_empty": {ZH_CN: "比例尺 —", EN: "Scale —"},
    "status.project_saved": {ZH_CN: "工程已保存", EN: "Project saved"},
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
        ZH_CN: "QGIS 工程 (*.qgz *.qgs)",
        EN: "QGIS Projects (*.qgz *.qgs)",
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
    "dialog.untitled": {ZH_CN: "未命名.qgz", EN: "Untitled.qgz"},
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
        ZH_CN: "<h3>SakuGIS 0.2.0</h3><p>一款基于 QGIS 的轻量 macOS 桌面 GIS。</p><p>开发团队：<a href=\"https://urbancomp.net\">UrbanComp</a>。</p><p>许可证：GNU GPL v2 或更高版本。</p>",
        EN: "<h3>SakuGIS 0.2.0</h3><p>A lightweight macOS desktop GIS powered by QGIS.</p><p>Developed by the <a href=\"https://urbancomp.net\">UrbanComp team</a>.</p><p>License: GNU GPL v2 or later.</p>",
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
    "layer.rename": {ZH_CN: "重命名", EN: "Rename"},
    "layer.remove_menu": {ZH_CN: "移除图层", EN: "Remove Layer"},
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
    "agent.run": {ZH_CN: "开始全球定位", EN: "Start Global Search"},
    "agent.export": {ZH_CN: "导出报告", EN: "Export Report"},
    "agent.new_search": {ZH_CN: "修改输入", EN: "Edit Input"},
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
        ZH_CN: "千问：已配置 · 模型 {model}",
        EN: "Qwen: configured · Model {model}",
    },
    "agent.key_missing": {
        ZH_CN: "千问：未配置 API Key",
        EN: "Qwen: API Key not configured",
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
        ZH_CN: "模型：{model} · GIS：{backend} · 当前分数不是统计概率。",
        EN: "Model: {model} · GIS: {backend} · Scores are not statistical probabilities.",
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
        ZH_CN: "检索 {retrieval} × 20% + 收缩后证据复核 {effective_model} × 35%（模型原始 {model}；证据强度 {confidence}%）+ 覆盖率校正 GIS {effective_gis} × 45%（原始 {gis}；覆盖 {coverage}%）− 冲突扣分 {penalty}",
        EN: "retrieval {retrieval} × 20% + shrunk evidence review {effective_model} × 35% (raw model {model}; evidence strength {confidence}%) + coverage-adjusted GIS {effective_gis} × 45% (raw {gis}; coverage {coverage}%) − contradiction penalty {penalty}",
    },
    "report.score_formula_multi": {
        ZH_CN: "检索 {retrieval} × 18% + 收缩后证据复核 {effective_model} × 30%（模型原始 {model}；证据强度 {confidence}%）+ 收缩后跨照片覆盖 {photo} × 10% + 覆盖率校正 GIS {effective_gis} × 42%（原始 {gis}；覆盖 {coverage}%）− 冲突扣分 {penalty}",
        EN: "retrieval {retrieval} × 18% + shrunk evidence review {effective_model} × 30% (raw model {model}; evidence strength {confidence}%) + shrunk cross-photo coverage {photo} × 10% + coverage-adjusted GIS {effective_gis} × 42% (raw {gis}; coverage {coverage}%) − contradiction penalty {penalty}",
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
    "progress.agent2": {
        ZH_CN: "Agent 2 正在生成全球候选位置…",
        EN: "Agent 2 is generating worldwide candidates…",
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
        ZH_CN: "千问没有返回可解析的 JSON。",
        EN: "Qwen did not return parseable JSON.",
    },
    "error.invalid_json": {
        ZH_CN: "千问返回的 JSON 格式不完整。",
        EN: "Qwen returned incomplete JSON.",
    },
    "error.not_json_object": {
        ZH_CN: "千问返回的结果不是 JSON 对象。",
        EN: "Qwen did not return a JSON object.",
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
        ZH_CN: "千问响应缺少消息内容。",
        EN: "The Qwen response has no message content.",
    },
    "error.api_message_format": {
        ZH_CN: "千问响应的消息格式不受支持。",
        EN: "The Qwen message format is unsupported.",
    },
    "error.api_unauthorized": {
        ZH_CN: "千问 API Key 无效或已过期。",
        EN: "The Qwen API Key is invalid or expired.",
    },
    "error.api_rate_limit": {
        ZH_CN: "千问 API 请求过于频繁或额度不足。",
        EN: "The Qwen API is rate-limited or has insufficient quota.",
    },
    "error.api_http": {
        ZH_CN: "千问 API 返回 HTTP {code}。",
        EN: "The Qwen API returned HTTP {code}.",
    },
    "error.api_network": {
        ZH_CN: "无法连接千问 API，请检查网络。",
        EN: "Cannot connect to the Qwen API. Check the network.",
    },
    "error.api_timeout": {ZH_CN: "千问 API 请求超时。", EN: "The Qwen API request timed out."},
    "error.api_response": {
        ZH_CN: "无法读取千问 API 响应。",
        EN: "Cannot read the Qwen API response.",
    },
    "error.api_invalid_response": {
        ZH_CN: "千问 API 响应格式无效。",
        EN: "The Qwen API response is invalid.",
    },
}


def normalize_language(value: str) -> str:
    lowered = (value or "").lower()
    return EN if lowered.startswith("en") else ZH_CN


def set_language(value: str) -> None:
    global _language
    _language = normalize_language(value)


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
