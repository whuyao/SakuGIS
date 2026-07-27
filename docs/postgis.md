# SakuGIS PostGIS 地点检索与核验后端

SakuGIS 默认使用 OSM Nominatim + Overpass。需要稳定吞吐、离线运行或更大
候选集时，可把 OSM extract 导入自有 PostgreSQL + PostGIS，并通过 Geo
Agents 面板的“PostGIS…”按钮配置连接。

## 规范化表

初始化数据库：

```bash
psql "$DATABASE_URL" -f scripts/init-postgis.sql
```

默认表为 `public.sakugis_osm_features`，必须包含：

- `osm_type`、`osm_id`：OSM 对象标识；
- `name`：可空的主要名称；
- `tags jsonb`：完整或任务所需的 OSM 标签；
- `geom geometry(Geometry, 4326)`：WGS 84 几何。

可使用 osm2pgsql、 imposm 或自有 ETL 读取 Geofabrik/OSM extract，再映射到
该表。行政区地点反查需要保留 `boundary=administrative`、`admin_level`、
`ISO3166-1:alpha2` 与多语言名称；特征核验需要保留任务中使用的
`natural`、`landuse`、`waterway`、`railway`、`aeroway`、`amenity` 等标签。
Agent 2 的地点检索还会使用 `name`、`name:en` 和 `name:zh`。初始化脚本为
这些字段建立 `pg_trgm` 索引。SakuGIS 不随应用分发全球 OSM 数据。

## 连接配置

推荐在界面中输入 PostgreSQL DSN，例如：

```text
postgresql://sakugis_reader:password@127.0.0.1:5432/sakugis
```

DSN 会保存到当前用户的 macOS 钥匙串
`net.urbancomp.sakugis.postgis`，不会写入工程。也可仅为当前进程设置：

```bash
SAKUGIS_POSTGIS_DSN='postgresql://...' ./scripts/run-dev.sh
```

非默认表可通过 `SAKUGIS_POSTGIS_TABLE=schema.table` 指定。表名只允许普通
PostgreSQL 标识符，所有候选坐标、半径和标签值都使用参数化 SQL。

## 查询语义

- 地点名称检索：参数化 `ILIKE` 查询多语言名称并返回
  `ST_PointOnSurface(geom)` 坐标；
- 行政区反查：`ST_Covers(admin_geom, candidate_point)`；
- 特征半径约束：`ST_DWithin(geom::geography, point::geography, radius_m)`；
- 最近距离：`ST_Distance(...::geography) / 1000`。

因此半径和距离采用米/千米，而不是经纬度角度。数据库不可达、缺少 PostGIS
或表结构不符时，本次分析回退到 OSM 在线服务，界面会显示实际使用的后端。

生产部署应给应用只读账户，仅授予目标表的 `SELECT` 权限，并为 `geom`
保留 GiST 索引、为 `tags` 保留 GIN 索引，并保留初始化脚本创建的多语言
名称 trigram 索引。导入或更新 OSM 数据后执行
`ANALYZE public.sakugis_osm_features`。
