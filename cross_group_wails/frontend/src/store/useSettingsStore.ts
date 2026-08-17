import { create } from "zustand";

export interface AppSettings {
  defaultBatchCount: string;
  defaultIntervalMs: string;
  defaultFilterStaff: boolean;
  autoConnectOnStart: boolean;
  theme: "light" | "system";
  uiScale: string;
  animations: boolean;
  compactTable: boolean;
  logLevel: string;
  maxLogFileSize: string;
  logRetentionDays: string;
  autoCleanLogs: boolean;
  serviceAddress: string;
  onebotUrl: string;
  napcatWebuiToken: string;
}

const defaults: AppSettings = {
  defaultBatchCount: "20",
  defaultIntervalMs: "1500",
  defaultFilterStaff: true,
  autoConnectOnStart: true,
  theme: "light",
  uiScale: "100",
  animations: true,
  compactTable: false,
  logLevel: "INFO",
  maxLogFileSize: "5",
  logRetentionDays: "7",
  autoCleanLogs: true,
  serviceAddress: "127.0.0.1:17888",
  onebotUrl: "http://127.0.0.1:3000",
  napcatWebuiToken: "",
};

interface SettingsStore {
  settings: AppSettings;
  update: (patch: Partial<AppSettings>) => void;
  load: () => void;
}

function applyUiSettings(settings: AppSettings) {
  const root = document.documentElement;
  const scale = Number(settings.uiScale) || 100;
  root.style.fontSize = `${(16 * scale) / 100}px`;
  root.classList.toggle("reduce-motion", !settings.animations);
  root.classList.toggle("compact-table", settings.compactTable);

  const preferDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = settings.theme === "system" && preferDark;
  root.classList.toggle("theme-dark", dark);
  root.classList.toggle("theme-light", !dark);
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: { ...defaults },
  update: (patch) =>
    set((s) => {
      const settings = { ...s.settings, ...patch };
      applyUiSettings(settings);
      return { settings };
    }),
  load: () => {
    try {
      const raw = localStorage.getItem("qq-cross-group-settings");
      if (raw) {
        const parsed = { ...defaults, ...JSON.parse(raw) } as AppSettings;
        // migrate old keys
        const legacy = parsed as AppSettings & { onebotPort?: string; onebotPassword?: string };
        if (!parsed.onebotUrl && legacy.onebotPort) {
          parsed.onebotUrl = `http://127.0.0.1:${legacy.onebotPort}`;
        }
        if (!parsed.napcatWebuiToken && legacy.onebotPassword) {
          parsed.napcatWebuiToken = legacy.onebotPassword;
        }
        applyUiSettings(parsed);
        set({ settings: parsed });
        return;
      }
    } catch {
      /* ignore */
    }
    applyUiSettings(defaults);
  },
}));

export function persistSettings(settings: AppSettings) {
  localStorage.setItem("qq-cross-group-settings", JSON.stringify(settings));
  applyUiSettings(settings);
}
