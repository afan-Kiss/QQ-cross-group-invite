import { create } from "zustand";
import type { BootstrapStatus } from "@/lib/types";
import { wailsBridge } from "@/lib/wails-bridge";

interface ServiceStore extends BootstrapStatus {
  bootstrapped: boolean;
  appSession: string;
  /** Non-secret identity epoch; bumps on reconnect / session / ready-state changes. */
  serviceEpoch: number;
  setFromBootstrap: (status: BootstrapStatus) => void;
  setBootstrapping: (message: string) => void;
  setBootstrapped: (value: boolean) => void;
  bumpServiceEpoch: () => void;
  refreshHealth: () => Promise<void>;
  ensureBackend: () => Promise<void>;
}

const initial: BootstrapStatus = {
  localService: "booting",
  message: "正在启动本地服务...",
  startedByUs: false,
  napcatOnline: false,
  napcatMessage: "",
  appSession: "",
};

function nextEpoch(prev: number): number {
  return prev + 1;
}

function applyBootstrap(
  prev: { localService: string; appSession: string; serviceEpoch: number },
  status: BootstrapStatus,
): Partial<ServiceStore> {
  const appSession = status.startedByUs ? status.appSession || "" : "";
  const sessionChanged = appSession !== prev.appSession;
  const stateChanged = prev.localService !== status.localService;
  const bump = sessionChanged || stateChanged;
  return {
    ...status,
    appSession,
    bootstrapped: status.localService === "ready",
    serviceEpoch: bump ? nextEpoch(prev.serviceEpoch) : prev.serviceEpoch,
  };
}

export const useServiceStore = create<ServiceStore>((set) => ({
  ...initial,
  bootstrapped: false,
  appSession: "",
  serviceEpoch: 0,

  setFromBootstrap: (status) => set((s) => applyBootstrap(s, status)),
  setBootstrapping: (message) =>
    set((s) => ({
      localService: "booting",
      message,
      bootstrapped: false,
      appSession: "",
      startedByUs: false,
      serviceEpoch: nextEpoch(s.serviceEpoch),
    })),
  setBootstrapped: (value) => set({ bootstrapped: value }),
  bumpServiceEpoch: () => set((s) => ({ serviceEpoch: nextEpoch(s.serviceEpoch) })),

  ensureBackend: async () => {
    set((s) => ({
      localService: "booting",
      message: "正在启动本地服务...",
      bootstrapped: false,
      appSession: "",
      startedByUs: false,
      serviceEpoch: nextEpoch(s.serviceEpoch),
    }));
    try {
      const status = await wailsBridge.ensureBackend();
      set((s) => applyBootstrap(s, status));
    } catch (e) {
      set((s) => ({
        localService: "error",
        message: e instanceof Error ? e.message : "本地服务启动失败",
        bootstrapped: false,
        appSession: "",
        serviceEpoch: nextEpoch(s.serviceEpoch),
      }));
    }
  },

  refreshHealth: async () => {
    try {
      const status = await wailsBridge.probeHealth();
      set((s) => applyBootstrap(s, status));
    } catch {
      set((s) => ({
        localService: "error",
        message: "后端服务未连接",
        napcatOnline: false,
        bootstrapped: false,
        appSession: "",
        serviceEpoch: nextEpoch(s.serviceEpoch),
      }));
    }
  },
}));
