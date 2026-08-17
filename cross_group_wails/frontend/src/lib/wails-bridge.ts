import type { BootstrapStatus } from "@/lib/types";

type WailsApp = {
  EnsureBackend: () => Promise<BootstrapStatusRaw>;
  ProbeHealth: () => Promise<BootstrapStatusRaw>;
  ShutdownBackend: () => Promise<void>;
  OpenLogsDir: () => Promise<void>;
  GetAppInfo: () => Promise<AppInfoRaw>;
  ExportLogs?: (content: string) => Promise<string>;
  SaveFileDialog?: (defaultFilename: string) => Promise<string>;
  RunDiagnostics?: () => Promise<DiagnosticItemRaw[]>;
};

type BootstrapStatusRaw = {
  localService: string;
  message: string;
  startedByUs: boolean;
  napcatOnline: boolean;
  napcatMessage: string;
};

type AppInfoRaw = {
  appVersion: string;
  wailsVersion: string;
  goVersion: string;
  frontendVersion: string;
  pythonServiceVersion: string;
  logsDir: string;
};

type DiagnosticItemRaw = {
  label: string;
  value: string;
  ok: boolean;
};

const NOT_IN_WAILS = "当前未运行在 Wails 桌面环境中";

function mapBootstrap(raw: BootstrapStatusRaw): BootstrapStatus {
  const localService =
    raw.localService === "ready"
      ? "ready"
      : raw.localService === "port_conflict"
        ? "port_conflict"
        : raw.localService === "error"
          ? "error"
          : "booting";

  let message = raw.message;
  if (message === "service ready") message = "服务已就绪";
  else if (message === "service started, waiting for NapCat...")
    message = "服务已启动，正在等待 NapCat...";
  else if (message === "connecting to local service...") message = "正在连接本地服务...";
  else if (message === "starting local service...") message = "正在启动本地服务...";
  else if (message === "backend not running") message = "后端服务未启动";
  else if (message.startsWith("port 17888") || message.includes("occupied"))
    message = `端口 17888 已被其他程序占用：${raw.message}`;
  else if (message.startsWith("local service startup timeout"))
    message = "本地服务启动超时，请检查 17888 端口";
  else if (message.startsWith("failed to start sidecar")) message = "本地服务启动失败";

  return {
    localService,
    message,
    startedByUs: raw.startedByUs,
    napcatOnline: raw.napcatOnline,
    napcatMessage: raw.napcatMessage,
  };
}

function getApp(): WailsApp | null {
  const w = window as Window & { go?: { main?: { App?: WailsApp } } };
  return w.go?.main?.App ?? null;
}

export const wailsBridge = {
  isAvailable(): boolean {
    return getApp() !== null;
  },

  async ensureBackend(): Promise<BootstrapStatus> {
    const app = getApp();
    if (!app) throw new Error(NOT_IN_WAILS);
    return mapBootstrap(await app.EnsureBackend());
  },

  async probeHealth(): Promise<BootstrapStatus> {
    const app = getApp();
    if (!app) throw new Error(NOT_IN_WAILS);
    return mapBootstrap(await app.ProbeHealth());
  },

  async shutdownBackend(): Promise<void> {
    const app = getApp();
    if (app) await app.ShutdownBackend();
  },

  async openLogsDir(): Promise<void> {
    const app = getApp();
    if (!app) throw new Error(NOT_IN_WAILS);
    await app.OpenLogsDir();
  },

  async getAppInfo(): Promise<AppInfoRaw | null> {
    const app = getApp();
    if (!app) return null;
    return app.GetAppInfo();
  },

  async exportLogs(content: string): Promise<string> {
    const app = getApp();
    if (!app?.ExportLogs) throw new Error(NOT_IN_WAILS);
    return app.ExportLogs(content);
  },

  async runDiagnostics(): Promise<DiagnosticItemRaw[]> {
    const app = getApp();
    if (!app?.RunDiagnostics) throw new Error(NOT_IN_WAILS);
    return app.RunDiagnostics();
  },
};
