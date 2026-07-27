# macOS 打包与发布

SakuGIS 0.2 起仅发布 Apple Silicon（arm64）版本，不再支持 Intel Mac。
打包脚本会拒绝不包含 arm64 架构的 QGIS 运行时，并始终以 `-arch arm64`
编译原生启动器。

## 本地测试包

`scripts/package-macos.sh` 默认使用 ad-hoc 签名，适合当前 Mac 本机验证：

```bash
./scripts/package-macos.sh \
  --qgis-app /path/to/QGIS.app \
  --output-dir ./dist
```

## 正式签名

正式分发需要 Apple Developer Program 的 Developer ID Application 证书：

```bash
./scripts/package-macos.sh \
  --qgis-app /path/to/QGIS.app \
  --output-dir ./dist \
  --sign-identity "Developer ID Application: Example (TEAMID)"
```

## 公证

打包后使用已保存的 notarytool 凭据：

```bash
xcrun notarytool submit \
  ./dist/SakuGIS-0.2.1.dmg \
  --keychain-profile SakuGISNotary \
  --wait

xcrun stapler staple ./dist/SakuGIS-0.2.1.dmg
spctl --assess --type open --context context:primary-signature \
  --verbose=4 ./dist/SakuGIS-0.2.1.dmg
```

Developer ID 私钥、Apple ID 密码和 API Key 不应提交到仓库。

## 运行时升级

每次升级 QGIS LTR 时，需要执行：

1. 使用官方 macOS 原生架构 QGIS 包重新构建。
2. 运行 `scripts/check-runtime.sh`。
3. 验证本地矢量、栅格、XYZ 底图和工程读写。
4. 重新检查第三方许可证和应用体积。
5. 重新签名、公证并验证 Gatekeeper。
