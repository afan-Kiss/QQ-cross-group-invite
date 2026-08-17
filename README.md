# QQ 跨群邀请工具

桌面端：Wails v2 + Go + React + TypeScript + Tailwind  
后端 Sidecar：Python（PyInstaller 打包为 `cross-group-service.exe`）

## 目录

- `cross_group_wails/` — 主桌面应用（Wails）
- `cross_group_tauri/` — 旧 Tauri 版本（待清理）
- `cross_group_service.py` — 本地 API 服务（17888）
- `config.example.json` — 配置模板（复制为 `config.json` 后填写）

## 开发

```powershell
cd cross_group_wails
# 先构建 sidecar 到 bin/
copy ..\dist\cross-group-service.exe bin\
wails dev
```

## 发布

```powershell
cd cross_group_wails
.\build_release.ps1
```

输出：`cross_group_wails\build\bin\`

## 注意

- 请勿将 `config.json` 提交到 Git（含 Token/QQ 等敏感信息）
- 本工具仅用于有权限管理的群环境测试与运营
