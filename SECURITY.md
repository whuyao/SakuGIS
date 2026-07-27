# Security / 安全说明

## English

### Secrets and private data

This repository must not contain:

- Qwen, DashScope, Alibaba Cloud, Google Maps, or other API keys;
- PostGIS connection strings, passwords, or private certificates;
- `.env` files or cloud profile CSV files;
- user photographs, exported queries, local GIS datasets, or cached map data;
- generated applications, DMGs, videos, or bundled QGIS runtimes.

SakuGIS resolves credentials at runtime from the current user's macOS
Keychain or from explicitly provided environment variables. The application
must never print credentials in logs or include them in exported reports.

If a secret is committed, revoke it immediately, remove it from Git history,
and rotate every credential that may have been exposed. Deleting only the
latest file is not sufficient.

### Reporting a vulnerability

Please do not open a public issue for an unpatched vulnerability or exposed
credential. Contact the UrbanComp team through
[urbancomp.net](https://urbancomp.net) with a concise description,
reproduction steps, affected versions, and the expected impact.

## 中文

### 密钥与隐私数据

本仓库禁止包含：

- 千问、DashScope、阿里云、Google Maps 或其他服务的 API Key；
- PostGIS 连接字符串、数据库密码或私有证书；
- `.env` 文件或云服务配置 CSV；
- 用户照片、查询导出、本地 GIS 数据集或地图缓存；
- 生成的应用程序、DMG、视频或打包后的 QGIS 运行时。

SakuGIS 只在运行时从当前用户的 macOS 钥匙串或显式设置的环境变量读取凭据。
应用不得将密钥写入日志或查询报告。

如果密钥被提交，应立即吊销并轮换密钥，同时从 Git 历史中彻底清除。仅删除
最新版本中的文件不足以消除泄漏。

### 报告安全问题

请不要通过公开 Issue 报告尚未修复的漏洞或泄漏的凭据。请通过
[urbancomp.net](https://urbancomp.net) 联系 UrbanComp 团队，并提供简要说明、
复现步骤、受影响版本和预期影响。
