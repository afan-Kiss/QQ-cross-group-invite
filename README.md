# QQ 跨群邀请工具（Wails 正式版）

本地桌面端：基于 **Wails v2 + Go + React 19 + TypeScript + Tailwind + Zustand**，Python sidecar 提供 OneBot / NapCat 跨群邀请能力。

> 正式桌面端为 Wails v2（目录：`cross_group_wails/`）。

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
  build_sidecar.ps1         # 框架无关 sidecar 构建
  build_release.ps1         # 根入口，转调 cross_group_wails/build_release.ps1
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

根目录入口（转调同一套 Wails 脚本）：

```powershell
.\build_release.ps1
```

或直接：

```powershell
cd cross_group_wails
.\build_release.ps1
```

仅构建 sidecar：

```powershell
.\build_sidecar.ps1
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

## Sidecar 生命周期与会话安全

1. 主程序启动后立即显示窗口
2. Go Manager 生成 app session，仅在进程内持有；owned bootstrap 再传给本机 frontend
3. 探测 17888：
   - `service=cross-group-invite` 且 `session_required=false` → 可复用（external unlocked）
   - `session_required=true` 且带 `X-App-Session` 后 `session_match=true` → owned ready，frontend 持有 appSession
   - `session_required=true` 但 `session_match=false` → `port_conflict`（受保护外部实例，不进入假 ready）
4. `/health` **永不回显** raw session；只返回 `session_required` / `session_match` 等非秘密字段
5. frontend 写操作通过 `X-App-Session` 认证
6. 退出时仅对确认 owned 的 sidecar 调用 `/shutdown`；外部同名服务不会被杀掉

## NapCat 依赖

- 加载成员 / 开始邀请需要 NapCat 在线
- “测试连接”会验证 OneBot 登录身份与 WebUI Token（不写入正式配置）
- NapCat 离线不阻塞窗口进入 Dashboard，仅禁用相关操作

## GitHub

https://github.com/afan-Kiss/QQ-cross-group-invite
