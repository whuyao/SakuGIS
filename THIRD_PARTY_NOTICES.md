# Third-party notices

SakuGIS 的独立 macOS 安装包包含 QGIS LTR 运行时及其依赖。

## QGIS

- Project: https://qgis.org/
- Source: https://github.com/qgis/QGIS
- License: GNU General Public License v2 or later

打包时使用的 QGIS 版本可从应用内“关于”窗口或运行时
`Contents/Resources/doc` 中确认。正式公开发布某一版本的 SakuGIS 时，
应在相同下载位置提供该安装包所对应的完整 QGIS 源码归档或符合 GPL
要求的书面源代码提供方式。

## OpenStreetMap

SakuGIS 可以显示 OpenStreetMap 标准在线地图：

- Map data © OpenStreetMap contributors
- Copyright: https://www.openstreetmap.org/copyright
- Tile usage policy: https://operations.osmfoundation.org/policies/tiles/

OpenStreetMap 数据许可与 SakuGIS 程序许可证相互独立。

## Google 遥感影像自定义 XYZ

SakuGIS 可按部署者指定的 XYZ 地址显示 Google 遥感影像。影像内容不随
SakuGIS 分发，仅用于交互地图可视化，并在界面显示 Google Maps 署名。
该自定义地址不是当前 Google Maps Tile API 官方文档中的受支持端点；
部署者需自行确认地址可用性、适用服务条款和授权。

## Bundled libraries

QGIS 运行时中包含 Qt、GDAL、PROJ、GEOS 及其他开源组件。它们各自的
许可证文件保留在应用包的 `Contents/Resources` 和相关框架目录中。
