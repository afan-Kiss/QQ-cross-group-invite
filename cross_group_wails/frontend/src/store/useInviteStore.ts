import { create } from "zustand";
import { api, ApiError } from "@/lib/api";
import type {
  AppStatus,
  FailedRecord,
  InviteConfig,
  Member,
  RateLimitRecord,
} from "@/lib/types";
import { toast } from "@/store/useToastStore";
import { useLogStore } from "@/store/useLogStore";
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
    throw new ApiError(service.message || "后端服务未连接", "network");
  }
}

function guardNapcatOnline() {
  const service = useServiceStore.getState();
  if (!service.napcatOnline) {
    throw new ApiError(service.napcatMessage || "NapCat 未连接", "backend");
  }
}

export interface InviteTask {
  id: string;
  sourceGroup: string;
  targetGroup: string;
  startTime: number;
  total: number;
  success: number;
  frequent: number;
  failed: number;
  status: "running" | "stopped" | "completed" | "error";
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
  tasks: InviteTask[];
  currentTaskId: string | null;
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
  getTask: (id: string) => InviteTask | undefined;
}

function makeTaskId() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

export const useInviteStore = create<InviteStore>((set, get) => ({
  config: { ...emptyConfig },
  members: [],
  membersLoaded: false,
  loadingMembers: false,
  inviting: false,
  statusText: "正在连接服务...",
  stats: emptyStats,
  logs: [],
  rateLimitList: [],
  failedList: [],
  autoScrollLogs: true,
  selectedQqs: new Set<number>(),
  activeTab: "members",
  tasks: [],
  currentTaskId: null,

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
    set({ config, statusText: "就绪" });
  },

  saveConfig: async () => {
    guardServiceReady();
    await api.saveConfig(get().config);
  },

  loadMembers: async () => {
    guardServiceReady();
    guardNapcatOnline();
    const { config } = get();
    set({ loadingMembers: true, statusText: "正在加载成员..." });
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
        statusText: `成员加载完成，共 ${res.count} 人`,
      });
      toast("success", "成员加载完成");
      await get().refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "加载失败";
      set({ statusText: msg });
      toast("error", msg);
    } finally {
      set({ loadingMembers: false });
    }
  },

  startInvite: async () => {
    guardServiceReady();
    guardNapcatOnline();
    const { config } = get();
    const taskId = makeTaskId();
    set({ inviting: true, statusText: "正在启动邀请...", activeTab: "progress", currentTaskId: taskId });
    try {
      await api.saveConfig(config);
      await api.startInvite({
        target_group_id: config.target_group_id,
        source_group_id: config.source_group_id,
        count: Number(config.batch_count) || 20,
        interval_ms: Number(config.interval_ms) || 1500,
        filter_staff: config.filter_staff,
      });
      const task: InviteTask = {
        id: taskId,
        sourceGroup: config.source_group_id,
        targetGroup: config.target_group_id,
        startTime: Date.now(),
        total: get().members.length,
        success: 0,
        frequent: 0,
        failed: 0,
        status: "running",
      };
      set((s) => ({
        statusText: "邀请运行中",
        tasks: [task, ...s.tasks],
      }));
      toast("info", "任务已启动");
      await get().refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "启动失败";
      set({ inviting: false, statusText: msg });
      toast("error", msg);
    }
  },

  stopInvite: async () => {
    guardServiceReady();
    try {
      await api.stopInvite();
      const taskId = get().currentTaskId;
      set((s) => ({
        inviting: false,
        statusText: "已停止",
        tasks: s.tasks.map((t) =>
          t.id === taskId ? { ...t, status: "stopped" as const } : t,
        ),
      }));
      toast("warning", "任务已停止");
      await get().refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "停止失败";
      set({ statusText: msg });
      toast("error", msg);
    }
  },

  refreshStatus: async () => {
    const service = useServiceStore.getState();
    if (service.localService !== "ready") return;
    try {
      const { members, currentTaskId, tasks } = get();
      const status = await api.getStatus(members);
      useServiceStore.setState({
        napcatOnline: Boolean(status.napcat_online),
        napcatMessage: status.napcat_message ?? "",
      });
      const updatedTasks = tasks.map((t) => {
        if (t.id !== currentTaskId) return t;
        const newStatus = status.running
          ? "running"
          : status.completed >= status.total && status.total > 0
            ? "completed"
            : t.status;
        return {
          ...t,
          total: status.total || t.total,
          success: status.success,
          frequent: status.rate_limited,
          failed: status.failed,
          status: newStatus as InviteTask["status"],
        };
      });
      useLogStore.getState().setFromRaw(status.logs);
      set({
        stats: status,
        members: status.members.length ? status.members : members,
        logs: status.logs,
        rateLimitList: status.rate_limit_list,
        failedList: status.failed_list,
        inviting: status.running,
        tasks: updatedTasks,
        statusText: status.running ? "邀请运行中" : status.message || "就绪",
      });
    } catch (e) {
      if (e instanceof ApiError && e.code === "port_conflict") {
        useServiceStore.setState({
          localService: "port_conflict",
          message: e.message,
          bootstrapped: false,
        });
      }
      set({ statusText: e instanceof Error ? e.message : "状态刷新失败" });
    }
  },

  clearLogs: () => {
    set({ logs: [] });
    useLogStore.getState().clear();
  },
  clearRateLimits: () => set({ rateLimitList: [] }),
  clearFailed: () => set({ failedList: [] }),

  getTask: (id) => get().tasks.find((t) => t.id === id),
}));
