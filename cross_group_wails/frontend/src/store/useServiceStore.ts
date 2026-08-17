import { create } from "zustand";
import type { BootstrapStatus } from "@/lib/types";
import { wailsBridge } from "@/lib/wails-bridge";

interface ServiceStore extends BootstrapStatus {
  bootstrapped: boolean;
  appSession: string;
  setFromBootstrap: (status: BootstrapStatus) => void;
  setBootstrapping: (message: string) => void;
  setBootstrapped: (value: boolean) => void;
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

export const useServiceStore = create<ServiceStore>((set) => ({
  ...initial,
  bootstrapped: false,
  appSession: "",

  setFromBootstrap: (status) =>
    set({
      ...status,
      appSession: status.startedByUs ? status.appSession || "" : "",
    }),
  setBootstrapping: (message) =>
    set({ localService: "booting", message, bootstrapped: false }),
  setBootstrapped: (value) => set({ bootstrapped: value }),

  ensureBackend: async () => {
    set({ localService: "booting", message: "正在启动本地服务...", bootstrapped: false });
    try {
      const status = await wailsBridge.ensureBackend();
      set({
        ...status,
        appSession: status.startedByUs ? status.appSession || "" : "",
        bootstrapped: status.localService === "ready",
      });
    } catch (e) {
      set({
        localService: "error",
        message: e instanceof Error ? e.message : "本地服务启动失败",
        bootstrapped: false,
        appSession: "",
      });
    }
  },

  refreshHealth: async () => {
    try {
      const status = await wailsBridge.probeHealth();
      set({
        ...status,
        appSession: status.startedByUs ? status.appSession || "" : "",
        bootstrapped: status.localService === "ready",
      });
    } catch {
      set({
        localService: "error",
        message: "后端服务未连接",
        napcatOnline: false,
        bootstrapped: false,
        appSession: "",
      });
    }
  },
}));
