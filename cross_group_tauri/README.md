# QQ 跨群邀请工具（Tauri 2 + React）

Windows 桌面独立 EXE，不打开浏览器。界面为浅绿企业工具风，顶栏毛玻璃自定义标题栏。

## 技术栈

- Tauri 2
- React 19 + TypeScript
- Vite 7
- Tailwind CSS 4
- shadcn 风格组件 + lucide-react + @tanstack/react-table + zustand + react-hook-form + zod + recharts

## 目录

```
cross_group_tauri/
  src/                    # React 前端
  src-tauri/              # Tauri Rust 壳
```

## 首次运行

### 1. 安装 Rust（打包/开发必需）

```powershell
# 若未安装 Rust
winget install Rustlang.Rustup
rustup default stable
```

### 2. 安装依赖

```powershell
cd myqq_http/cross_group_tauri
npm install
```

### 3. 开发模式（独立窗口，非浏览器）

```powershell
npm run tauri dev
```

或双击：`myqq_http/启动跨群邀请助手_Tauri.bat`

### 4. 打包 EXE

```powershell
npm run tauri build
```

产物：`src-tauri/target/release/bundle/msi/` 或 `nsis/`

## 对接 Python 后端

1. 先启动后端（另开终端）：

```powershell
cd myqq_http
python cross_group_service.py
```

2. 修改 `src/lib/api.ts`：

```ts
export const USE_MOCK_API = false;  // 改为 false 连接 127.0.0.1:17888
```

## API 端点

- `GET /health`
- `GET /config` / `POST /config`
- `POST /members/load`
- `POST /invite/start` / `POST /invite/stop`
- `GET /status`

默认 mock 数据可直接预览完整 UI，无需后端。

## 界面结构

- 毛玻璃顶栏（仅标题栏）
- 5 张统计卡片
- 左：邀请配置 | 中：成员列表/邀请进度 | 右：整体/批次进度
- 底：运行日志 + 频繁限制 + 邀请失败
- 状态栏
