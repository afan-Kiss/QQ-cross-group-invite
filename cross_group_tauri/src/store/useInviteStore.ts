import { create } from "zustand";
import { api, ApiError } from "@/lib/api";
import type {
  AppStatus,
  FailedRecord,
  InviteConfig,
  Member,
  RateLimitRecord,
} from "@/lib/types";
import { useServiceStore } from "@/store/useServiceStore";

const emptyBatch: AppStatus["batch"] = {
  batchNumber: 0,
  batchTotal: 20,
  batchDone: 0,
  currentNickname: "",
  currentQq: 0,
  intervalRemainingMs: 0,
};

const emptyStats: AppStatus = {
  running: false,
  total: 0,
  completed: 0,
  success: 0,
  rate_limited: 0,
  failed: 0,
  waiting: 0,
  inviting: 0,
  logs: [],
  rate_limit_list: [],
  failed_list: [],
  members: [],
  current_qq: 0,
  current_nickname: "",
  message: "",
  napcat_online: false,
  napcat_message: "",
  batch: emptyBatch,
};

const emptyConfig: InviteConfig = {
  target_group_id: "",
  source_group_id: "",
  batch_count: "20",
  interval_ms: "1500",
  filter_staff: true,
};

function guardServiceReady() {
  const service = useServiceStore.getState();
  if (service.localService !== "ready") {
    throw new ApiError(service.message || "��˷���δ����", "network");
  }
}

function guardNapcatOnline() {
  const service = useServiceStore.getState();
  if (!service.napcatOnline) {
    throw new ApiError(service.napcatMessage || "NapCat δ����", "backend");
  }
}

interface InviteStore {
  config: InviteConfig;
  members: Member[];
  membersLoaded: boolean;
  loadingMembers: boolean;
  inviting: boolean;
  statusText: string;
  stats: AppStatus;
  logs: string[];
  rateLimitList: RateLimitRecord[];
  failedList: FailedRecord[];
  autoScrollLogs: boolean;
  selectedQqs: Set<number>;
  activeTab: "members" | "progress";
  setConfig: (patch: Partial<InviteConfig>) => void;
  setActiveTab: (tab: "members" | "progress") => void;
  setAutoScrollLogs: (value: boolean) => void;
  toggleSelect: (qq: number) => void;
  toggleSelectAll: (qqs: number[]) => void;
  loadConfig: () => Promise<void>;
  saveConfig: () => Promise<void>;
  loadMembers: () => Promise<void>;
  startInvite: () => Promise<void>;
  stopInvite: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  clearLogs: () => void;
  clearRateLimits: () => void;
  clearFailed: () => void;
}

export const useInviteStore = create<InviteStore>((set, get) => ({
  config: { ...emptyConfig },
  members: [],
  membersLoaded: false,
  loadingMembers: false,
  inviting: false,
  statusText: "�������ӷ���...",
  stats: emptyStats,
  logs: [],
  rateLimitList: [],
  failedList: [],
  autoScrollLogs: true,
  selectedQqs: new Set<number>(),
  activeTab: "members",

  setConfig: (patch) => set((s) => ({ config: { ...s.config, ...patch } })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setAutoScrollLogs: (value) => set({ autoScrollLogs: value }),

  toggleSelect: (qq) =>
    set((s) => {
      const next = new Set(s.selectedQqs);
      if (next.has(qq)) next.delete(qq);
      else next.add(qq);
      return { selectedQqs: next };
    }),

  toggleSelectAll: (qqs) =>
    set((s) => {
      const allSelected = qqs.every((qq) => s.selectedQqs.has(qq));
      return { selectedQqs: allSelected ? new Set<number>() : new Set(qqs) };
    }),

  loadConfig: async () => {
    guardServiceReady();
    const config = await api.getConfig();
    set({ config, statusText: "����" });
  },

  saveConfig: async () => {
    guardServiceReady();
    await api.saveConfig(get().config);
  },

  loadMembers: async () => {
    guardServiceReady();
    guardNapcatOnline();
    const { config } = get();
    set({ loadingMembers: true, statusText: "���ڼ��س�Ա..." });
    try {
      const res = await api.loadMembers({
        source_group_id: config.source_group_id,
        filter_staff: config.filter_staff,
      });
      const members = api.mapLoadedMembers(res.members, config.filter_staff);
      set({
        members,
        membersLoaded: true,
        selectedQqs: new Set(members.map((m) => m.qq)),
        statusText: `��Ա������ɣ��� ${res.count} ��`,
      });
      await get().refreshStatus();
    } catch (e) {
      set({ statusText: e instanceof Error ? e.message : "����ʧ��" });
    } finally {
      set({ loadingMembers: false });
    }
  },

  startInvite: async () => {
    guardServiceReady();
    guardNapcatOnline();
    const { config } = get();
    set({ inviting: true, statusText: "������������...", activeTab: "progress" });
    try {
      await api.saveConfig(config);
      await api.startInvite({
        target_group_id: config.target_group_id,
        source_group_id: config.source_group_id,
        count: Number(config.batch_count) || 20,
        interval_ms: Number(config.interval_ms) || 1500,
        filter_staff: config.filter_staff,
      });
      set({ statusText: "���������" });
      await get().refreshStatus();
    } catch (e) {
      set({
        inviting: false,
        statusText: e instanceof Error ? e.message : "����ʧ��",
      });
    }
  },

  stopInvite: async () => {
    guardServiceReady();
    try {
      await api.stopInvite();
      set({ inviting: false, statusText: "��ֹͣ" });
      await get().refreshStatus();
    } catch (e) {
      set({ statusText: e instanceof Error ? e.message : "ֹͣʧ��" });
    }
  },

  refreshStatus: async () => {
    const service = useServiceStore.getState();
    if (service.localService !== "ready") return;
    try {
      const { members } = get();
      const status = await api.getStatus(members);
      useServiceStore.setState({
        napcatOnline: Boolean(status.napcat_online),
        napcatMessage: status.napcat_message ?? "",
      });
      set({
        stats: status,
        members: status.members.length ? status.members : members,
        logs: status.logs,
        rateLimitList: status.rate_limit_list,
        failedList: status.failed_list,
        inviting: status.running,
        statusText: status.running ? "���������" : status.message || "����",
      });
    } catch (e) {
      if (e instanceof ApiError && e.code === "port_conflict") {
        useServiceStore.setState({
          localService: "port_conflict",
          message: e.message,
          bootstrapped: false,
        });
      }
      set({ statusText: e instanceof Error ? e.message : "״̬ˢ��ʧ��" });
    }
  },

  clearLogs: () => set({ logs: [] }),
  clearRateLimits: () => set({ rateLimitList: [] }),
  clearFailed: () => set({ failedList: [] }),
}));
