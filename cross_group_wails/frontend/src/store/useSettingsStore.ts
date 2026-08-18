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
  fanfanPath: string;
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
  fanfanPath: "",
};

interface SettingsStore {
  settings: AppSettings;
  hydrated: boolean;
  update: (patch: Partial<AppSettings>) => void;
  load: () => void;
}

function applyUiSettings(settings: AppSettings) {
  if (typeof document === "undefined" || typeof window === "undefined") return;
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

function stripToken(settings: AppSettings): AppSettings {
  return { ...settings, napcatWebuiToken: "" };
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: { ...defaults },
  hydrated: false,
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
        const legacy = parsed as AppSettings & { onebotPort?: string; onebotPassword?: string };
        if (!parsed.onebotUrl && legacy.onebotPort) {
          parsed.onebotUrl = `http://127.0.0.1:${legacy.onebotPort}`;
        }
        // Never keep token in localStorage (migrate away legacy copies).
        parsed.napcatWebuiToken = "";
        applyUiSettings(parsed);
        localStorage.setItem("qq-cross-group-settings", JSON.stringify(stripToken(parsed)));
        set({ settings: parsed, hydrated: true });
        return;
      }
    } catch {
      /* ignore */
    }
    applyUiSettings(defaults);
    set({ hydrated: true });
  },
}));

export function persistSettings(settings: AppSettings) {
  const safe = stripToken(settings);
  localStorage.setItem("qq-cross-group-settings", JSON.stringify(safe));
  applyUiSettings(settings);
}
