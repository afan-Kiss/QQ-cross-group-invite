import { create } from "zustand";
import { api, ApiError } from "@/lib/api";
import type {
  AppStatus,
  FailedRecord,
  InviteConfig,
  Member,
  MemberStatus,
  PersistedTask,
  RateLimitRecord,
  RateSeriesPoint,
} from "@/lib/types";
import { toast } from "@/store/useToastStore";
import { useLogStore } from "@/store/useLogStore";
import { useServiceStore } from "@/store/useServiceStore";
import { useSettingsStore } from "@/store/useSettingsStore";

const emptyBatch: AppStatus["batch"] = {
  batchNumber: 0,
  batchTotal: 20,
  batchDone: 0,
  totalBatches: 0,
  currentNickname: "",
  currentQq: 0,
  intervalRemainingMs: 0,
  intervalMs: 0,
  nextInviteAt: 0,
};

const emptyStats: AppStatus = {
  running: false,
  status: "idle",
  task_id: "",
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
  results: [],
  rate_series: [],
  members: [],
  current_qq: 0,
  current_nickname: "",
  message: "",
  error_message: "",
  started_at: 0,
  finished_at: 0,
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
    throw new ApiError(service.napcatMessage || "NapCat 未连接", "NAPCAT_OFFLINE");
  }
}

export interface InviteTask {
  id: string;
  sourceGroup: string;
  targetGroup: string;
  startTime: number;
  endTime?: number;
  total: number;
  success: number;
  frequent: number;
  failed: number;
  status: "running" | "stopped" | "completed" | "error" | "preparing" | "stopping";
  errorMessage?: string;
  timeline?: Array<{ at: number; event: string; detail?: string }>;
}

function mapPersistedTask(t: PersistedTask): InviteTask {
  const statusRaw = String(t.status || "");
  let status: InviteTask["status"] = "completed";
  if (statusRaw === "running" || statusRaw === "preparing" || statusRaw === "stopping") {
    status = statusRaw;
  } else if (statusRaw === "stopped") status = "stopped";
  else if (statusRaw === "error") status = "error";
  else if (statusRaw === "completed") status = "completed";

  return {
    id: String(t.id),
    sourceGroup: String(t.source_group_id ?? ""),
    targetGroup: String(t.target_group_id ?? ""),
    startTime: Number(t.started_at || t.created_at || 0) * (Number(t.started_at || 0) > 1e12 ? 1 : 1000),
    endTime: t.finished_at
      ? Number(t.finished_at) * (Number(t.finished_at) > 1e12 ? 1 : 1000)
      : undefined,
    total: Number(t.total || 0),
    success: Number(t.success || 0),
    frequent: Number(t.rate_limited || 0),
    failed: Number(t.failed || 0),
    status,
    errorMessage: t.error_message,
    timeline: t.timeline,
  };
}

function selectableStatus(status: MemberStatus): boolean {
  return status === "waiting" || status === "failed" || status === "rate_limited";
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
  rateSeries: RateSeriesPoint[];
  autoScrollLogs: boolean;
  selectedQqs: Set<number>;
  activeTab: "members" | "progress";
  tasks: InviteTask[];
  currentTaskId: string | null;
  detailMemberQq: number | null;
  setConfig: (patch: Partial<InviteConfig>) => void;
  setActiveTab: (tab: "members" | "progress") => void;
  setAutoScrollLogs: (value: boolean) => void;
  setDetailMemberQq: (qq: number | null) => void;
  toggleSelect: (qq: number) => void;
  toggleSelectAll: (qqs: number[]) => void;
  selectQq: (qq: number) => void;
  deselectQq: (qq: number) => void;
  requeueMember: (qq: number) => void;
  loadConfig: () => Promise<void>;
  saveConfig: () => Promise<void>;
  loadMembers: () => Promise<void>;
  startInvite: () => Promise<void>;
  stopInvite: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  loadTasks: () => Promise<void>;
  clearLogs: () => Promise<void>;
  clearRateLimits: () => Promise<void>;
  clearFailed: () => Promise<void>;
  getTask: (id: string) => InviteTask | undefined;
  getMember: (qq: number) => Member | undefined;
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
  rateSeries: [],
  autoScrollLogs: true,
  selectedQqs: new Set<number>(),
  activeTab: "members",
  tasks: [],
  currentTaskId: null,
  detailMemberQq: null,

  setConfig: (patch) => set((s) => ({ config: { ...s.config, ...patch } })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setAutoScrollLogs: (value) => set({ autoScrollLogs: value }),
  setDetailMemberQq: (qq) => set({ detailMemberQq: qq }),

  toggleSelect: (qq) =>
    set((s) => {
      const member = s.members.find((m) => m.qq === qq);
      if (member && !selectableStatus(member.status) && member.status !== "waiting") {
        if (member.status === "filtered" || member.status === "success" || member.status === "inviting") {
          return {};
        }
      }
      const next = new Set(s.selectedQqs);
      if (next.has(qq)) next.delete(qq);
      else next.add(qq);
      return { selectedQqs: next };
    }),

  toggleSelectAll: (qqs) =>
    set((s) => {
      const selectable = qqs.filter((qq) => {
        const m = s.members.find((x) => x.qq === qq);
        return m && selectableStatus(m.status);
      });
      const allSelected = selectable.every((qq) => s.selectedQqs.has(qq));
      return { selectedQqs: allSelected ? new Set<number>() : new Set(selectable) };
    }),

  selectQq: (qq) =>
    set((s) => {
      const next = new Set(s.selectedQqs);
      next.add(qq);
      return { selectedQqs: next };
    }),

  deselectQq: (qq) =>
    set((s) => {
      const next = new Set(s.selectedQqs);
      next.delete(qq);
      return { selectedQqs: next };
    }),

  requeueMember: (qq) =>
    set((s) => {
      const members = s.members.map((m) =>
        m.qq === qq && (m.status === "failed" || m.status === "rate_limited")
          ? { ...m, status: "waiting" as const, failReason: undefined }
          : m,
      );
      const next = new Set(s.selectedQqs);
      next.add(qq);
      toast("info", "已重新加入邀请队列");
      return { members, selectedQqs: next };
    }),

  loadConfig: async () => {
    guardServiceReady();
    const config = await api.getConfig();
    const settings = useSettingsStore.getState().settings;
    set({
      config: {
        ...config,
        batch_count: config.batch_count || settings.defaultBatchCount,
        interval_ms: config.interval_ms || settings.defaultIntervalMs,
        filter_staff: config.filter_staff ?? settings.defaultFilterStaff,
      },
      statusText: "就绪",
    });
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
      const selected = new Set(
        members.filter((m) => m.status === "waiting").map((m) => m.qq),
      );
      set({
        members,
        membersLoaded: true,
        selectedQqs: selected,
        statusText: `成员加载完成，共 ${res.count} 人（可邀请 ${res.eligible ?? selected.size}）`,
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
    const { config, selectedQqs, members } = get();
    const qqList = Array.from(selectedQqs).filter((qq) => {
      const m = members.find((x) => x.qq === qq);
      return m && selectableStatus(m.status);
    });
    if (qqList.length === 0) {
      toast("warning", "请至少选择一名成员");
      return;
    }
    set({ inviting: true, statusText: "正在启动邀请...", activeTab: "progress" });
    try {
      await api.saveConfig(config);
      const res = await api.startInvite({
        target_group_id: config.target_group_id,
        source_group_id: config.source_group_id,
        batch_count: Number(config.batch_count) || 20,
        interval_ms: Number(config.interval_ms) || 1500,
        filter_staff: config.filter_staff,
        qq_list: qqList,
      });
      const taskId = res.task_id || `task-${Date.now()}`;
      const task: InviteTask = {
        id: taskId,
        sourceGroup: config.source_group_id,
        targetGroup: config.target_group_id,
        startTime: Date.now(),
        total: qqList.length,
        success: 0,
        frequent: 0,
        failed: 0,
        status: "running",
      };
      set((s) => ({
        statusText: "邀请运行中",
        currentTaskId: taskId,
        tasks: [task, ...s.tasks.filter((t) => t.id !== taskId)],
      }));
      toast("info", "任务已启动");
      await get().refreshStatus();
      await get().loadTasks();
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
        statusText: "正在停止...",
        tasks: s.tasks.map((t) =>
          t.id === taskId ? { ...t, status: "stopping" as const } : t,
        ),
      }));
      toast("warning", "已发送停止请求");
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

      const taskId = status.task_id || currentTaskId;
      let mappedStatus: InviteTask["status"] = "completed";
      if (status.status === "running" || status.status === "preparing") mappedStatus = status.status;
      else if (status.status === "stopping") mappedStatus = "stopping";
      else if (status.status === "stopped") mappedStatus = "stopped";
      else if (status.status === "error") mappedStatus = "error";
      else if (status.status === "completed") mappedStatus = "completed";
      else if (status.running) mappedStatus = "running";

      const updatedTasks = tasks.map((t) => {
        if (taskId && t.id !== taskId) return t;
        return {
          ...t,
          id: taskId || t.id,
          total: status.total || t.total,
          success: status.success,
          frequent: status.rate_limited,
          failed: status.failed,
          status: mappedStatus,
          endTime: status.finished_at
            ? status.finished_at * (status.finished_at > 1e12 ? 1 : 1000)
            : t.endTime,
          errorMessage: status.error_message || t.errorMessage,
        };
      });

      useLogStore.getState().setFromRaw(status.logs);
      set({
        stats: status,
        members: status.members.length ? status.members : members,
        logs: status.logs,
        rateLimitList: status.rate_limit_list,
        failedList: status.failed_list,
        rateSeries: status.rate_series,
        inviting: status.running,
        currentTaskId: taskId,
        tasks: updatedTasks,
        statusText: status.running
          ? status.message || "邀请运行中"
          : status.message || "就绪",
      });
    } catch (e) {
      if (e instanceof ApiError && (e.code === "port_conflict" || e.code === "PORT_CONFLICT")) {
        useServiceStore.setState({
          localService: "port_conflict",
          message: e.message,
          bootstrapped: false,
        });
      }
      set({ statusText: e instanceof Error ? e.message : "状态刷新失败" });
    }
  },

  loadTasks: async () => {
    try {
      guardServiceReady();
      const list = await api.listTasks();
      const mapped = list.map(mapPersistedTask);
      set({ tasks: mapped });
      const running = mapped.find((t) => t.status === "running" || t.status === "preparing");
      if (running) set({ currentTaskId: running.id });
    } catch {
      /* idle until service ready */
    }
  },

  clearLogs: async () => {
    try {
      guardServiceReady();
      await api.clearLogs();
      set({ logs: [] });
      useLogStore.getState().clear();
      toast("success", "日志已清空");
      await get().refreshStatus();
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "清空失败");
    }
  },

  clearRateLimits: async () => {
    try {
      guardServiceReady();
      await api.clearRateLimits();
      set({ rateLimitList: [] });
      toast("success", "频繁记录已清空");
      await get().refreshStatus();
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "清空失败");
    }
  },

  clearFailed: async () => {
    try {
      guardServiceReady();
      await api.clearFailed();
      set({ failedList: [] });
      toast("success", "失败记录已清空");
      await get().refreshStatus();
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "清空失败");
    }
  },

  getTask: (id) => get().tasks.find((t) => t.id === id),
  getMember: (qq) => get().members.find((m) => m.qq === qq),
}));
