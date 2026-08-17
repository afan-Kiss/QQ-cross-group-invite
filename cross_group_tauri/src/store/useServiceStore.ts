import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import type { BootstrapStatus } from "@/lib/types";

interface ServiceStore extends BootstrapStatus {
  bootstrapped: boolean;
  setFromBootstrap: (status: BootstrapStatus) => void;
  setBootstrapping: (message: string) => void;
  setBootstrapped: (value: boolean) => void;
  refreshHealth: () => Promise<void>;
  ensureBackend: () => Promise<void>;
}

const initial: BootstrapStatus = {
  localService: "booting",
  message: "�����������ط���...",
  startedByUs: false,
  napcatOnline: false,
  napcatMessage: "",
};

function mapBootstrap(raw: {
  localService: string;
  message: string;
  startedByUs: boolean;
  napcatOnline: boolean;
  napcatMessage: string;
}): BootstrapStatus {
  const localService =
    raw.localService === "ready"
      ? "ready"
      : raw.localService === "port_conflict"
        ? "port_conflict"
        : raw.localService === "error"
          ? "error"
          : "booting";
  return {
    localService,
    message: raw.message,
    startedByUs: raw.startedByUs,
    napcatOnline: raw.napcatOnline,
    napcatMessage: raw.napcatMessage,
  };
}

export const useServiceStore = create<ServiceStore>((set) => ({
  ...initial,
  bootstrapped: false,

  setFromBootstrap: (status) => set({ ...status }),
  setBootstrapping: (message) =>
    set({ localService: "booting", message, bootstrapped: false }),
  setBootstrapped: (value) => set({ bootstrapped: value }),

  ensureBackend: async () => {
    set({ localService: "booting", message: "�����������ط���...", bootstrapped: false });
    try {
      const raw = await invoke<{
        localService: string;
        message: string;
        startedByUs: boolean;
        napcatOnline: boolean;
        napcatMessage: string;
      }>("ensure_backend_command");
      const status = mapBootstrap(raw);
      set({ ...status, bootstrapped: status.localService === "ready" });
    } catch (e) {
      set({
        localService: "error",
        message: e instanceof Error ? e.message : "���ط�������ʧ��",
        bootstrapped: false,
      });
    }
  },

  refreshHealth: async () => {
    try {
      const raw = await invoke<{
        localService: string;
        message: string;
        startedByUs: boolean;
        napcatOnline: boolean;
        napcatMessage: string;
      }>("probe_health_command");
      const status = mapBootstrap(raw);
      set({ ...status, bootstrapped: status.localService === "ready" });
    } catch {
      set({
        localService: "error",
        message: "��˷���δ����",
        napcatOnline: false,
        bootstrapped: false,
      });
    }
  },
}));
