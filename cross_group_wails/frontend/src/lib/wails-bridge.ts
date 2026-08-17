import type { BootstrapStatus } from "@/lib/types";

type WailsApp = {
  EnsureBackend: () => Promise<BootstrapStatusRaw>;
  ProbeHealth: () => Promise<BootstrapStatusRaw>;
  ShutdownBackend: () => Promise<void>;
  OpenLogsDir: () => Promise<void>;
  GetAppInfo: () => Promise<AppInfoRaw>;
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
  else if (message === "service started, waiting for NapCat...") message = "服务已启动，正在等待 NapCat...";
  else if (message === "connecting to local service...") message = "正在连接本地服务...";
  else if (message === "starting local service...") message = "正在启动本地服务...";
  else if (message === "backend not running") message = "后端服务未启动";
  else if (message.startsWith("port 17888")) message = "17888 端口被其他程序占用";
  else if (message.startsWith("local service startup timeout")) message = "本地服务启动超时，请检查 17888 端口";
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
    if (!app) {
      throw new Error("Wails ???????????");
    }
    return mapBootstrap(await app.EnsureBackend());
  },

  async probeHealth(): Promise<BootstrapStatus> {
    const app = getApp();
    if (!app) {
      throw new Error("Wails ???????????");
    }
    return mapBootstrap(await app.ProbeHealth());
  },

  async shutdownBackend(): Promise<void> {
    const app = getApp();
    if (app) await app.ShutdownBackend();
  },

  async openLogsDir(): Promise<void> {
    const app = getApp();
    if (app) await app.OpenLogsDir();
  },

  async getAppInfo(): Promise<AppInfoRaw | null> {
    const app = getApp();
    if (!app) return null;
    return app.GetAppInfo();
  },
};
