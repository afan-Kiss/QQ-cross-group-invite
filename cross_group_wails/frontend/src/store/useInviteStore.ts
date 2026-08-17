import { create } from "zustand";
import { api, ApiError, applyResultsToMembers } from "@/lib/api";
import { toEpochMs } from "@/lib/utils";
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

let membersLoadGeneration = 0;

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
  status: "running" | "stopped" | "completed" | "error" | "preparing" | "stopping" | "interrupted";
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
  else if (statusRaw === "interrupted") status = "interrupted";
  else if (statusRaw === "completed") status = "completed";

  return {
    id: String(t.id),
    sourceGroup: String(t.source_group_id ?? ""),
    targetGroup: String(t.target_group_id ?? ""),
    startTime: toEpochMs(t.started_at || t.created_at || 0),
    endTime: t.finished_at ? toEpochMs(t.finished_at) : undefined,
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

export type InvitePhase = "idle" | "starting" | "running" | "stopping";

interface InviteStore {
  config: InviteConfig;
  members: Member[];
  membersRevision: number;
  memberResultTaskId: string | null;
  membersLoaded: boolean;
  loadingMembers: boolean;
  inviting: boolean;
  invitePhase: InvitePhase;
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
  stopInvite: (taskId?: string) => Promise<void>;
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
  membersRevision: 0,
  memberResultTaskId: null,
  membersLoaded: false,
  loadingMembers: false,
  inviting: false,
  invitePhase: "idle",
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

  setConfig: (patch) =>
    set((s) => {
      const config = { ...s.config, ...patch };
      const sourceChanged =
        patch.source_group_id !== undefined && patch.source_group_id !== s.config.source_group_id;
      const filterChanged =
        patch.filter_staff !== undefined && patch.filter_staff !== s.config.filter_staff;
      if (sourceChanged || filterChanged) {
        membersLoadGeneration += 1;
        return {
          config,
          members: [],
          membersRevision: s.membersRevision + 1,
          memberResultTaskId: null,
          membersLoaded: false,
          selectedQqs: new Set<number>(),
          loadingMembers: false,
          statusText: sourceChanged
            ? "来源群已修改，请重新加载成员"
            : "过滤规则已修改，请重新加载成员",
        };
      }
      return { config };
    }),
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
      const allSelected = selectable.length > 0 && selectable.every((qq) => s.selectedQqs.has(qq));
      const next = new Set(s.selectedQqs);
      if (allSelected) {
        for (const qq of selectable) next.delete(qq);
      } else {
        for (const qq of selectable) next.add(qq);
      }
      return { selectedQqs: next };
    }),

  selectQq: (qq) =>
    set((s) => {
      const m = s.members.find((x) => x.qq === qq);
      if (!m || !selectableStatus(m.status)) return {};
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
      const target = s.members.find((m) => m.qq === qq);
      if (!target || (target.status !== "failed" && target.status !== "rate_limited")) {
        return {};
      }
      const members = s.members.map((m) =>
        m.qq === qq ? { ...m, status: "waiting" as const, failReason: undefined } : m,
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
    const generation = ++membersLoadGeneration;
    const sourceGroupId = config.source_group_id;
    const filterStaff = config.filter_staff;
    set({ loadingMembers: true, statusText: "正在加载成员..." });
    try {
      const res = await api.loadMembers({
        source_group_id: sourceGroupId,
        filter_staff: filterStaff,
      });
      const latest = get();
      if (
        generation !== membersLoadGeneration ||
        latest.config.source_group_id !== sourceGroupId ||
        latest.config.filter_staff !== filterStaff
      ) {
        return;
      }
      const members = api.mapLoadedMembers(res.members, filterStaff);
      const selected = new Set(
        members.filter((x) => x.status === "waiting").map((x) => x.qq),
      );
      set((s) => ({
        members,
        membersRevision: s.membersRevision + 1,
        memberResultTaskId: null,
        membersLoaded: true,
        selectedQqs: selected,
        statusText: `成员加载完成，共 ${res.count} 人（可邀请 ${res.eligible ?? selected.size}）`,
      }));
      toast("success", "成员加载完成");
      await get().refreshStatus();
    } catch (e) {
      if (generation !== membersLoadGeneration) return;
      const msg = e instanceof Error ? e.message : "加载失败";
      set({ statusText: msg });
      toast("error", msg);
    } finally {
      if (generation === membersLoadGeneration) {
        set({ loadingMembers: false });
      }
    }
  },

  startInvite: async () => {
    guardServiceReady();
    guardNapcatOnline();
    if (get().invitePhase !== "idle") {
      return;
    }
    const { config, selectedQqs, members } = get();
    const qqList = Array.from(selectedQqs).filter((qq) => {
      const m = members.find((x) => x.qq === qq);
      return m && selectableStatus(m.status);
    });
    if (!get().membersLoaded) {
      toast("warning", "\u8bf7\u5148\u52a0\u8f7d\u6210\u5458");
      return;
    }
    if (qqList.length === 0) {
      toast("warning", "\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u540d\u6210\u5458");
      return;
    }
    set({
      invitePhase: "starting",
      inviting: true,
      statusText: "\u6b63\u5728\u542f\u52a8\u9080\u8bf7...",
      activeTab: "progress",
    });
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
      const taskId = String(res.task_id || "").trim();
      if (!taskId) {
        throw new Error("\u542f\u52a8\u5931\u8d25\uff1a\u672a\u8fd4\u56de task_id");
      }
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
        invitePhase: "running",
        inviting: true,
        memberResultTaskId: taskId,
        statusText: "\u9080\u8bf7\u8fd0\u884c\u4e2d",
        currentTaskId: taskId,
        tasks: [task, ...s.tasks.filter((x) => x.id !== taskId)],
      }));
      toast("info", "\u4efb\u52a1\u5df2\u542f\u52a8");
      await get().refreshStatus();
      await get().loadTasks();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "\u542f\u52a8\u5931\u8d25";
      set({ invitePhase: "idle", inviting: false, statusText: msg });
      toast("error", msg);
    }
  },
  stopInvite: async (taskId) => {
    guardServiceReady();
    const phase = get().invitePhase;
    if (phase === "starting") {
      // New task_id not known yet; never stop using a previous task id.
      return;
    }
    if (phase === "stopping") {
      return;
    }
    const activeId =
      taskId ||
      (phase === "running" ? get().memberResultTaskId || get().currentTaskId || undefined : undefined);
    if (!activeId) {
      toast("warning", "\u5f53\u524d\u6ca1\u6709\u53ef\u505c\u6b62\u7684\u4efb\u52a1");
      return;
    }
    set((s) => ({
      invitePhase: "stopping",
      inviting: true,
      statusText: "\u6b63\u5728\u505c\u6b62...",
      tasks: s.tasks.map((task) =>
        task.id === activeId ? { ...task, status: "stopping" as const } : task,
      ),
    }));
    try {
      await api.stopInvite(activeId);
      toast("warning", "\u5df2\u53d1\u9001\u505c\u6b62\u8bf7\u6c42");
      await get().refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "\u505c\u6b62\u5931\u8d25";
      set({ statusText: msg, invitePhase: get().invitePhase === "stopping" ? "running" : get().invitePhase });
      toast("error", msg);
    }
  },
  refreshStatus: async () => {
    const service = useServiceStore.getState();
    if (service.localService !== "ready") return;
    const snap = get();
    const rev = snap.membersRevision;
    const sourceGroupId = snap.config.source_group_id;
    const filterStaff = snap.config.filter_staff;
    const resultTaskId = snap.memberResultTaskId;
    const membersAtStart = snap.members;
    try {
      const status = await api.getStatus();
      useServiceStore.setState({
        napcatOnline: Boolean(status.napcat_online),
        napcatMessage: status.napcat_message ?? "",
      });

      const latest = get();
      const configChanged =
        latest.membersRevision !== rev ||
        latest.config.source_group_id !== sourceGroupId ||
        latest.config.filter_staff !== filterStaff;

      // Always refresh global/service-facing fields; never revive stale members.
      useLogStore.getState().setFromRaw(status.logs);

      let nextMembers = latest.members;
      if (!configChanged) {
        const canApply =
          Boolean(resultTaskId) &&
          Boolean(status.task_id) &&
          status.task_id === resultTaskId &&
          latest.memberResultTaskId === resultTaskId;
        if (canApply) {
          nextMembers = applyResultsToMembers(membersAtStart, status.results);
        }
      }

      const ownedTask =
        Boolean(latest.memberResultTaskId) && status.task_id === latest.memberResultTaskId;
      const taskIdForUi = ownedTask
        ? status.task_id
        : latest.invitePhase === "running" || latest.invitePhase === "stopping"
          ? latest.currentTaskId
          : status.running
            ? status.task_id || latest.currentTaskId
            : latest.currentTaskId;

      let mappedStatus: InviteTask["status"] = "completed";
      if (status.status === "running" || status.status === "preparing") mappedStatus = status.status;
      else if (status.status === "stopping") mappedStatus = "stopping";
      else if (status.status === "stopped") mappedStatus = "stopped";
      else if (status.status === "error") mappedStatus = "error";
      else if (status.status === "completed") mappedStatus = "completed";
      else if (status.running) mappedStatus = "running";

      const updatedTasks = latest.tasks.map((task) => {
        if (!taskIdForUi || task.id !== taskIdForUi) return task;
        if (!ownedTask && latest.invitePhase === "starting") return task;
        return {
          ...task,
          id: taskIdForUi || task.id,
          total: status.total || task.total,
          success: status.success,
          frequent: status.rate_limited,
          failed: status.failed,
          status: mappedStatus,
          endTime: status.finished_at ? toEpochMs(status.finished_at) : task.endTime,
          errorMessage: status.error_message || task.errorMessage,
        };
      });

      let invitePhase = latest.invitePhase;
      let inviting = latest.inviting;
      if (latest.invitePhase === "starting") {
        // Keep starting until startInvite resolves with task_id.
        invitePhase = "starting";
        inviting = true;
      } else if (ownedTask) {
        if (status.status === "stopping") {
          invitePhase = "stopping";
          inviting = true;
        } else if (status.running || status.status === "preparing" || status.status === "running") {
          invitePhase = "running";
          inviting = true;
        } else if (
          !status.running ||
          status.status === "stopped" ||
          status.status === "completed" ||
          status.status === "error" ||
          status.status === "idle" ||
          status.status === "interrupted"
        ) {
          invitePhase = "idle";
          inviting = false;
        }
      } else if (latest.invitePhase === "running" || latest.invitePhase === "stopping") {
        // Stale/empty status must not demote an owned local phase mid-flight.
        invitePhase = latest.invitePhase;
        inviting = true;
      } else if (status.running || status.status === "preparing") {
        invitePhase = "running";
        inviting = true;
      } else if (status.status === "stopping") {
        invitePhase = "stopping";
        inviting = true;
      } else {
        invitePhase = "idle";
        inviting = false;
      }

      set({
        stats: status,
        members: configChanged ? latest.members : nextMembers,
        logs: status.logs,
        rateLimitList: status.rate_limit_list,
        failedList: status.failed_list,
        rateSeries: status.rate_series,
        inviting,
        invitePhase,
        currentTaskId:
          invitePhase === "idle" && !status.running
            ? null
            : taskIdForUi || latest.currentTaskId,
        tasks: updatedTasks,
        statusText: inviting
          ? status.message || "\u9080\u8bf7\u8fd0\u884c\u4e2d"
          : status.message || "\u5c31\u7eea",
      });
    } catch (e) {
      if (e instanceof ApiError && (e.code === "port_conflict" || e.code === "PORT_CONFLICT")) {
        useServiceStore.setState({
          localService: "port_conflict",
          message: e.message,
          bootstrapped: false,
        });
      }
      set({ statusText: e instanceof Error ? e.message : "\u72b6\u6001\u5237\u65b0\u5931\u8d25" });
    }
  },
  loadTasks: async () => {
    try {
      guardServiceReady();
      const list = await api.listTasks();
      const mapped = list.map(mapPersistedTask);
      const running = mapped.find(
        (t) => t.status === "running" || t.status === "preparing" || t.status === "stopping",
      );
      set({ tasks: mapped, currentTaskId: running ? running.id : null });
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
