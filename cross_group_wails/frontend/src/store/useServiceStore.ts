import { create } from "zustand";
import type { BootstrapStatus } from "@/lib/types";
import { wailsBridge } from "@/lib/wails-bridge";

interface ServiceStore extends BootstrapStatus {
  bootstrapped: boolean;
  appSession: string;
  backendInstance: string;
  /** Non-secret identity epoch; bumps on reconnect / session / ready-state / instance changes. */
  serviceEpoch: number;
  /** Invalidates in-flight ensureBackend / refreshHealth writers. */
  lifecycleGeneration: number;
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
  backendInstance: "",
  backendPid: 0,
  backendVersion: "",
};

function nextEpoch(prev: number): number {
  return prev + 1;
}

function ownedSession(status: BootstrapStatus): string {
  return status.startedByUs ? status.appSession || "" : "";
}

function instanceOf(status: BootstrapStatus): string {
  if (status.backendInstance) return status.backendInstance;
  if (status.backendPid && status.backendPid > 0) {
    return `cross-group-invite:${status.backendVersion || "unknown"}:${status.backendPid}`;
  }
  return "";
}

export function applyBootstrap(
  prev: {
    localService: string;
    appSession: string;
    backendInstance: string;
    serviceEpoch: number;
  },
  status: BootstrapStatus,
): Partial<ServiceStore> {
  const appSession = ownedSession(status);
  const backendInstance = instanceOf(status);
  const sessionChanged = appSession !== prev.appSession;
  const stateChanged = prev.localService !== status.localService;
  const instanceChanged = Boolean(backendInstance) && backendInstance !== prev.backendInstance;
  const bump = sessionChanged || stateChanged || instanceChanged;
  return {
    ...status,
    appSession,
    backendInstance,
    bootstrapped: status.localService === "ready",
    serviceEpoch: bump ? nextEpoch(prev.serviceEpoch) : prev.serviceEpoch,
  };
}

export const useServiceStore = create<ServiceStore>((set, get) => ({
  ...initial,
  bootstrapped: false,
  appSession: "",
  backendInstance: "",
  serviceEpoch: 0,
  lifecycleGeneration: 0,

  setFromBootstrap: (status) => set((s) => applyBootstrap(s, status)),
  setBootstrapping: (message) =>
    set((s) => ({
      localService: "booting",
      message,
      bootstrapped: false,
      appSession: "",
      startedByUs: false,
      backendInstance: "",
      serviceEpoch: nextEpoch(s.serviceEpoch),
      lifecycleGeneration: nextEpoch(s.lifecycleGeneration),
    })),
  setBootstrapped: (value) => set({ bootstrapped: value }),
  bumpServiceEpoch: () => set((s) => ({ serviceEpoch: nextEpoch(s.serviceEpoch) })),

  ensureBackend: async () => {
    const gen = get().lifecycleGeneration + 1;
    set((s) => ({
      localService: "booting",
      message: "正在启动本地服务...",
      bootstrapped: false,
      appSession: "",
      startedByUs: false,
      backendInstance: "",
      serviceEpoch: nextEpoch(s.serviceEpoch),
      lifecycleGeneration: gen,
    }));
    try {
      const status = await wailsBridge.ensureBackend();
      if (get().lifecycleGeneration !== gen) return;
      set((s) => applyBootstrap(s, status));
    } catch (e) {
      if (get().lifecycleGeneration !== gen) return;
      set((s) => ({
        localService: "error",
        message: e instanceof Error ? e.message : "本地服务启动失败",
        bootstrapped: false,
        appSession: "",
        backendInstance: "",
        serviceEpoch: nextEpoch(s.serviceEpoch),
      }));
    }
  },

  refreshHealth: async () => {
    const gen = get().lifecycleGeneration;
    try {
      const status = await wailsBridge.probeHealth();
      if (get().lifecycleGeneration !== gen) return;
      set((s) => applyBootstrap(s, status));
    } catch {
      if (get().lifecycleGeneration !== gen) return;
      set((s) => ({
        localService: "error",
        message: "后端服务未连接",
        napcatOnline: false,
        bootstrapped: false,
        appSession: "",
        backendInstance: "",
        serviceEpoch: nextEpoch(s.serviceEpoch),
      }));
    }
  },
}));
