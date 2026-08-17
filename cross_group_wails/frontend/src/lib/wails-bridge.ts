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
  appSession?: string;
  backendInstance?: string;
  backendPid?: number;
  backendVersion?: string;
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

const NOT_IN_WAILS = "\u5f53\u524d\u672a\u8fd0\u884c\u5728 Wails \u684c\u9762\u73af\u5883\u4e2d";

function mapBootstrap(raw: BootstrapStatusRaw): BootstrapStatus {
  const localService =
    raw.localService === "ready"
      ? "ready"
      : raw.localService === "port_conflict"
        ? "port_conflict"
        : raw.localService === "error"
          ? "error"
          : raw.localService === "manual"
            ? "manual"
            : "booting";

  let message = raw.message;
  if (message === "service ready") message = "\u670d\u52a1\u5df2\u5c31\u7eea";
  else if (message === "service started, waiting for NapCat...")
    message = "\u670d\u52a1\u5df2\u542f\u52a8\uff0c\u6b63\u5728\u7b49\u5f85\u996d\u996d\u5b9a\u5236...";
  else if (message === "connecting to local service...") message = "\u6b63\u5728\u8fde\u63a5\u672c\u5730\u670d\u52a1...";
  else if (message === "starting local service...") message = "\u6b63\u5728\u542f\u52a8\u672c\u5730\u670d\u52a1...";
  else if (message === "backend not running") message = "\u540e\u7aef\u670d\u52a1\u672a\u542f\u52a8";
  else if (message.startsWith("port 17888") || message.includes("occupied"))
    message = `\u7aef\u53e3 17888 \u5df2\u88ab\u5176\u4ed6\u7a0b\u5e8f\u5360\u7528\uff1a${raw.message}`;
  else if (message.startsWith("local service startup timeout"))
    message = "\u672c\u5730\u670d\u52a1\u542f\u52a8\u8d85\u65f6\uff0c\u8bf7\u68c0\u67e5 17888 \u7aef\u53e3";
  else if (message.startsWith("failed to start sidecar")) message = "\u672c\u5730\u670d\u52a1\u542f\u52a8\u5931\u8d25";

  return {
    localService,
    message,
    startedByUs: raw.startedByUs,
    napcatOnline: raw.napcatOnline,
    napcatMessage: raw.napcatMessage,
    appSession: raw.startedByUs ? raw.appSession || "" : "",
    backendInstance: raw.backendInstance || "",
    backendPid: Number(raw.backendPid || 0),
    backendVersion: raw.backendVersion || "",
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

  async getAppInfo(): Promise<AppInfoRaw> {
    const app = getApp();
    if (!app) throw new Error(NOT_IN_WAILS);
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
