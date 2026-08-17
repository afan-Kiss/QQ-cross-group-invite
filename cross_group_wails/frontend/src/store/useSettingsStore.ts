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
  onebotPort: string;
  onebotPassword: string;
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
  onebotPort: "3000",
  onebotPassword: "",
};

interface SettingsStore {
  settings: AppSettings;
  update: (patch: Partial<AppSettings>) => void;
  load: () => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: { ...defaults },
  update: (patch) => set((s) => ({ settings: { ...s.settings, ...patch } })),
  load: () => {
    try {
      const raw = localStorage.getItem("qq-cross-group-settings");
      if (raw) {
        set({ settings: { ...defaults, ...JSON.parse(raw) } });
      }
    } catch {
      /* ignore */
    }
  },
}));

export function persistSettings(settings: AppSettings) {
  localStorage.setItem("qq-cross-group-settings", JSON.stringify(settings));
}
