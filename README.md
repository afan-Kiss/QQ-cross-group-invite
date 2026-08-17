# QQ 跨群邀请工具（Wails 正式版）

本地桌面端：基于 **Wails v2 + Go + React 19 + TypeScript + Tailwind + Zustand**，Python sidecar 提供 OneBot / NapCat 跨群邀请能力。

> 正式桌面端目录：`cross_group_wails/`  
> 不要使用 Electron / Tauri 作为正式交付。

## 技术栈

- Wails v2
- Go
- React 19 + TypeScript + Tailwind CSS
- Zustand + TanStack Table + Recharts
- Python sidecar（PyInstaller）
- NapCat / OneBot

## 目录结构

```text
myqq_http/
  cross_group_batch.py      # 批量邀请引擎
  cross_group_service.py    # 本地 HTTP sidecar (127.0.0.1:17888)
  service_logger.py
  pull_cross_group.py       # 协议发送（勿随意改动）
  tests/                    # pytest
  VERSION
  cross_group_wails/        # 正式桌面端
    app.go / main.go
    internal/service/       # sidecar 生命周期 / health
    internal/window/        # 单实例 / 聚焦
    frontend/               # React UI
    build_release.ps1
```

## 开发

```powershell
cd cross_group_wails\frontend
npm ci
npm run dev

# 另开终端启动 Python 服务
cd ..\..
python cross_group_service.py --no-browser
```

Wails 开发：

```powershell
cd cross_group_wails
wails dev
```

## 测试

```powershell
cd myqq_http
python -m pytest tests -q

cd cross_group_wails
go test ./...

cd frontend
npm test
npm run check:encoding
npm run build
```

## 构建 / Release

```powershell
cd cross_group_wails
.\build_release.ps1
```

产物：

```text
cross_group_wails\build\bin\
  QQ跨群邀请工具.exe
  cross-group-service.exe
```

## 日志 / 配置位置

- 日志：`%LOCALAPPDATA%\QQCrossGroupInvite\logs\`（`app.log` / `service.log`）
- 任务历史：`%LOCALAPPDATA%\QQCrossGroupInvite\data\tasks.json`
- 本地服务：`http://127.0.0.1:17888`（仅回环）

## Sidecar 生命周期

1. 主程序启动后立即显示窗口
2. 探测 17888；若已是 `service=cross-group-invite` 则复用
3. 否则启动 `cross-group-service.exe --session-id <uuid> --no-browser`
4. 仅当健康检查 `session_id` 匹配时，退出时才会 graceful `/shutdown`（超时再 Kill）
5. 外部已运行的同名服务不会被杀掉

## NapCat 依赖

- 加载成员 / 开始邀请需要 NapCat 在线
- NapCat 离线不阻塞窗口进入 Dashboard，仅禁用相关操作

## GitHub

https://github.com/afan-Kiss/QQ-cross-group-invite
